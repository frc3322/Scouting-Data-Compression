# QR Code Testing - Usage Guide

This project provides tools for encoding CSV data into images using AprilTags and decoding images back to CSV data. This is useful for storing structured data in a visual format that can be captured by cameras.

## Dependencies

Install the required dependencies using pip:

```bash
pip install opencv-python numpy pupil-apriltags zstandard
```

Or if using uv (recommended):

```bash
uv pip install opencv-python numpy pupil-apriltags zstandard
```

## Scripts Overview

### `encode_csv_to_image.py`
Encodes CSV data into an image embedded with AprilTags for data storage.

### `decode_image_to_csv.py`
Decodes images containing AprilTags back into CSV data.

### `camera_decoder.py`
Interactive camera application for real-time decoding of AprilTag-encoded data.

## Command Line Usage

### Encoding CSV to Image

```bash
python encode_csv_to_image.py INPUT.csv [OUTPUT.png] [PACKED.packed]
```

**Parameters:**
- `INPUT.csv`: Path to the input CSV file (required)
- `OUTPUT.png`: Path for the output image file (optional, defaults to `INPUT.png`)
- `PACKED.packed`: Path for the intermediate packed data file (optional, defaults to `INPUT.packed`)

**Example:**
```bash
# Basic usage - creates data.csv.png and data.packed
python encode_csv_to_image.py data.csv

# Specify custom output names
python encode_csv_to_image.py input.csv output.png packed_data.packed

# Using uv
uv run python encode_csv_to_image.py data.csv
```

### Decoding Image to CSV

```bash
python decode_image_to_csv.py INPUT.png [OUTPUT.csv] [PACKED.packed]
```

**Parameters:**
- `INPUT.png`: Path to the input image file (required)
- `OUTPUT.csv`: Path for the output CSV file (optional, defaults to `INPUT.csv`)
- `PACKED.packed`: Path for the intermediate packed data file (optional, uses temporary file)

**Example:**
```bash
# Basic usage - creates image.png.csv
python decode_image_to_csv.py image.png

# Specify custom output names
python decode_image_to_csv.py input.png output.csv packed_data.packed

# Using uv
uv run python decode_image_to_csv.py image.png
```

### Camera-Based Decoding

```bash
python camera_decoder.py
```

**Features:**
- Opens camera feed in a window
- Press SPACE to capture current frame and attempt decoding
- Press ESC to exit the application
- Plays success sound (high beep) when decoding succeeds
- Plays failure sound (low beep) when decoding fails
- Saves decoded CSV files to `decoded_csvs/` folder with timestamped names (format: decoded_YYYYMMDD_HHMMSS.csv)

**Example:**
```bash
# Run the camera decoder
python camera_decoder.py

# Using uv
uv run python camera_decoder.py
```

## Programmatic Usage

You can also import and use these functions directly in your Python scripts.

### Encoding CSV to Image

```python
from pathlib import Path
from encode_csv_to_image import encode_csv_to_image

# Basic usage
output_path = encode_csv_to_image("data.csv")
print(f"Encoded image saved to: {output_path}")

# With custom output paths
output_path = encode_csv_to_image(
    csv_path="input.csv",
    output_image_path="custom_output.png",
    packed_file_path="intermediate.packed"
)
```

### Decoding Image to CSV

```python
from pathlib import Path
from decode_image_to_csv import decode_image_to_csv

# Basic usage
output_path = decode_image_to_csv("image.png")
print(f"Decoded CSV saved to: {output_path}")

# With custom output paths
output_path = decode_image_to_csv(
    image_path="input.png",
    output_csv_path="output.csv",
    packed_file_path="intermediate.packed"
)
```

## Function Signatures

### `encode_csv_to_image()`

```python
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
```

### `decode_image_to_csv()`

```python
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
```

## Data Flow

1. **Encoding Process:**
   - CSV data is read and compressed using zstandard
   - Compressed data is packed into a binary format
   - Binary data is encoded into color pixels (RGB values)
   - Pixels are arranged in regions within an image alongside AprilTags
   - AprilTags provide spatial reference for data extraction

2. **Decoding Process:**
   - Image is processed to detect three AprilTags (IDs 0, 1, 2)
   - AprilTags provide coordinate system for data regions and orientation detection
   - Tag IDs determine correct image orientation (rotation-agnostic decoding)
   - Color pixels in data regions are decoded back to binary data
   - Binary data is uncompressed and unpacked back to CSV format

## Technical Details

- **Color Encoding:** Uses pure RGB colors (255,0,0), (0,255,0), (0,0,255) for data storage
- **Compression:** Zstandard compression is applied to reduce data size
- **Error Detection:** Built-in verification compares original vs decoded data
- **Capacity:** Data capacity scales with image size (2 bytes per 8 pixels)

## Example Workflow

```python
# Encode CSV data into an image
from encode_csv_to_image import encode_csv_to_image
from decode_image_to_csv import decode_image_to_csv

# Step 1: Encode
image_path = encode_csv_to_image("match_data.csv")
print(f"Data encoded into: {image_path}")

# Step 2: Simulate image capture (in real use, this would be camera input)
# The image file now contains your data visually encoded

# Step 3: Decode back to CSV
csv_path = decode_image_to_csv(str(image_path))
print(f"Data decoded back to: {csv_path}")
```

## Error Handling

Both functions will raise exceptions for common issues:
- `FileNotFoundError`: Input file doesn't exist
- `ValueError`: AprilTag detection fails or data extraction issues
- General exceptions during processing

Handle errors appropriately in your applications:

```python
try:
    result_path = encode_csv_to_image("data.csv")
    print(f"Success: {result_path}")
except FileNotFoundError:
    print("Input CSV file not found")
except ValueError as e:
    print(f"Encoding failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```
