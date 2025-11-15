#!/usr/bin/env python3
"""Script to encode packed scouting data into AprilTag tracking squares using BGR values."""

import cv2
import numpy as np
from generate_tracking_squares import generate_april_tags_image, get_data_regions
from pathlib import Path

DATA_COLOR_SEQUENCE: tuple[tuple[int, int, int], ...] = (
    (0, 0, 255),
    (0, 255, 0),
    (255, 0, 0),
    (0, 0, 0),
)

DATA_COLOR_MAP: dict[int, tuple[int, int, int]] = {
    index: color for index, color in enumerate(DATA_COLOR_SEQUENCE)
}

ALLOWED_COLOR_PALETTE: tuple[tuple[int, int, int], ...] = DATA_COLOR_SEQUENCE + (
    (255, 255, 255),
)


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


def create_encoded_image(
    data_bytes: bytes,
    image_width: int = 40,
    image_height: int = 40,
    padding: int = 4,
    tag_data_gap: int = 1,
    data_padding: int = 4,
) -> np.ndarray:
    """Create an image with AprilTags and encoded data in BGR regions.

    Args:
        data_bytes: Bytes to encode in the image.
        image_width: Width of the output image.
        image_height: Height of the output image.
        padding: Number of pixels to pad the tags from the image edges.
        tag_data_gap: Number of pixels gap between tags and data areas.
        data_padding: Number of pixels to pad the data areas from the image edges.

    Returns:
        Numpy array representing the encoded image.
    """
    # Generate base image with AprilTags
    image = generate_april_tags_image(
        image_width, image_height, padding, tag_data_gap, data_padding
    )

    # Get data regions
    data_regions = get_data_regions(
        image_width, image_height, padding, tag_data_gap, data_padding
    )

    # Encode bytes to BGR values (8 pixels per 2 bytes)
    encoded_colors = encode_bytes_to_rgb(data_bytes)

    # Flatten all data regions into a sequence of pixel coordinates
    pixel_coords = []
    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                pixel_coords.append((row, col))

    # Check if we have enough pixels for the data
    bytes_needed = len(data_bytes)
    pixels_needed = ((bytes_needed + 1) // 2) * 8  # Round up (8 pixels per 2 bytes)
    pixels_available = len(pixel_coords)

    if pixels_needed > pixels_available:
        raise ValueError(
            f"Not enough pixels to encode data: need {pixels_needed} pixels "
            f"for {bytes_needed} bytes, but only have {pixels_available} pixels available"
        )

    # Encode data into pixels (leave unfilled pixels as white)
    for i, (row, col) in enumerate(pixel_coords):
        if i < len(encoded_colors):
            image[row, col] = encoded_colors[i]
        # Else leave as white (255, 255, 255)

    return image


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
        combined_value |= (mapped_value << (index * 2))

    # Split back into 2 bytes
    byte1 = (combined_value >> 8) & 0xFF
    byte2 = combined_value & 0xFF

    return (byte1, byte2)


def decode_image_data(
    image: np.ndarray,
    original_length: int | None = None,
    padding: int = 4,
    tag_data_gap: int = 1,
    data_padding: int = 0
) -> bytes:
    """Decode data from an encoded image.

    Args:
        image: Numpy array of the encoded image.
        original_length: Optional original data length to truncate padding.
        padding: Padding around the grid.
        tag_data_gap: Gap between tags and data.
        data_padding: Padding within data regions.

    Returns:
        Decoded bytes.
    """
    # Get data regions (assuming same parameters as encoding)
    data_regions = get_data_regions(
        image.shape[1], image.shape[0], padding, tag_data_gap, data_padding
    )

    # Collect all pixels from data regions in the same order as encoding
    pixel_list = []
    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                r, g, b = image[row, col]
                pixel_list.append((r, g, b))

    # Calculate expected number of pixels used for data
    if original_length is not None:
        expected_pixels = ((original_length + 1) // 2) * 8
        # Take only the pixels that contain data
        pixel_list = pixel_list[:expected_pixels]

    # Decode in groups of 8 pixels (each group = 2 bytes)
    decoded_bytes = []
    for i in range(0, len(pixel_list), 8):
        rgb_group = pixel_list[i:i+8]
        # Pad with black if we don't have 8 pixels
        while len(rgb_group) < 8:
            rgb_group.append((0, 0, 0))
        byte1, byte2 = decode_rgb_to_2bytes(rgb_group)
        decoded_bytes.extend([byte1, byte2])

    result = bytes(decoded_bytes)

    # Truncate to original length if provided
    if original_length is not None:
        result = result[:original_length]

    return result


def calculate_minimum_image_size(
    data_bytes: bytes,
    padding: int = 4,
    tag_data_gap: int = 1,
    data_padding: int = 4,
    start_size: int = 20
) -> int:
    """Calculate the minimum square image size needed to fit all data.

    Args:
        data_bytes: Bytes to encode.
        padding: Number of pixels to pad the tags from the image edges.
        tag_data_gap: Number of pixels gap between tags and data areas.
        data_padding: Number of pixels to pad the data areas from the image edges.
        start_size: Starting image size to test from.

    Returns:
        Minimum square image size that can accommodate the data.
    """
    # Calculate pixels needed (8 pixels per 2 bytes)
    pixels_needed = ((len(data_bytes) + 1) // 2) * 8

    image_size = start_size
    while True:
        # Calculate available pixels for this size by flattening all data regions (includes center)
        data_regions = get_data_regions(
            image_size, image_size, padding, tag_data_gap, data_padding
        )
        pixel_coords: list[tuple[int, int]] = []
        for row_slice, col_slice in data_regions:
            for row in range(row_slice.start, row_slice.stop):
                for col in range(col_slice.start, col_slice.stop):
                    pixel_coords.append((row, col))

        if len(pixel_coords) >= pixels_needed:
            return image_size

        image_size += 2  # Increment by 2 to avoid odd sizes

        # Safety check to prevent infinite loop
        if image_size > 1000:
            raise ValueError(f"Cannot find suitable image size for {len(data_bytes)} bytes of data")


def main():
    """Main function to encode packed scouting data into an image."""
    # Load packed data
    packed_file = Path("MatchData.packed")

    if not packed_file.exists():
        print(f"Packed data file not found: {packed_file}")
        return

    print(f"Loading packed data from: {packed_file}")

    # Read the packed data as raw bytes
    packed_data = packed_file.read_bytes()
    print(f"Packed data size: {len(packed_data)} bytes")

    # Parameters (can be made configurable)
    padding = 4
    tag_data_gap = 1
    data_padding = 4

    # Auto-detect minimum image size needed
    image_size = calculate_minimum_image_size(
        packed_data, padding, tag_data_gap, data_padding
    )

    print(f"Auto-detected minimum image size: {image_size}x{image_size}")

    # Calculate available pixels
    data_regions = get_data_regions(
        image_size, image_size, padding, tag_data_gap, data_padding
    )
    total_pixels = sum(
        (row_slice.stop - row_slice.start) * (col_slice.stop - col_slice.start)
        for row_slice, col_slice in data_regions
    )
    max_bytes = (total_pixels // 8) * 2  # 8 pixels per 2 bytes

    print(f"Available data pixels: {total_pixels}")
    print(
        f"Maximum data capacity: {max_bytes} bytes (2 bytes per 8 pixels using pure RGB colors)"
    )
    print(
        "Color encoding: Pure red (255,0,0), green (0,255,0), blue (0,0,255) for data"
    )
    print(
        f"Utilization: {len(packed_data)}/{max_bytes} bytes ({len(packed_data)/max_bytes*100:.1f}%)"
    )

    # Create encoded image
    try:
        encoded_image = create_encoded_image(
            packed_data,
            image_size,
            image_size,
            padding,
            tag_data_gap,
            data_padding,
        )
    except ValueError as e:
        print(f"Error: {e}")
        print("Consider increasing image size or reducing data size")
        return

    # Save the image
    output_filename = "encoded_scouting_data.png"
    cv2.imwrite(output_filename, encoded_image)
    print(f"Encoded image saved to {output_filename}")

    # Test decoding
    decoded_bytes = decode_image_data(
        encoded_image,
        len(packed_data),
        padding=padding,
        tag_data_gap=tag_data_gap,
        data_padding=data_padding,
    )
    print(f"Original data size: {len(packed_data)} bytes")
    print(f"Decoded data size:  {len(decoded_bytes)} bytes")
    print(f"Data matches: {packed_data == decoded_bytes}")

    # Verify the decoded data can still be unpacked
    if packed_data == decoded_bytes:
        print("SUCCESS: Round-trip encoding/decoding successful")

        # Test that the decoded data can be unpacked back to CSV
        try:
            from pack_data import decode as unpack_data

            _, rows = unpack_data(packed_file)
            print(
                f"SUCCESS: Original packed data contains {len(rows)} rows of scouting data"
            )
        except Exception as e:
            print(f"Warning: Could not verify unpacked data: {e}")
    else:
        print("FAILED: Round-trip encoding/decoding failed")
        print("First 20 bytes original:", packed_data[:20].hex())
        print("First 20 bytes decoded: ", decoded_bytes[:20].hex())

        # Find first mismatch
        for i, (orig, dec) in enumerate(zip(packed_data, decoded_bytes)):
            if orig != dec:
                print(f"First mismatch at byte {i}: {orig} vs {dec}")
                break

        # Try to decode the corrupted data to see if it's still valid
        try:
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".packed"
            ) as tmp_file:
                tmp_file.write(decoded_bytes)
                tmp_file_path = Path(tmp_file.name)

            try:
                from pack_data import decode as unpack_data

                _, rows = unpack_data(tmp_file_path)
                print(
                    f"Warning: Decoded data is still valid and contains {len(rows)} rows"
                )
            except Exception as e2:
                print(f"Decoded data is corrupted: {e2}")
            finally:
                os.unlink(tmp_file_path)
        except Exception as e3:
            print(f"Could not test decoded data validity: {e3}")


if __name__ == "__main__":
    main()