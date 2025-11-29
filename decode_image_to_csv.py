#!/usr/bin/env python3
"""CLI script to decode image with AprilTags back to CSV data."""

import sys
import tempfile
from pathlib import Path
import traceback
import argparse

from src.common.color_palette import (
    load_color_palette,
    usable_color_set,
    palette_to_bgr,
)
from src.decoder.data_unpacker import decode, write_csv
from src.decoder.image_processor import process_image_to_data


def decode_image_to_csv(
    image_path: str | Path,
    output_csv_path: str | Path | None = None,
    packed_file_path: str | Path | None = None,
    debug: bool = False,
    palette_path: str | Path | None = None,
) -> Path:
    """Decode image with AprilTags back to CSV data.

    Args:
        image_path: Path to input image file.
        output_csv_path: Optional path for output CSV. Defaults to image name with .csv extension.
        packed_file_path: Optional path for intermediate packed file. If None, uses a temporary file.
        debug: If True, save intermediate images during processing.
        palette_path: Optional path to color palette JSON file. Defaults to src/common/color_palette.json.

    Returns:
        Path to the created CSV file.
    """
    image_path = Path(image_path)

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

    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    if output_csv_path is None:
        output_csv_path = image_path.with_suffix(".csv")
    else:
        output_csv_path = Path(output_csv_path)

    print(f"Processing image: {image_path}")

    decoded_bytes = process_image_to_data(image_path, debug=debug, palette_bgr=palette_bgr)

    if decoded_bytes is None:
        raise ValueError("Failed to detect AprilTags or extract data from image")

    print(f"Extracted {len(decoded_bytes)} bytes from image")

    if packed_file_path is None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".packed") as tmp:
            packed_file_path = Path(tmp.name)

    packed_file_path = Path(packed_file_path)
    packed_file_path.write_bytes(decoded_bytes)

    print(f"Wrote packed data to: {packed_file_path}")

    try:
        headers, rows = decode(packed_file_path)
        print(f"Decoded {len(rows)} rows with {len(headers)} columns")
    except Exception as e:
        print(f"Error decoding packed data: {e}")
        raise

    write_csv(headers, rows, output_csv_path)
    print(f"CSV data saved to: {output_csv_path}")

    temp_dir = Path(tempfile.gettempdir())
    if packed_file_path.parent == temp_dir:
        packed_file_path.unlink()

    return output_csv_path


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Decode image with AprilTags back to CSV data."
    )
    parser.add_argument("input_image", help="Path to input image file")
    parser.add_argument(
        "output_csv",
        nargs="?",
        help="Optional path for output CSV (defaults to input image name with .csv extension)"
    )
    parser.add_argument(
        "packed_file",
        nargs="?",
        help="Optional path for intermediate packed file"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save intermediate images during processing"
    )
    parser.add_argument(
        "--palette",
        type=str,
        help="Path to color palette JSON file (defaults to src/common/color_palette.json)",
    )

    args = parser.parse_args()

    try:
        decode_image_to_csv(
            args.input_image,
            args.output_csv,
            args.packed_file,
            debug=args.debug,
            palette_path=args.palette,
        )
    except Exception:
        print(f"Error: {traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

