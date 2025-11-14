#!/usr/bin/env python3
"""Script to encode packed scouting data into AprilTag tracking squares using RGB values."""

import cv2
import numpy as np
from generate_tracking_squares import generate_april_tags_image, get_data_regions
from pathlib import Path


def encode_2bytes_to_rgb(byte1: int, byte2: int, step_size: int = 2) -> tuple[int, int, int]:
    """Encode 2 bytes to RGB values using step-based encoding.

    Args:
        byte1: First byte (0-255).
        byte2: Second byte (0-255).
        step_size: Step size for RGB values (default 2 for 122 steps).

    Returns:
        Tuple of (R, G, B) values.
    """
    # Combine 2 bytes into a single value (0-65535)
    combined_value = (byte1 << 8) | byte2

    # Use 122 steps (0-121), multiply by step_size to get 0-242
    max_steps = 122

    # Encode into RGB using base-122 representation
    r_step = combined_value % max_steps
    r = r_step * step_size

    g_step = (combined_value // max_steps) % max_steps
    g = g_step * step_size

    b_step = (combined_value // (max_steps * max_steps)) % max_steps
    b = b_step * step_size

    return (r, g, b)


def encode_bytes_to_rgb(data_bytes: bytes, step_size: int = 2) -> list[tuple[int, int, int]]:
    """Encode bytes into a list of RGB tuples (2 bytes per pixel).

    Args:
        data_bytes: Bytes to encode.
        step_size: Step size for RGB values.

    Returns:
        List of RGB tuples, one tuple per 2 bytes.
    """
    rgb_list = []
    for i in range(0, len(data_bytes), 2):
        byte1 = data_bytes[i]
        byte2 = data_bytes[i + 1] if i + 1 < len(data_bytes) else 0
        rgb_list.append(encode_2bytes_to_rgb(byte1, byte2, step_size))
    return rgb_list


def create_encoded_image(
    data_bytes: bytes,
    image_width: int = 40,
    image_height: int = 40,
    padding: int = 4,
    tag_data_gap: int = 1,
    data_padding: int = 4,
    step_size: int = 2,
) -> np.ndarray:
    """Create an image with AprilTags and encoded data in RGB regions.

    Args:
        data_bytes: Bytes to encode in the image.
        image_width: Width of the output image.
        image_height: Height of the output image.
        padding: Number of pixels to pad the tags from the image edges.
        tag_data_gap: Number of pixels gap between tags and data areas.
        data_padding: Number of pixels to pad the data areas from the image edges.
        step_size: Step size for RGB encoding.

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

    # Encode bytes to RGB values (2 bytes per pixel)
    encoded_colors = encode_bytes_to_rgb(data_bytes, step_size)

    # Flatten all data regions into a sequence of pixel coordinates
    pixel_coords = []
    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                pixel_coords.append((row, col))

    # Check if we have enough pixels for the data
    bytes_needed = len(data_bytes)
    pixels_needed = (bytes_needed + 1) // 2  # Round up (2 bytes per pixel)
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


def decode_rgb_to_2bytes(r: int, g: int, b: int, step_size: int = 2) -> tuple[int, int]:
    """Decode RGB values back to 2 bytes.

    Args:
        r: Red value.
        g: Green value.
        b: Blue value.
        step_size: Step size used for encoding.

    Returns:
        Tuple of (byte1, byte2).
    """
    max_steps = 122

    # Reverse the encoding
    r_step = round(r / step_size)
    g_step = round(g / step_size)
    b_step = round(b / step_size)

    # Reconstruct combined value
    combined_value = r_step + (g_step * max_steps) + (b_step * max_steps * max_steps)

    # Split back into 2 bytes
    byte1 = (combined_value >> 8) & 0xFF
    byte2 = combined_value & 0xFF

    return (byte1, byte2)


def decode_image_data(
    image: np.ndarray, original_length: int | None = None, step_size: int = 2
) -> bytes:
    """Decode data from an encoded image.

    Args:
        image: Numpy array of the encoded image.
        original_length: Optional original data length to truncate padding.
        step_size: Step size used for encoding.

    Returns:
        Decoded bytes.
    """
    # Get data regions (assuming same parameters as encoding)
    data_regions = get_data_regions(
        image.shape[1], image.shape[0], padding=4, tag_data_gap=1, data_padding=4
    )

    # Collect non-white pixels from data regions
    decoded_bytes = []
    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                r, g, b = image[row, col]
                # Skip white pixels (255, 255, 255)
                if not (r == 255 and g == 255 and b == 255):
                    byte1, byte2 = decode_rgb_to_2bytes(r, g, b, step_size)
                    decoded_bytes.extend([byte1, byte2])

    result = bytes(decoded_bytes)

    # Truncate to original length if provided
    if original_length is not None:
        result = result[:original_length]

    return result


def main():
    """Main function to encode packed scouting data into an image."""
    # Load packed data
    packed_file = Path("/Users/darkeden/Scouting-Data-Compression/MatchData.packed")

    if not packed_file.exists():
        print(f"Packed data file not found: {packed_file}")
        return

    print(f"Loading packed data from: {packed_file}")

    # Read the packed data as raw bytes
    packed_data = packed_file.read_bytes()
    print(f"Packed data size: {len(packed_data)} bytes")

    # Parameters (can be made configurable)
    image_width = 35
    image_height = 35
    padding = 4
    tag_data_gap = 1
    data_padding = 4
    step_size = 2

    # Calculate available pixels
    data_regions = get_data_regions(
        image_width, image_height, padding, tag_data_gap, data_padding
    )
    total_pixels = sum(
        (row_slice.stop - row_slice.start) * (col_slice.stop - col_slice.start)
        for row_slice, col_slice in data_regions
    )
    max_bytes = total_pixels * 2  # 2 bytes per pixel

    print(f"Available data pixels: {total_pixels}")
    print(
        f"Maximum data capacity: {max_bytes} bytes (2 bytes per pixel with step_size={step_size})"
    )
    print(
        f"Utilization: {len(packed_data)}/{max_bytes} bytes ({len(packed_data)/max_bytes*100:.1f}%)"
    )

    # Create encoded image
    try:
        encoded_image = create_encoded_image(
            packed_data,
            image_width,
            image_height,
            padding,
            tag_data_gap,
            data_padding,
            step_size,
        )
    except ValueError as e:
        print(f"Error: {e}")
        print(f"Consider increasing image size or reducing data size")
        return

    # Save the image
    output_filename = "encoded_scouting_data.png"
    cv2.imwrite(output_filename, encoded_image)
    print(f"Encoded image saved to {output_filename}")

    # Test decoding
    decoded_bytes = decode_image_data(encoded_image, len(packed_data), step_size)
    print(f"Original data size: {len(packed_data)} bytes")
    print(f"Decoded data size:  {len(decoded_bytes)} bytes")
    print(f"Data matches: {packed_data == decoded_bytes}")

    # Verify the decoded data can still be unpacked
    if packed_data == decoded_bytes:
        print("✓ Round-trip encoding/decoding successful")

        # Test that the decoded data can be unpacked back to CSV
        try:
            from pack_data import decode as unpack_data

            _, rows = unpack_data(packed_file)
            print(
                f"✓ Original packed data contains {len(rows)} rows of scouting data"
            )
        except Exception as e:
            print(f"Warning: Could not verify unpacked data: {e}")
    else:
        print("✗ Round-trip encoding/decoding failed")
        print("First 20 bytes original:", packed_data[:20].hex())
        print("First 20 bytes decoded: ", decoded_bytes[:20].hex())

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