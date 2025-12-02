"""Color palette utilities for dynamic color encoding."""

import json
import math
from pathlib import Path


def load_color_palette(palette_path: Path) -> list[tuple[int, int, int]]:
    """Load color palette from JSON file.

    Args:
        palette_path: Path to JSON file containing RGB color array.

    Returns:
        List of RGB tuples (R, G, B) in range 0-255.

    Raises:
        FileNotFoundError: If palette file does not exist.
        ValueError: If palette file contains invalid data.
    """
    if not palette_path.exists():
        raise FileNotFoundError(f"Palette file not found: {palette_path}")

    with open(palette_path, "r") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Palette file must contain a JSON array")

    palette = []
    for i, color in enumerate(data):
        if not isinstance(color, list) or len(color) != 3:
            raise ValueError(f"Invalid color at index {i}: must be [R, G, B] array")
        r, g, b = color
        if not all(isinstance(c, int) and 0 <= c <= 255 for c in (r, g, b)):
            raise ValueError(f"Invalid color at index {i}: RGB values must be 0-255")
        palette.append((r, g, b))

    if len(palette) < 2:
        raise ValueError("Palette must contain at least 2 colors")

    return palette


def usable_color_set(palette: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """Get the largest power-of-two subset of colors from the palette.

    Uses the first N colors where N is the largest power of 2 <= len(palette).
    Examples: 3 colors -> use first 2, 5-7 colors -> use first 4, 9-15 colors -> use first 8.

    Args:
        palette: List of RGB tuples.

    Returns:
        Subset of palette with power-of-two length.
    """
    palette_size = len(palette)
    if palette_size < 2:
        raise ValueError("Palette must contain at least 2 colors")

    power_of_two = 1
    while power_of_two * 2 <= palette_size:
        power_of_two *= 2

    return palette[:power_of_two]


def index_to_rgb(
    index: int, palette: list[tuple[int, int, int]]
) -> tuple[int, int, int]:
    """Convert a palette index to RGB tuple.

    Args:
        index: Palette index (0-based).
        palette: List of RGB tuples.

    Returns:
        RGB tuple for the given index.

    Raises:
        IndexError: If index is out of range.
    """
    if index < 0 or index >= len(palette):
        raise IndexError(f"Palette index {index} out of range [0, {len(palette)})")
    return palette[index]


def rgb_to_bgr(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Convert RGB tuple to BGR tuple (OpenCV format).

    Args:
        rgb: RGB tuple (R, G, B).

    Returns:
        BGR tuple (B, G, R).
    """
    return (rgb[2], rgb[1], rgb[0])


def palette_to_bgr(palette: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """Convert a palette from RGB to BGR format.

    Args:
        palette: List of RGB tuples.

    Returns:
        List of BGR tuples.
    """
    return [rgb_to_bgr(rgb) for rgb in palette]


def calculate_bits_per_pixel(num_colors: int) -> int:
    """Calculate bits per pixel needed for the given number of colors.

    Args:
        num_colors: Number of colors in palette (must be power of 2).

    Returns:
        Number of bits per pixel.
    """
    return int(math.log2(num_colors))
