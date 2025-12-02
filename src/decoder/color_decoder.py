"""Color decoding utilities for extracting RGB values from images."""

import numpy as np
from ..common.data_regions import get_data_regions  # type: ignore
from ..common.color_palette import calculate_bits_per_pixel  # type: ignore


def assign_palette_indices(
    pixel_values: np.ndarray,
    corrected_palette_bgr: list[tuple[int, int, int]],
) -> np.ndarray:
    """Assign each pixel in the array to the closest palette index using corrected colors.

    Args:
        pixel_values: Array of pixel colors shaped (N, 3) or (3,).
        corrected_palette_bgr: List of corrected BGR tuples representing the palette colors.

    Returns:
        Array of palette indices that best match each pixel.
    """
    pixel_array = np.atleast_2d(pixel_values).astype(np.float32, copy=False)
    np.clip(pixel_array, 0.0, 255.0, out=pixel_array)

    corrected_palette_array = np.array(corrected_palette_bgr, dtype=np.float32)

    color_distances = np.linalg.norm(
        pixel_array[:, np.newaxis, :] - corrected_palette_array[np.newaxis, :, :],
        axis=2,
    )
    nearest_palette_indices = np.argmin(color_distances, axis=1).astype(np.int32)

    return nearest_palette_indices


def map_to_palette(
    cell: np.ndarray,
    corrected_palette_bgr: list[tuple[int, int, int]],
    original_palette_bgr: list[tuple[int, int, int]],
) -> tuple[int, int, int]:
    """Map an image cell to the nearest palette entry. Sees what palette color is most common in the cell.

    Args:
        cell: Image cell as numpy array.
        corrected_palette_bgr: List of corrected BGR tuples from calibration.
        original_palette_bgr: List of original BGR tuples for the palette.

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
    palette_indices = assign_palette_indices(pixel_values, corrected_palette_bgr)

    # count the number of pixels for each palette index
    counts = np.bincount(palette_indices, minlength=len(original_palette_bgr))

    # get the palette index with the highest count
    majority_palette_idx = int(np.argmax(counts))

    # get the color for the majority palette index from original palette
    majority_color = original_palette_bgr[majority_palette_idx]
    return majority_color


def decode_rgb_to_byte(
    rgb_list: list[tuple[int, int, int]], palette_bgr: list[tuple[int, int, int]]
) -> int:
    """Decode a list of BGR values back to a single byte using dynamic palette.

    Args:
        rgb_list: List of BGR tuples (number depends on bits per pixel).
        palette_bgr: List of BGR tuples representing the color palette.

    Returns:
        Decoded byte value.
    """
    import math

    bits_per_pixel = calculate_bits_per_pixel(len(palette_bgr))
    pixels_per_byte = math.ceil(8 / bits_per_pixel)

    if len(rgb_list) < pixels_per_byte:
        rgb_list.extend([palette_bgr[0]] * (pixels_per_byte - len(rgb_list)))

    color_to_index: dict[tuple[int, int, int], int] = {
        color: idx for idx, color in enumerate(palette_bgr)
    }

    byte_value = 0
    for index, rgb in enumerate(rgb_list[:pixels_per_byte]):
        bit_offset = index * bits_per_pixel
        if bit_offset < 8:
            color_index = color_to_index.get(rgb, 0)
            byte_value |= color_index << bit_offset

    return byte_value


def decode_rgb_to_2bytes(
    rgb_list: list[tuple[int, int, int]], palette_bgr: list[tuple[int, int, int]]
) -> tuple[int, int]:
    """Decode a list of BGR values back to 2 bytes using dynamic palette.

    Args:
        rgb_list: List of BGR tuples (number depends on bits per pixel).
        palette_bgr: List of BGR tuples representing the color palette.

    Returns:
        Tuple of (byte1, byte2).
    """
    bits_per_pixel = calculate_bits_per_pixel(len(palette_bgr))

    if 16 % bits_per_pixel == 0:
        pixels_per_2bytes = 16 // bits_per_pixel

        if len(rgb_list) < pixels_per_2bytes:
            rgb_list.extend([palette_bgr[0]] * (pixels_per_2bytes - len(rgb_list)))

        color_to_index: dict[tuple[int, int, int], int] = {
            color: idx for idx, color in enumerate(palette_bgr)
        }

        combined_value = 0
        for index, rgb in enumerate(rgb_list[:pixels_per_2bytes]):
            color_index = color_to_index.get(rgb, 0)
            combined_value |= color_index << (index * bits_per_pixel)

        byte1 = (combined_value >> 8) & 0xFF
        byte2 = combined_value & 0xFF

        return (byte1, byte2)
    else:
        pixels_per_byte = 8 // bits_per_pixel
        byte1 = decode_rgb_to_byte(rgb_list[:pixels_per_byte], palette_bgr)
        byte2 = decode_rgb_to_byte(rgb_list[pixels_per_byte:], palette_bgr)
        return (byte1, byte2)


def decode_image_data(
    image: np.ndarray,
    original_length: int | None = None,
    tag_data_gap: int = 1,
    data_padding: int = 0,
    palette_bgr: list[tuple[int, int, int]] | None = None,
    num_calibration_pixels: int = 6,
) -> bytes:
    """Decode data from an encoded image.

    Args:
        image: Numpy array of the encoded image.
        original_length: Optional original data length to truncate padding.
        tag_data_gap: Gap between tags and data.
        data_padding: Padding within data regions.
        palette_bgr: Optional list of BGR tuples for color palette. If None, uses default 4-color palette.
        num_calibration_pixels: Number of calibration pixels at the end of data.

    Returns:
        Decoded bytes.
    """
    if palette_bgr is None:
        from ..common.constants import DATA_COLOR_SEQUENCE  # type: ignore
        from ..common.color_palette import palette_to_bgr  # type: ignore

        palette_bgr = palette_to_bgr(list(DATA_COLOR_SEQUENCE))

    import math

    bits_per_pixel = calculate_bits_per_pixel(len(palette_bgr))
    pixels_per_byte = math.ceil(8 / bits_per_pixel)

    if 16 % bits_per_pixel == 0:
        pixels_per_2bytes = 16 // bits_per_pixel
        encode_by_2bytes = True
    else:
        encode_by_2bytes = False
        pixels_per_2bytes = pixels_per_byte * 2

    data_regions = get_data_regions(
        image.shape[1], image.shape[0], tag_data_gap, data_padding
    )

    pixel_list = []
    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                r, g, b = image[row, col]
                pixel_list.append((r, g, b))

    # Remove calibration pixels from the end
    if len(pixel_list) >= num_calibration_pixels:
        pixel_list = pixel_list[:-num_calibration_pixels]

    if original_length is not None:
        if encode_by_2bytes:
            expected_pixels = ((original_length + 1) // 2) * pixels_per_2bytes
        else:
            expected_pixels = original_length * pixels_per_byte
        pixel_list = pixel_list[:expected_pixels]

    decoded_bytes = []
    if encode_by_2bytes:
        for i in range(0, len(pixel_list), pixels_per_2bytes):
            rgb_group = pixel_list[i : i + pixels_per_2bytes]
            while len(rgb_group) < pixels_per_2bytes:
                rgb_group.append(palette_bgr[0])
            byte1, byte2 = decode_rgb_to_2bytes(rgb_group, palette_bgr)
            decoded_bytes.extend([byte1, byte2])
    else:
        for i in range(0, len(pixel_list), pixels_per_byte):
            rgb_group = pixel_list[i : i + pixels_per_byte]
            while len(rgb_group) < pixels_per_byte:
                rgb_group.append(palette_bgr[0])
            byte_val = decode_rgb_to_byte(rgb_group, palette_bgr)
            decoded_bytes.append(byte_val)

    result = bytes(decoded_bytes)

    if original_length is not None:
        result = result[:original_length]

    return result
