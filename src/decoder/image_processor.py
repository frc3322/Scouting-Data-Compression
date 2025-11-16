"""Image processing utilities for detecting AprilTags and dewarping images."""

import cv2
import numpy as np
import pupil_apriltags as apriltag
from pathlib import Path

from ..common.data_regions import get_data_regions
from .color_decoder import decode_image_data, get_majority_color, map_to_palette


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

    apriltag_modules = 6

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
    """Find the extreme corners from all detected April Tags.

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

    outer_corners = np.array(
        [
            all_corners[np.argmin(all_corners.sum(axis=1))],
            all_corners[np.argmax(all_corners[:, 0] - all_corners[:, 1])],
            all_corners[np.argmax(all_corners.sum(axis=1))],
            all_corners[
                np.argmin(all_corners[:, 0] - all_corners[:, 1])
            ],
        ]
    )

    return outer_corners


def detect_and_dewarp_image(image_path: str | Path) -> tuple[np.ndarray, int] | None:
    """Detect AprilTags in an image and dewarp the detected region.

    Args:
        image_path: Path to the input image.

    Returns:
        Tuple of (dewarped_image, grid_size) if successful, None otherwise.
    """
    image_path = Path(image_path)
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    grey_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    detector = apriltag.Detector(
        families="tag16h5",
        nthreads=4,
        quad_decimate=1.0,
        quad_sigma=0.0,
        refine_edges=1,
        decode_sharpening=0.25,
        debug=0,
    )

    detections = detector.detect(grey_image)

    if not detections:
        return None

    new_detections = []
    for detection in detections:
        if detection.tag_id == 0 and detection.hamming < 0.1:
            new_detections.append(detection)

    detections = new_detections

    outer_corners = find_outer_corners_from_tags(detections)

    if len(outer_corners) == 0:
        return None

    _, total_cells = estimate_module_size(detections, outer_corners)
    output_size = (total_cells * 50, total_cells * 50)

    dewarped_color = dewarp_image(image, outer_corners, output_size=output_size)

    return (dewarped_color, total_cells)


def extract_data_from_dewarped(
    dewarped_image: np.ndarray, grid_size: int
) -> np.ndarray:
    """Extract quantized data from a dewarped image.

    Args:
        dewarped_image: Dewarped image array.
        grid_size: Size of the grid in cells.

    Returns:
        Quantized data image array.
    """
    cell_size = dewarped_image.shape[0] // grid_size

    data_regions: list[tuple[slice, slice]] = get_data_regions(
        grid_size,
        grid_size,
        tag_data_gap=1,
        data_padding=0,
    )

    if not data_regions:
        raise ValueError(
            "No data regions could be determined from the decoded grid size."
        )

    decoded_data_image = np.zeros((grid_size, grid_size, 3), dtype=np.uint8)

    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                y_start = row * cell_size
                y_end = min((row + 1) * cell_size, dewarped_image.shape[0])
                x_start = col * cell_size
                x_end = min((col + 1) * cell_size, dewarped_image.shape[1])

                cell = dewarped_image[y_start:y_end, x_start:x_end]
                majority_color = get_majority_color(cell)
                quantized_color = map_to_palette(majority_color)
                decoded_data_image[row, col] = quantized_color

    return decoded_data_image


def process_image_to_data(image_path: str | Path) -> bytes | None:
    """Process an image to extract encoded data.

    Args:
        image_path: Path to the input image.

    Returns:
        Decoded bytes if successful, None otherwise.
    """
    result = detect_and_dewarp_image(image_path)
    if result is None:
        return None

    dewarped_image, grid_size = result
    decoded_data_image = extract_data_from_dewarped(dewarped_image, grid_size)

    decoded_bytes = decode_image_data(
        decoded_data_image,
        original_length=None,
        tag_data_gap=1,
        data_padding=0,
    )

    return decoded_bytes

