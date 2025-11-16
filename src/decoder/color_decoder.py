"""Color decoding utilities for extracting RGB values from images."""

import numpy as np
from ..common.constants import (
    DATA_COLOR_MAP,
    NON_WHITE_INDICES,
    NON_WHITE_PALETTE_FLOAT,
    PALETTE_COLORS,
    WHITE_INDEX,
    WHITE_MAX_CHANNEL_SPREAD,
    WHITE_MIN_CHANNEL,
)
from ..common.data_regions import get_data_regions


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
    white_mask = (min_channels >= WHITE_MIN_CHANNEL) & (
        channel_spread <= WHITE_MAX_CHANNEL_SPREAD
    )

    palette_indices = np.empty(pixel_array.shape[0], dtype=np.int32)
    palette_indices[white_mask] = WHITE_INDEX

    if np.any(~white_mask):
        residual_pixels = pixel_array[~white_mask].astype(np.float32, copy=False)
        distances = np.linalg.norm(
            residual_pixels[:, np.newaxis, :]
            - NON_WHITE_PALETTE_FLOAT[np.newaxis, :, :],
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

