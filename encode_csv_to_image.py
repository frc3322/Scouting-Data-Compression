#!/usr/bin/env python3
"""CLI script to encode CSV data into an image with AprilTags."""

import sys
from pathlib import Path

import cv2

from src.common.data_regions import get_data_regions
from src.encoder.data_packer import clean_csv_newlines, encode, read_csv
from src.encoder.image_generator import (
    calculate_minimum_image_size,
    create_encoded_image,
)


def encode_csv_to_image(
    csv_path: str | Path,
    output_image_path: str | Path | None = None,
    packed_file_path: str | Path | None = None,
) -> Path:
    """Encode CSV data into an image with AprilTags.

    Args:
        csv_path: Path to input CSV file.
        output_image_path: Optional path for output image. Defaults to CSV name with .png extension.
        packed_file_path: Optional path for intermediate packed file. Defaults to CSV name with .packed extension.

    Returns:
        Path to the created image file.
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    if output_image_path is None:
        output_image_path = csv_path.with_suffix(".png")
    else:
        output_image_path = Path(output_image_path)

    if packed_file_path is None:
        packed_file_path = csv_path.with_suffix(".packed")
    else:
        packed_file_path = Path(packed_file_path)

    clean_csv_newlines(csv_path)

    headers, rows = read_csv(csv_path)

    encode(headers, rows, packed_file_path)

    packed_data = packed_file_path.read_bytes()
    print(f"Packed data size: {len(packed_data)} bytes")

    padding = 4
    tag_data_gap = 1
    data_padding = 4

    image_size = calculate_minimum_image_size(packed_data, tag_data_gap, data_padding)

    print(f"Auto-detected minimum image size: {image_size}x{image_size}")

    data_regions = get_data_regions(image_size, image_size, tag_data_gap, data_padding)
    total_pixels = sum(
        (row_slice.stop - row_slice.start) * (col_slice.stop - col_slice.start)
        for row_slice, col_slice in data_regions
    )
    max_bytes = (total_pixels // 8) * 2

    print(f"Available data pixels: {total_pixels}")
    print(
        f"Maximum data capacity: {max_bytes} bytes (2 bytes per 8 pixels using pure RGB colors)"
    )
    print(
        "Color encoding: Pure red (255,0,0), green (0,255,0), blue (0,0,255) for data"
    )
    print(
        f"Utilization: {len(packed_data)}/{max_bytes} bytes ({len(packed_data) / max_bytes * 100:.1f}%)"
    )

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
        raise

    cv2.imwrite(str(output_image_path), encoded_image)
    print(f"Encoded image saved to: {output_image_path}")

    from src.decoder.color_decoder import decode_image_data

    decoded_bytes = decode_image_data(
        encoded_image,
        len(packed_data),
        tag_data_gap=tag_data_gap,
        data_padding=data_padding,
    )
    print(f"Original data size: {len(packed_data)} bytes")
    print(f"Decoded data size:  {len(decoded_bytes)} bytes")
    print(f"Data matches: {packed_data == decoded_bytes}")

    if packed_data == decoded_bytes:
        print("SUCCESS: Round-trip encoding/decoding verified")
    else:
        print("WARNING: Round-trip encoding/decoding failed")
        print("First 20 bytes original:", packed_data[:20].hex())
        print("First 20 bytes decoded: ", decoded_bytes[:20].hex())

    return output_image_path


def main() -> None:
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} INPUT.csv [OUTPUT.png] [PACKED.packed]")
        sys.exit(1)

    csv_path = sys.argv[1]
    output_image_path = sys.argv[2] if len(sys.argv) >= 3 else None
    packed_file_path = sys.argv[3] if len(sys.argv) >= 4 else None

    try:
        encode_csv_to_image(csv_path, output_image_path, packed_file_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

