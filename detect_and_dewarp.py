"""Module for detecting April Tags in images and de-warping the detected area."""

import cv2
import numpy as np
import pupil_apriltags as apriltag
from pathlib import Path
from generate_tracking_squares import get_data_regions

from encode_data import ALLOWED_COLOR_PALETTE, decode_image_data, encode_bytes_to_rgb, encode_2bytes_to_rgb

PALETTE_COLORS: np.ndarray = np.array(ALLOWED_COLOR_PALETTE, dtype=np.uint8)
PALETTE_COLOR_ARRAY: np.ndarray = PALETTE_COLORS.astype(np.int16)
WHITE_COLOR: np.ndarray = np.array((255, 255, 255), dtype=np.int16)
WHITE_INDEX: int = int(np.where(np.all(PALETTE_COLOR_ARRAY == WHITE_COLOR, axis=1))[0][0])
NON_WHITE_INDICES: np.ndarray = np.delete(np.arange(len(PALETTE_COLORS)), WHITE_INDEX)
NON_WHITE_PALETTE: np.ndarray = PALETTE_COLOR_ARRAY[NON_WHITE_INDICES]
NON_WHITE_PALETTE_FLOAT: np.ndarray = NON_WHITE_PALETTE.astype(np.float32)
WHITE_MIN_CHANNEL: int = 230
WHITE_MAX_CHANNEL_SPREAD: int = 30

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
        return (50, 30)  # Fallback defaults

    # Tag16h5 has 6x6 data bits + 2-bit border = 8x8 modules total
    # (including white border, but not quiet zone)
    apriltag_modules = 6

    # Calculate average tag size in pixels from all detected tags
    tag_sizes = []
    for tag in tags:
        corners = tag.corners
        # Calculate width and height of the tag
        width = np.linalg.norm(corners[1] - corners[0])
        height = np.linalg.norm(corners[2] - corners[1])
        tag_sizes.append((width + height) / 2)

    avg_tag_size_px = np.mean(tag_sizes)
    pixels_per_module = avg_tag_size_px / apriltag_modules

    # Calculate total distance between opposite corners
    tl_to_br = np.linalg.norm(outer_corners[2] - outer_corners[0])
    tr_to_bl = np.linalg.norm(outer_corners[3] - outer_corners[1])
    avg_diagonal = (tl_to_br + tr_to_bl) / 2

    # Estimate total modules (divide by sqrt(2) for side length from diagonal)
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

    # Collect all corner points from all tags
    all_corners = []
    for tag in tags:
        all_corners.extend(tag.corners)

    all_corners = np.array(all_corners)

    # Find extreme corners
    outer_corners = np.array(
        [
            all_corners[np.argmin(all_corners.sum(axis=1))],  # top-left
            all_corners[np.argmax(all_corners[:, 0] - all_corners[:, 1])],  # top-right
            all_corners[np.argmax(all_corners.sum(axis=1))],  # bottom-right
            all_corners[
                np.argmin(all_corners[:, 0] - all_corners[:, 1])
            ],  # bottom-left
        ]
    )

    return outer_corners


def assign_palette_indices(pixel_values: np.ndarray) -> np.ndarray:
    """Assign each pixel in the array to the closest palette index.

    Args:
        pixel_values: Array of pixel colors shaped (N, 3) or (3,).

    Returns:
        Array of palette indices that best match each pixel.
    """
    pixel_array = np.atleast_2d(pixel_values).astype(np.int16, copy=False)
    min_channels = pixel_array.min(axis=1)
    max_channels = pixel_array.max(axis=1)
    channel_spread = max_channels - min_channels
    white_mask = (min_channels >= WHITE_MIN_CHANNEL) & (channel_spread <= WHITE_MAX_CHANNEL_SPREAD)

    palette_indices = np.empty(pixel_array.shape[0], dtype=np.int32)
    palette_indices[white_mask] = WHITE_INDEX

    if np.any(~white_mask):
        residual_pixels = pixel_array[~white_mask].astype(np.float32, copy=False)
        distances = np.linalg.norm(
            residual_pixels[:, np.newaxis, :] - NON_WHITE_PALETTE_FLOAT[np.newaxis, :, :],
            axis=2,
        )
        nearest = np.argmin(distances, axis=1)
        palette_indices[~white_mask] = NON_WHITE_INDICES[nearest]

    return palette_indices


def get_majority_color(cell: np.ndarray) -> tuple[int, int, int]:
    """Get the palette color that the most pixels in the cell are closest to.

    Args:
        cell: Image cell as numpy array.

    Returns:
        BGR tuple of the palette color with the highest pixel count.
    """
    if cell.size == 0:
        return (0, 0, 0)

    pixels = cell.reshape(-1, cell.shape[-1])
    closest_palette_indices = assign_palette_indices(pixels)

    counts = np.bincount(closest_palette_indices, minlength=len(PALETTE_COLORS))
    majority_palette_idx = int(np.argmax(counts))
    majority_color = PALETTE_COLORS[majority_palette_idx]
    return tuple(int(channel) for channel in majority_color)


def map_to_palette(color: tuple[int, int, int]) -> tuple[int, int, int]:
    """Map an arbitrary BGR color to the nearest palette entry.

    Args:
        color: BGR color to quantize.

    Returns:
        Palette color in BGR order.
    """
    color_array = np.array(color, dtype=np.int16)
    palette_index = int(assign_palette_indices(color_array)[0])
    nearest_color = PALETTE_COLORS[palette_index]
    return tuple(int(channel) for channel in nearest_color)


def print_color_grid(grid: np.ndarray, title: str) -> None:
    """Print a color grid in a readable text format.

    Args:
        grid: Color grid as numpy array (height, width, 3).
        title: Title to display above the grid.
    """
    print(f"\n{title}:")

    # Create a mapping from colors to symbols
    color_map = {
        (255, 255, 255): 'W',  # White
        (0, 0, 255): 'R',      # Red
        (0, 255, 0): 'G',      # Green
        (255, 0, 0): 'B',      # Blue
        (0, 0, 0): 'K',        # Black
    }

    for row in grid:
        row_str = ""
        for color in row:
            color_tuple = tuple(int(c) for c in color)
            if any(channel < 0 for channel in color_tuple):
                row_str += " "
                continue
            symbol = color_map.get(color_tuple, '?')
            row_str += symbol
        print(row_str)


def colors_to_symbols(colors: list[tuple[int, int, int]]) -> str:
    """Convert a list of BGR colors to a string of readable symbols.

    Args:
        colors: List of BGR color tuples.

    Returns:
        String representation using color symbols.
    """
    color_map = {
        (255, 255, 255): 'W',  # White
        (0, 0, 255): 'R',      # Red
        (0, 255, 0): 'G',      # Green
        (255, 0, 0): 'B',      # Blue
        (0, 0, 0): 'K',        # Black
    }

    symbols = []
    for color in colors:
        color_tuple = tuple(int(c) for c in color)
        symbol = color_map.get(color_tuple, '?')
        symbols.append(symbol)

    return ''.join(symbols)


def decode_and_verify_data(
    extracted_image: np.ndarray,
    reference_data_path: Path,
    visual_grid: np.ndarray | None = None,
) -> None:
    """Decode data from the extracted image and compare it with the reference data.

    Args:
        extracted_image: Image containing encoded data pixels.
        reference_data_path: Path to the reference packed data file.
        visual_grid: Optional grid highlighting only data regions for visualization.
    """
    reference_bytes: bytes | None = None
    original_length: int | None = None

    if reference_data_path.exists():
        reference_bytes = reference_data_path.read_bytes()
        original_length = len(reference_bytes)
        print(
            f"Loaded reference data: {reference_data_path} ({original_length} bytes)"
        )
    else:
        print(f"Reference data file not found: {reference_data_path}")

    try:
        decoded_bytes = decode_image_data(
            extracted_image,
            original_length=original_length,
            data_padding=0,
        )
    except Exception as decode_error:
        print(f"Failed to decode data from image: {decode_error}")
        return

    print(f"Decoded data size: {len(decoded_bytes)} bytes")

    if reference_bytes is None:
        return

    data_matches = decoded_bytes == reference_bytes
    print(f"Data matches reference: {data_matches}")

    if data_matches:
        return

    # Show color patterns when data doesn't match
    display_grid = visual_grid if visual_grid is not None else extracted_image
    print_color_grid(display_grid, "Detected Color Pattern")

    # Create expected color pattern from reference data
    expected_colors = encode_bytes_to_rgb(reference_bytes)
    expected_grid = np.full_like(extracted_image, 255, dtype=np.uint8)

    # Place colors in data regions only (same logic as encoder)
    height, width = extracted_image.shape[:2]
    data_regions = get_data_regions(width, height, padding=4, tag_data_gap=1, data_padding=0)

    color_idx = 0
    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                if color_idx < len(expected_colors):
                    expected_grid[row, col] = expected_colors[color_idx]
                    color_idx += 1

    print_color_grid(expected_grid, "Expected Color Pattern from Reference")

    for index, (decoded_byte, reference_byte) in enumerate(
        zip(decoded_bytes, reference_bytes)
    ):
        if decoded_byte != reference_byte:
            # Get color sequences for the mismatched bytes (4 colors per byte)
            decoded_colors = encode_2bytes_to_rgb(decoded_byte, 0)[:4]
            reference_colors = encode_2bytes_to_rgb(reference_byte, 0)[:4]
            print(
                f"First mismatch at byte {index}: decoded {decoded_byte} vs reference {reference_byte}"
            )
            print(f"  Decoded colors: {colors_to_symbols(decoded_colors)}")
            print(f"  Reference colors: {colors_to_symbols(reference_colors)}")
            break


def process_image(
    image_path: str,
    reference_data_path: str | Path | None = "MatchData.packed",
) -> None:
    """Process an image to detect April Tags and dewarp the area.

    Args:
        image_path: Path to the input image.
        reference_data_path: Optional path to the reference packed data file.
    """
    reference_file: Path | None = None
    if reference_data_path is not None:
        reference_file = Path(reference_data_path)

    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    grey_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Initialize April Tag detector
    detector = apriltag.Detector(
        families="tag16h5",
        nthreads=4,
        quad_decimate=1.0,
        quad_sigma=0.0,
        refine_edges=1,
        decode_sharpening=0.25,
        debug=0,
    )

    # Detect April Tags
    detections = detector.detect(grey_image)

    if not detections:
        print("No April Tags detected!")
        return

    print(f"Detected {len(detections)} April Tags")
    new_detections = []
    for detection in detections:
        if detection.tag_id == 0 and detection.hamming < 0.1:
            new_detections.append(detection)

    detections = new_detections

    print(f"Filtered to {len(detections)} April Tags (ID=0)")

    # Find outer corners from all detected tags
    outer_corners = find_outer_corners_from_tags(detections)
    print(f"Outer corners: {outer_corners}")

    if len(outer_corners) == 0:
        print("Could not determine outer corners from detected tags!")
        return

    # Auto-detect grid size and output resolution
    pixels_per_module, total_cells = estimate_module_size(detections, outer_corners)
    output_size = (total_cells * 50, total_cells * 50)  # 50 pixels per cell

    print(f"Auto-detected grid size: {total_cells}x{total_cells} cells")
    print(f"Output size: {output_size[0]}x{output_size[1]} pixels")
    print(f"Estimated {pixels_per_module:.2f} pixels per module in original image")
    
    # Dewarp the image
    dewarped_color = dewarp_image(image, outer_corners, output_size=output_size)

    # Create majority color grid
    cell_size = dewarped_color.shape[0] // total_cells

    print(f"Cell size: {cell_size} pixels/cell")

    data_regions: list[tuple[slice, slice]] = get_data_regions(
        total_cells,
        total_cells,
        padding=4,
        tag_data_gap=1,
        data_padding=0,
    )

    if not data_regions:
        raise ValueError("No data regions could be determined from the decoded grid size.")

    no_data_value: int = -1
    decoded_grid_visual = np.full((total_cells, total_cells, 3), no_data_value, dtype=np.int16)
    decoded_data_image = np.zeros((total_cells, total_cells, 3), dtype=np.uint8)

    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                y_start = row * cell_size
                y_end = min((row + 1) * cell_size, dewarped_color.shape[0])
                x_start = col * cell_size
                x_end = min((col + 1) * cell_size, dewarped_color.shape[1])

                cell = dewarped_color[y_start:y_end, x_start:x_end]
                majority_color = get_majority_color(cell)
                quantized_color = map_to_palette(majority_color)
                decoded_grid_visual[row, col] = quantized_color
                decoded_data_image[row, col] = quantized_color
            
    if reference_file is not None:
        decode_and_verify_data(decoded_data_image, reference_file, decoded_grid_visual)

    # Annotate grid lines on the dewarped image
    annotated_dewarped = dewarped_color.copy()
    for i in range(1, total_cells):
        # Vertical lines
        x = i * cell_size
        cv2.line(annotated_dewarped, (x, 0), (x, dewarped_color.shape[0]), (0, 0, 255), 5)
        # Horizontal lines
        y = i * cell_size
        cv2.line(annotated_dewarped, (0, y), (dewarped_color.shape[1], y), (0, 0, 255), 5)

    # Display images
    cv2.imshow("Quantized Color Grid", cv2.resize(decoded_data_image, (800, 800), interpolation=cv2.INTER_NEAREST))
    cv2.imshow("Dewarped Color", cv2.resize(annotated_dewarped, (800, 800), interpolation=cv2.INTER_NEAREST))

    print("Press any key to close windows...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    process_image("IMG_2518.JPG")