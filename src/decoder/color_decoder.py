"""Color decoding utilities for extracting RGB values from images."""

import numpy as np
from ..common.constants import (
    DATA_COLOR_MAP,
    PALETTE_COLORS,
)
from ..common.data_regions import get_data_regions


def assign_palette_indices(
    pixel_values: np.ndarray,
    corrected_red_color: tuple[int, int, int],
    corrected_blue_color: tuple[int, int, int],
    corrected_green_color: tuple[int, int, int],
    corrected_black_color: tuple[int, int, int],
    corrected_white_color: tuple[int, int, int],
) -> np.ndarray:
    """Assign each pixel in the array to the closest palette index using corrected colors.

    Args:
        pixel_values: Array of pixel colors shaped (N, 3) or (3,).
        corrected_red_color: Corrected red BGR tuple.
        corrected_blue_color: Corrected blue BGR tuple.
        corrected_green_color: Corrected green BGR tuple.
        corrected_black_color: Corrected black BGR tuple.
        corrected_white_color: Corrected white BGR tuple.

    Returns:
        Array of palette indices that best match each pixel.
    """
    pixel_array = np.atleast_2d(pixel_values).astype(np.float32, copy=False)
    np.clip(pixel_array, 0.0, 255.0, out=pixel_array)

    # Build corrected palette from the provided corrected RGB tuples
    corrected_palette = np.array(
        [
            corrected_red_color,  # Red BGR
            corrected_green_color,  # Green BGR
            corrected_blue_color,  # Blue BGR
            corrected_black_color,  # Black BGR
            corrected_white_color,  # White BGR
        ],
        dtype=np.float32,
    )

    color_distances = np.linalg.norm(
        pixel_array[:, np.newaxis, :] - corrected_palette[np.newaxis, :, :],
        axis=2,
    )
    nearest_palette_indices = np.argmin(color_distances, axis=1).astype(np.int32)

    # return the nearest palette index for each pixel
    return nearest_palette_indices


def map_to_palette(
    cell: np.ndarray,
    corrected_red_color: tuple[int, int, int],
    corrected_blue_color: tuple[int, int, int],
    corrected_green_color: tuple[int, int, int],
    corrected_black_color: tuple[int, int, int],
    corrected_white_color: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Map an image cell to the nearest palette entry. Sees what palette color is most common in the cell.

    Args:
        cell: Image cell as numpy array.
        corrected_red_color: Corrected red BGR tuple.
        corrected_blue_color: Corrected blue BGR tuple.
        corrected_green_color: Corrected green BGR tuple.
        corrected_black_color: Corrected black BGR tuple.
        corrected_white_color: Corrected white BGR tuple.

    Returns:
        Palette color in BGR order.
    """
    # only use center half of the cell, ie from 1/4 to 3/4 of the width and height
    cell = cell[
        cell.shape[0] // 4 : cell.shape[0] * 3 // 4,
        cell.shape[1] // 4 : cell.shape[1] * 3 // 4,
    ]

    # Reshape cell to (N, 3) where N is total pixels, 3 is RGB channels
    if cell.ndim == 3:
        pixel_values = cell.reshape(-1, 3)
    else:
        pixel_values = cell

    # go through each pixel in the cell and assign a palette index
    palette_indices = assign_palette_indices(
        pixel_values,
        corrected_red_color,
        corrected_blue_color,
        corrected_green_color,
        corrected_black_color,
        corrected_white_color,
    )

    # count the number of pixels for each palette index
    counts = np.bincount(palette_indices, minlength=len(PALETTE_COLORS))

    # get the palette index with the highest count
    majority_palette_idx = int(np.argmax(counts))

    # get the color for the majority palette index
    majority_color = PALETTE_COLORS[majority_palette_idx]
    return tuple(int(channel) for channel in majority_color)


def decode_rgb_to_2bytes(rgb_list: list[tuple[int, int, int]]) -> tuple[int, int]:
    """Decode a list of BGR values back to 2 bytes.

    Args:
        rgb_list: List of 8 BGR tuples.

    Returns:
        Tuple of (byte1, byte2).
    """
    color_to_value: dict[tuple[int, int, int], int] = {
        color: value for value, color in DATA_COLOR_MAP.items()
    }
    color_to_value[(255, 255, 255)] = 3

    combined_value = 0
    for index, rgb in enumerate(rgb_list):
        mapped_value = color_to_value.get(rgb, 3)
        combined_value |= mapped_value << (index * 2)

    byte1 = (combined_value >> 8) & 0xFF
    byte2 = combined_value & 0xFF

    return (byte1, byte2)


def decode_image_data(
    image: np.ndarray,
    original_length: int | None = None,
    tag_data_gap: int = 1,
    data_padding: int = 0,
) -> bytes:
    """Decode data from an encoded image.

    Args:
        image: Numpy array of the encoded image.
        original_length: Optional original data length to truncate padding.
        tag_data_gap: Gap between tags and data.
        data_padding: Padding within data regions.

    Returns:
        Decoded bytes.
    """
    data_regions = get_data_regions(
        image.shape[1], image.shape[0], tag_data_gap, data_padding
    )

    pixel_list = []
    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                r, g, b = image[row, col]
                pixel_list.append((r, g, b))

    if original_length is not None:
        expected_pixels = ((original_length + 1) // 2) * 8
        pixel_list = pixel_list[:expected_pixels]

    decoded_bytes = []
    for i in range(0, len(pixel_list), 8):
        rgb_group = pixel_list[i : i + 8]
        while len(rgb_group) < 8:
            rgb_group.append((0, 0, 0))
        byte1, byte2 = decode_rgb_to_2bytes(rgb_group)
        decoded_bytes.extend([byte1, byte2])

    result = bytes(decoded_bytes)

    if original_length is not None:
        result = result[:original_length]

    return result
