#!/usr/bin/env python3
"""CLI script to decode image with AprilTags back to CSV data."""

import sys
import tempfile
from pathlib import Path

from src.decoder.data_unpacker import decode, write_csv
from src.decoder.image_processor import process_image_to_data


def decode_image_to_csv(
    image_path: str | Path,
    output_csv_path: str | Path | None = None,
    packed_file_path: str | Path | None = None,
) -> Path:
    """Decode image with AprilTags back to CSV data.

    Args:
        image_path: Path to input image file.
        output_csv_path: Optional path for output CSV. Defaults to image name with .csv extension.
        packed_file_path: Optional path for intermediate packed file. If None, uses a temporary file.

    Returns:
        Path to the created CSV file.
    """
    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    if output_csv_path is None:
        output_csv_path = image_path.with_suffix(".csv")
    else:
        output_csv_path = Path(output_csv_path)

    print(f"Processing image: {image_path}")

    decoded_bytes = process_image_to_data(image_path)

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
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} INPUT.png [OUTPUT.csv] [PACKED.packed]")
        sys.exit(1)

    image_path = sys.argv[1]
    output_csv_path = sys.argv[2] if len(sys.argv) >= 3 else None
    packed_file_path = sys.argv[3] if len(sys.argv) >= 4 else None

    try:
        decode_image_to_csv(image_path, output_csv_path, packed_file_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

