"""Color encoding utilities for converting bytes to RGB values."""

from ..common.constants import DATA_COLOR_MAP


def encode_2bytes_to_rgb(byte1: int, byte2: int) -> list[tuple[int, int, int]]:
    """Encode 2 bytes to a list of BGR values using pure colors.

    Args:
        byte1: First byte (0-255).
        byte2: Second byte (0-255).

    Returns:
        List of 8 BGR tuples containing red, green, blue, or black.
    """
    combined_value = (byte1 << 8) | byte2

    rgb_list = []
    for bit_index in range(8):
        bit_pair = (combined_value >> (bit_index * 2)) & 0x3
        rgb_list.append(DATA_COLOR_MAP[bit_pair])

    return rgb_list


def encode_bytes_to_rgb(data_bytes: bytes) -> list[tuple[int, int, int]]:
    """Encode bytes into a list of BGR tuples (8 tuples per 2 bytes).

    Args:
        data_bytes: Bytes to encode.

    Returns:
        List of BGR tuples, 8 tuples per 2 bytes.
    """
    rgb_list = []
    for i in range(0, len(data_bytes), 2):
        byte1 = data_bytes[i]
        byte2 = data_bytes[i + 1] if i + 1 < len(data_bytes) else 0
        rgb_list.extend(encode_2bytes_to_rgb(byte1, byte2))
    return rgb_list

