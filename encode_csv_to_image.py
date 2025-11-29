#!/usr/bin/env python3
"""CLI script to encode CSV data into an image with AprilTags."""

import argparse
import sys
from pathlib import Path

import cv2

from src.common.data_regions import get_data_regions
from src.common.schema import SchemaLoader
from src.common.color_palette import (
    load_color_palette,
    usable_color_set,
    palette_to_bgr,
)
from src.encoder.data_packer import clean_csv_newlines, encode, read_csv
from src.encoder.image_generator import (
    calculate_minimum_image_size,
    create_encoded_image,
)


def encode_csv_to_image(
    csv_path: str | Path,
    output_image_path: str | Path | None = None,
    packed_file_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    palette_path: str | Path | None = None,
) -> Path:
    """Encode CSV data into an image with AprilTags.

    Args:
        csv_path: Path to input CSV file.
        output_image_path: Optional path for output image. Defaults to CSV name with .png extension.
        packed_file_path: Optional path for intermediate packed file. Defaults to CSV name with .packed extension.
        schema_path: Optional path to schema file (JSON or Python). If None, uses default schema.
        palette_path: Optional path to color palette JSON file. Defaults to src/common/color_palette.json.

    Returns:
        Path to the created image file.
    """
    csv_path = Path(csv_path)

    if palette_path is None:
        palette_path = Path(__file__).parent / "src" / "common" / "color_palette.json"
    else:
        palette_path = Path(palette_path)

    try:
        palette_rgb = load_color_palette(palette_path)
        usable_palette_rgb = usable_color_set(palette_rgb)
        palette_bgr = palette_to_bgr(usable_palette_rgb)
        print(f"Loaded palette with {len(usable_palette_rgb)} colors (from {len(palette_rgb)} total)")
    except FileNotFoundError:
        print(f"Warning: Palette file not found at {palette_path}, using default 4-color palette")
        from src.common.constants import DATA_COLOR_SEQUENCE
        palette_bgr = palette_to_bgr(list(DATA_COLOR_SEQUENCE))

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

    schema = None
    if schema_path is not None:
        schema = SchemaLoader.load_schema(Path(schema_path))

    clean_csv_newlines(csv_path)

    headers, rows = read_csv(csv_path)

    encode(headers, rows, packed_file_path, schema=schema)

    packed_data = packed_file_path.read_bytes()
    print(f"Packed data size: {len(packed_data)} bytes")

    padding = 4
    tag_data_gap = 1
    data_padding = 4

    image_size = calculate_minimum_image_size(
        packed_data, tag_data_gap, data_padding, palette_bgr=palette_bgr
    )

    print(f"Auto-detected minimum image size: {image_size}x{image_size}")

    import math
    from src.common.color_palette import calculate_bits_per_pixel

    data_regions = get_data_regions(image_size, image_size, tag_data_gap, data_padding)
    total_pixels = sum(
        (row_slice.stop - row_slice.start) * (col_slice.stop - col_slice.start)
        for row_slice, col_slice in data_regions
    )
    bits_per_pixel = calculate_bits_per_pixel(len(palette_bgr))
    pixels_per_byte = math.ceil(8 / bits_per_pixel)
    num_calibration_colors = len(palette_bgr)
    max_data_pixels = total_pixels - num_calibration_colors
    
    if 16 % bits_per_pixel == 0:
        pixels_per_2bytes = 16 // bits_per_pixel
        max_bytes = (max_data_pixels // pixels_per_2bytes) * 2
        encoding_info = f"{pixels_per_2bytes} pixels per 2 bytes"
    else:
        max_bytes = max_data_pixels // pixels_per_byte
        encoding_info = f"{pixels_per_byte} pixels per byte"

    print(f"Available data pixels: {total_pixels} (minus {num_calibration_colors} for calibration)")
    print(
        f"Maximum data capacity: {max_bytes} bytes ({bits_per_pixel} bits per pixel, {encoding_info})"
    )
    print(f"Color palette: {len(palette_bgr)} colors")
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
            palette_bgr=palette_bgr,
        )
    except ValueError as e:
        print(f"Error: {e}")
        print("Consider increasing image size or reducing data size")
        raise

    cv2.imwrite(str(output_image_path), encoded_image)
    print(f"Encoded image saved to: {output_image_path}")

    from src.decoder.color_decoder import decode_image_data

    num_calibration_colors = min(len(palette_bgr), 6)
    decoded_bytes = decode_image_data(
        encoded_image,
        len(packed_data),
        tag_data_gap=tag_data_gap,
        data_padding=data_padding,
        palette_bgr=palette_bgr,
        num_calibration_pixels=num_calibration_colors,
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
    parser = argparse.ArgumentParser(
        description="Encode CSV data into an image with AprilTags."
    )
    parser.add_argument("csv_path", help="Path to input CSV file")
    parser.add_argument(
        "output_image_path",
        nargs="?",
        help="Optional path for output image (defaults to CSV name with .png extension)",
    )
    parser.add_argument(
        "packed_file_path",
        nargs="?",
        help="Optional path for intermediate packed file (defaults to CSV name with .packed extension)",
    )
    parser.add_argument(
        "--schema",
        dest="schema_path",
        help="Path to schema file (JSON or Python). If not provided, uses default schema.",
    )
    
    parser.add_argument(
        "--palette",
        type=str,
        help="Path to color palette JSON file (defaults to src/common/color_palette.json)",
    )

    args = parser.parse_args()

    try:
        encode_csv_to_image(
            args.csv_path,
            args.output_image_path,
            args.packed_file_path,
            schema_path=args.schema_path,
            palette_path=args.palette,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

