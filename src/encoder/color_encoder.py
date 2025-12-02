"""Color encoding utilities for converting bytes to RGB values."""

from ..common.color_palette import calculate_bits_per_pixel  # type: ignore


def encode_byte_to_rgb(
    byte_val: int, palette_bgr: list[tuple[int, int, int]]
) -> list[tuple[int, int, int]]:
    """Encode a single byte to a list of BGR values using dynamic palette.

    Args:
        byte_val: Byte value (0-255).
        palette_bgr: List of BGR tuples representing the color palette.

    Returns:
        List of BGR tuples. Number depends on bits per pixel.
    """
    import math

    num_colors = len(palette_bgr)
    bits_per_pixel = calculate_bits_per_pixel(num_colors)
    pixels_per_byte = math.ceil(8 / bits_per_pixel)

    rgb_list = []
    for pixel_idx in range(pixels_per_byte):
        bit_offset = pixel_idx * bits_per_pixel
        if bit_offset < 8:
            color_index = (byte_val >> bit_offset) & ((1 << bits_per_pixel) - 1)
            rgb_list.append(palette_bgr[color_index])
        else:
            rgb_list.append(palette_bgr[0])

    return rgb_list


def encode_2bytes_to_rgb(
    byte1: int, byte2: int, palette_bgr: list[tuple[int, int, int]]
) -> list[tuple[int, int, int]]:
    """Encode 2 bytes to a list of BGR values using dynamic palette.

    Args:
        byte1: First byte (0-255).
        byte2: Second byte (0-255).
        palette_bgr: List of BGR tuples representing the color palette.

    Returns:
        List of BGR tuples. Number depends on bits per pixel.
    """
    num_colors = len(palette_bgr)
    bits_per_pixel = calculate_bits_per_pixel(num_colors)

    if 16 % bits_per_pixel == 0:
        combined_bits = 16
        pixels_per_2bytes = combined_bits // bits_per_pixel
        combined_value = (byte1 << 8) | byte2

        rgb_list = []
        for pixel_idx in range(pixels_per_2bytes):
            bit_offset = pixel_idx * bits_per_pixel
            color_index = (combined_value >> bit_offset) & ((1 << bits_per_pixel) - 1)
            rgb_list.append(palette_bgr[color_index])
        return rgb_list
    else:
        rgb_list = encode_byte_to_rgb(byte1, palette_bgr)
        rgb_list.extend(encode_byte_to_rgb(byte2, palette_bgr))
        return rgb_list


def encode_bytes_to_rgb(
    data_bytes: bytes, palette_bgr: list[tuple[int, int, int]]
) -> list[tuple[int, int, int]]:
    """Encode bytes into a list of BGR tuples using dynamic palette.

    Args:
        data_bytes: Bytes to encode.
        palette_bgr: List of BGR tuples representing the color palette.

    Returns:
        List of BGR tuples. Number depends on bits per pixel.
    """
    num_colors = len(palette_bgr)
    bits_per_pixel = calculate_bits_per_pixel(num_colors)

    rgb_list = []
    if 8 % bits_per_pixel == 0:
        for i in range(0, len(data_bytes), 2):
            byte1 = data_bytes[i]
            byte2 = data_bytes[i + 1] if i + 1 < len(data_bytes) else 0
            rgb_list.extend(encode_2bytes_to_rgb(byte1, byte2, palette_bgr))
    else:
        for byte_val in data_bytes:
            rgb_list.extend(encode_byte_to_rgb(byte_val, palette_bgr))
    return rgb_list
