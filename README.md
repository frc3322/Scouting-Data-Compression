# FRC Scouting Data - AprilTag Encoding System

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A specialized Python system for encoding FRC (FIRST Robotics Competition) scouting data into visual images using heavy data compression and Apriltags for data tag finding, enabling efficient data compression and transfer through camera capture. Designed specifically for scouting applications where structured match data needs to be quickly captured and transferred in environments with very limited connectivity.

39 matches encoded to a data-code!
<img width="1397" height="1413" alt="image" src="https://github.com/user-attachments/assets/a1df171f-46c0-4c20-a27a-5fd840eebe59" />

## 🚀 Features

- **FRC Scouting Optimized**: Specifically designed for FIRST Robotics Competition match data encoding and transfer
- **High Compression**: Custom data packing and Zstandard compression significantly reduces scouting data size for efficient storage
- **Visual Data Transfer**: Convert structured CSV scouting data into images that can be captured by phones/tablets
- **Real-time Processing**: Camera-based live decoding with visual feedback for instant data capture
- **Robust Detection**: AprilTag-based spatial reference ensures reliable data extraction even in challenging conditions
- **Color Encoding**: Pure RGB color palette optimized for camera capture and reliable data extraction
- **Error Detection**: Built-in verification comparing original vs decoded data to ensure data integrity

## 📦 Installation

### Prerequisites

- Python 3.8+
- uv package manager (recommended) or pip

### Install Dependencies

Using uv (recommended):

```bash
uv pip install -r requirements.txt
```

Using pip:

```bash
pip install -r requirements.txt
```

## 🛠️ Usage

For detailed usage instructions, including command-line examples, programmatic API usage, and camera controls, see [USAGE.md](USAGE.md).

### Quick Start

**Encode scouting data:**

```bash
python encode_csv_to_image.py match_data.csv
```

**Decode from image:**

```bash
python decode_image_to_csv.py encoded_image.png
```

**Real-time camera decoding:**

```bash
python camera_decoder.py
```

## 📚 API Reference

### `encode_csv_to_image(csv_path, output_image_path=None, packed_file_path=None)`

Encode CSV data into an image with AprilTags.

**Parameters:**

- `csv_path` (str | Path): Path to input CSV file
- `output_image_path` (str | Path, optional): Path for output image. Defaults to CSV name with .png extension
- `packed_file_path` (str | Path, optional): Path for intermediate packed file. Defaults to CSV name with .packed extension

**Returns:** Path to the created image file

### `decode_image_to_csv(image_path, output_csv_path=None, packed_file_path=None)`

Decode image with AprilTags back to CSV data.

**Parameters:**

- `image_path` (str | Path): Path to input image file
- `output_csv_path` (str | Path, optional): Path for output CSV. Defaults to image name with .csv extension
- `packed_file_path` (str | Path, optional): Path for intermediate packed file. If None, uses a temporary file

**Returns:** Path to the created CSV file

## 🔧 Technical Details

### Data Flow

1. **Encoding Process:**

   - CSV data is read and compressed using zstandard
   - Compressed data is packed into a binary format
   - Binary data is encoded into color pixels (RGB values)
   - Pixels are arranged in regions within an image alongside AprilTags
   - AprilTags provide spatial reference for data extraction

2. **Decoding Process:**
   - Image is processed to detect AprilTags
   - AprilTags provide accurate corners for de-warping
   - Color pixels in data regions are decoded back to binary data
   - Binary data is uncompressed and unpacked back to CSV format

### Color Encoding

Uses a 4-color palette for data storage:

- Red: (255, 0, 0)
- Green: (0, 255, 0)
- Blue: (0, 0, 255)
- Black: (0, 0, 0)

White (255, 255, 255) is reserved for background/filler.

### FRC Scouting Benefits

- **Competition Optimized**: Designed for fast data transfer in busy FRC competition environments
- **High Capacity**: Scales with image size (2 bytes per 8 pixels) - can encode hundreds of match records
- **Efficient Compression**: Zstandard compression and custom packing reduces scouting data size by 10X for better transfer
- **Robust Detection**: AprilTag positioning works reliably even with poor lighting or camera angles
- **Data Integrity**: Built-in verification ensures scouting data is not corrupted. (not amazing, but it's there for very bad scans)
- **No Network Required**: Visual transfer works without WiFi/bluetooth - perfect for competition venues

## 🏗️ Project Structure

```
qr-code-testing/
├── src/
│   ├── common/           # Shared utilities and constants
│   │   ├── constants.py  # Color palettes and shared constants
│   │   ├── data_regions.py    # Data region management
│   │   └── apriltag_generation.py  # AprilTag utilities
│   ├── encoder/          # Data encoding components
│   │   ├── data_packer.py     # Data compression/packing
│   │   ├── color_encoder.py   # Color pixel encoding
│   │   └── image_generator.py # Image generation
│   └── decoder/          # Data decoding components
│       ├── image_processor.py # Image processing
│       ├── color_decoder.py   # Color pixel decoding
│       └── data_unpacker.py   # Data decompression/unpacking
├── encode_csv_to_image.py    # Main encoding script
├── decode_image_to_csv.py    # Main decoding script
├── camera_decoder.py         # Real-time camera decoder
├── april_tag_viewer.py       # AprilTag detection viewer
├── requirements.txt          # Python dependencies
└── USAGE.md                 # Detailed usage guide
```

## 🎯 FRC Scouting Workflow

```python
from encode_csv_to_image import encode_csv_to_image
from decode_image_to_csv import decode_image_to_csv

# Encode match scouting data into a visual format
print("Encoding FRC match data...")
image_path = encode_csv_to_image("match_data.csv")
print(f"Scouting data encoded into: {image_path}")

# In competition, this image would be displayed on a device
# and captured by another device's code
# For this example, we immediately decode it back
print("Decoding scouting data...")
csv_path = decode_image_to_csv(str(image_path))
print(f"Scouting data recovered to: {csv_path}")
```

**Typical FRC Competition Usage:**

1. **At Competition**: Scouting teams collect match data in CSV format
2. **Data Encoding**: Convert CSV data to visual AprilTag images for transfer
3. **Visual Transfer**: Display encoded images on tablets/phones
4. **Data Capture**: Capture the data with a central laptop/tablet
5. **Data Decoding**: Automatically extract CSV data from captured images
6. **Data Aggregation**: Combine scouting data from multiple sources/devices for analysis

## ⚠️ Error Handling

Both encoding and decoding functions may raise exceptions:

- `FileNotFoundError`: Input file doesn't exist
- `ValueError`: AprilTag detection fails or data extraction issues
- General exceptions during processing

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

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-username/qr-code-testing.git
cd qr-code-testing

# Install dependencies
uv pip install -r requirements.txt
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [AprilTags](https://april.eecs.umich.edu/software/apriltag/) for robust visual fiducial markers
- [OpenCV](https://opencv.org/) for computer vision functionality
- [Zstandard](https://facebook.github.io/zstd/) for high-performance compression
- [Pupil Labs](https://pupil-labs.com/) for the Python AprilTag implementation
