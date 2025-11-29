"""Image processing utilities for detecting AprilTags and dewarping images."""

import cv2
import numpy as np
import pupil_apriltags as apriltag
from pathlib import Path

from ..common.data_regions import get_data_regions
from ..common.color_palette import palette_to_bgr
from .color_decoder import decode_image_data, map_to_palette


def estimate_module_size(tags: list, outer_corners: np.ndarray) -> tuple[int, int]:
    """Estimate the module size and total grid size from AprilTag dimensions.

    Args:
        tags: List of detected April Tag objects.
        outer_corners: Outer corner points of the region.

    Returns:
        Tuple of (pixels_per_module, total_modules) where total_modules is the
        grid size.
    """
    if not tags:
        return (50, 30)

    apriltag_modules = 8

    tag_sizes = []
    for tag in tags:
        corners = tag.corners
        width = np.linalg.norm(corners[1] - corners[0])
        height = np.linalg.norm(corners[2] - corners[1])
        tag_sizes.append((width + height) / 2)

    avg_tag_size_px = np.mean(tag_sizes)
    pixels_per_module = avg_tag_size_px / apriltag_modules

    tl_to_br = np.linalg.norm(outer_corners[2] - outer_corners[0])
    tr_to_bl = np.linalg.norm(outer_corners[3] - outer_corners[1])
    avg_diagonal = (tl_to_br + tr_to_bl) / 2

    side_length_px = avg_diagonal / np.sqrt(2)
    total_modules = int(round(side_length_px / pixels_per_module))

    return (pixels_per_module, total_modules)


def dewarp_image(
    image: np.ndarray, corners: np.ndarray, output_size: tuple = (400, 400)
) -> np.ndarray:
    """Apply perspective transformation to dewarp the image.

    Args:
        image: Input image to dewarp.
        corners: Ordered corner points (top-left, top-right, bottom-right, bottom-left).
        output_size: Desired output size (width, height).

    Returns:
        Dewarped image.
    """
    dst_points = np.array(
        [
            [0, 0],
            [output_size[0] - 1, 0],
            [output_size[0] - 1, output_size[1] - 1],
            [0, output_size[1] - 1],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(corners.astype(np.float32), dst_points)
    return cv2.warpPerspective(image, matrix, output_size)


def find_outer_corners_from_tags(tags: list) -> np.ndarray:
    """Find the extreme corners from all detected April Tags and estimate the fourth corner.

    Args:
        tags: List of detected April Tag objects.

    Returns:
        Array of outer corner points [top-left, top-right, bottom-right, bottom-left].
    """
    if not tags:
        return np.array([])

    all_corners = []
    for tag in tags:
        all_corners.extend(tag.corners)

    all_corners = np.array(all_corners)

    tl = all_corners[np.argmin(all_corners.sum(axis=1))]
    tr = all_corners[np.argmax(all_corners[:, 0] - all_corners[:, 1])]
    bl = all_corners[np.argmin(all_corners[:, 0] - all_corners[:, 1])]
    
    br = tr + (bl - tl)

    outer_corners = np.array([tl, tr, br, bl])

    return outer_corners


def reorder_corners_by_tag_ids(tags: list, corners: np.ndarray) -> np.ndarray:
    """Reorder corners so tag 0 is TL, tag 1 is TR, tag 2 is BL.

    Args:
        tags: List of detected April Tag objects with tag_id 0, 1, or 2.
        corners: Array of corner points [tl, tr, br, bl].

    Returns:
        Reordered corner array with correct orientation.
    """
    if len(tags) != 3 or len(corners) != 4:
        return corners

    tag_by_id = {tag.tag_id: tag for tag in tags}
    if len(tag_by_id) != 3:
        return corners

    tag_centers = {tag.tag_id: np.array(tag.center) for tag in tags}
    
    corner_distances = {}
    for i, corner in enumerate(corners):
        distances = {tag_id: np.linalg.norm(corner - center) 
                    for tag_id, center in tag_centers.items()}
        closest_tag = min(distances.keys(), key=lambda k, d=distances: d[k])
        corner_distances[i] = (closest_tag, distances[closest_tag])

    tl_idx = min([i for i in range(4) if corner_distances[i][0] == 0], 
                 key=lambda i: corner_distances[i][1], default=0)
    tr_idx = min([i for i in range(4) if corner_distances[i][0] == 1], 
                 key=lambda i: corner_distances[i][1], default=1)
    bl_idx = min([i for i in range(4) if corner_distances[i][0] == 2], 
                 key=lambda i: corner_distances[i][1], default=3)
    br_idx = [i for i in range(4) if i not in [tl_idx, tr_idx, bl_idx]][0]

    return np.array([corners[tl_idx], corners[tr_idx], corners[br_idx], corners[bl_idx]])


def detect_and_dewarp_image(image_path: str | Path, debug: bool = False) -> tuple[np.ndarray, int] | None:
    """Detect AprilTags in an image and dewarp the detected region.

    This function filters detections to only include tag_id 0, 1, or 2 with hamming < 0.1,
    and requires exactly 3 April tags to be detected. The function determines orientation
    based on tag positions and rotates the image accordingly for rotation-agnostic decoding.

    Args:
        image_path: Path to the input image.
        debug: If True, save intermediate images during processing.

    Returns:
        Tuple of (dewarped_image, grid_size) if successful, None otherwise.

    Raises:
        ValueError: If not exactly 3 April tags are detected after filtering.
    """
    image_path = Path(image_path)
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    grey_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    grey_image = grey_image.astype(np.uint8)

    detector = apriltag.Detector(
        families="tag36h11",
        nthreads=4,
        quad_decimate=1.0,
        quad_sigma=0.4,
        refine_edges=1,
        decode_sharpening=0.25,
        debug=0,
    )

    detections = detector.detect(grey_image)

    if not detections:
        return None

    new_detections = []
    for detection in detections:  # type: ignore
        try:
            tag_id = detection.tag_id
            hamming = detection.hamming
            if tag_id in [0, 1, 2] and hamming < 0.1:
                new_detections.append(detection)
        except (AttributeError, TypeError):
            continue

    detections = new_detections

    if len(detections) != 3:
        raise ValueError(
            f"Expected exactly 3 April tags (IDs 0, 1, 2) after filtering, but found {len(detections)}"
        )

    tag_ids = {tag.tag_id for tag in detections}
    if tag_ids != {0, 1, 2}:
        raise ValueError(
            f"Expected tags with IDs 0, 1, and 2, but found IDs: {tag_ids}"
        )

    outer_corners = find_outer_corners_from_tags(detections)

    if len(outer_corners) == 0:
        return None

    ordered_corners = reorder_corners_by_tag_ids(detections, outer_corners)

    _, total_cells = estimate_module_size(detections, ordered_corners)
    output_size = (total_cells * 50, total_cells * 50)

    dewarped_color = dewarp_image(image, ordered_corners, output_size=output_size)

    if debug:
        cv2.imwrite("dewarped_image.png", dewarped_color)

    return (dewarped_color, total_cells)


def extract_data_from_dewarped(
    dewarped_image: np.ndarray,
    grid_size: int,
    tag_data_gap: int = 1,
    data_padding: int = 0,
    debug: bool = False,
    palette_bgr: list[tuple[int, int, int]] | None = None,
) -> np.ndarray:
    """Extract quantized data from a dewarped image.

    Args:
        dewarped_image: Dewarped image array.
        grid_size: Size of the grid in cells.
        debug: If True, save intermediate images during processing.
        tag_data_gap: Number of grid cells between AprilTags and data.
        data_padding: Number of grid cells padding data from outer edges.
        palette_bgr: Optional list of BGR tuples for color palette. If None, uses default 4-color palette.

    Returns:
        Quantized data image array.
    """
    if palette_bgr is None:
        from ..common.constants import DATA_COLOR_SEQUENCE
        palette_bgr = palette_to_bgr(list(DATA_COLOR_SEQUENCE))

    num_calibration_colors = len(palette_bgr)

    cell_size = dewarped_image.shape[0] // grid_size

    data_regions: list[tuple[slice, slice]] = get_data_regions(
        grid_size,
        grid_size,
        tag_data_gap=tag_data_gap,
        data_padding=data_padding,
    )

    if not data_regions:
        raise ValueError(
            "No data regions could be determined from the decoded grid size."
        )

    # This retrieves the color of the last N pixels which are the calibration colors from the palette.
    # This accounts for varying lighting conditions.
    last_data_region = data_regions[-1]
    calibration_cells_average = []
    for row in range(last_data_region[0].stop - 1, last_data_region[0].stop):
        for col in range(
            last_data_region[1].stop - num_calibration_colors,
            last_data_region[1].stop,
        ):
            y_start = row * cell_size
            y_end = min((row + 1) * cell_size, dewarped_image.shape[0])
            x_start = col * cell_size
            x_end = min((col + 1) * cell_size, dewarped_image.shape[1])

            cell = dewarped_image[y_start:y_end, x_start:x_end]

            cell = cell[
                cell.shape[0] // 4 : cell.shape[0] * 3 // 4,
                cell.shape[1] // 4 : cell.shape[1] * 3 // 4,
            ]

            calibration_cells_average.append(np.mean(cell, axis=(0, 1)))

    # Build corrected palette from calibration cells
    # Use calibration cells to map to palette colors, wrapping if needed
    corrected_palette_bgr = []
    for i in range(len(palette_bgr)):
        calibration_idx = i % len(calibration_cells_average)
        corrected_palette_bgr.append(
            tuple(int(c) for c in calibration_cells_average[calibration_idx])
        )

    decoded_data_image = np.zeros((grid_size, grid_size, 3), dtype=np.uint8)
    annotated_image = dewarped_image.copy()

    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                y_start = row * cell_size
                y_end = min((row + 1) * cell_size, dewarped_image.shape[0])
                x_start = col * cell_size
                x_end = min((col + 1) * cell_size, dewarped_image.shape[1])

                cell = dewarped_image[y_start:y_end, x_start:x_end]
                quantized_color = map_to_palette(
                    cell,
                    corrected_palette_bgr,
                    palette_bgr,
                )
                decoded_data_image[row, col] = quantized_color

                # draw rectangle around the cell
                cv2.rectangle(
                    annotated_image,
                    (col * cell_size, row * cell_size),
                    ((col + 1) * cell_size, (row + 1) * cell_size),
                    quantized_color,
                    1,
                )
                # draw circle at the center of the cell color of the majority color
                cv2.circle(
                    annotated_image,
                    (
                        col * cell_size + cell_size // 2,
                        row * cell_size + cell_size // 2,
                    ),
                    5,
                    quantized_color,
                    -1,
                )

    # save the decoded data image
    if debug:
        cv2.imwrite("decoded_data_image.png", decoded_data_image)
        cv2.imwrite("annotated_image.png", annotated_image)

    return decoded_data_image


def process_image_to_data(
    image_path: str | Path,
    debug: bool = False,
    palette_bgr: list[tuple[int, int, int]] | None = None,
) -> bytes | None:
    """Process an image to extract encoded data.

    Args:
        image_path: Path to the input image.
        debug: If True, save intermediate images during processing.
        palette_bgr: Optional list of BGR tuples for color palette. If None, uses default 4-color palette.

    Returns:
        Decoded bytes if successful, None otherwise.

    Raises:
        ValueError: If exactly 3 April tags (IDs 0, 1, 2) are not detected after filtering.
    """
    if palette_bgr is None:
        from ..common.constants import DATA_COLOR_SEQUENCE
        palette_bgr = palette_to_bgr(list(DATA_COLOR_SEQUENCE))

    result = detect_and_dewarp_image(image_path, debug=debug)
    if result is None:
        return None

    dewarped_image, grid_size = result
    decoded_data_image = extract_data_from_dewarped(
        dewarped_image, grid_size, debug=debug, palette_bgr=palette_bgr
    )

    num_calibration_colors = len(palette_bgr)
    decoded_bytes = decode_image_data(
        decoded_data_image,
        original_length=None,
        tag_data_gap=1,
        data_padding=0,
        palette_bgr=palette_bgr,
        num_calibration_pixels=num_calibration_colors,
    )

    return decoded_bytes
