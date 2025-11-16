"""Image generation utilities for creating encoded images."""

import numpy as np
from ..common.apriltag_generation import generate_april_tags_image
from ..common.data_regions import get_data_regions
from .color_encoder import encode_bytes_to_rgb


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
    image = generate_april_tags_image(image_width, image_height, padding)

    data_regions = get_data_regions(
        image_width, image_height, tag_data_gap, data_padding
    )

    encoded_colors = encode_bytes_to_rgb(data_bytes)

    pixel_coords = []
    for row_slice, col_slice in data_regions:
        for row in range(row_slice.start, row_slice.stop):
            for col in range(col_slice.start, col_slice.stop):
                pixel_coords.append((row, col))

    bytes_needed = len(data_bytes)
    pixels_needed = ((bytes_needed + 1) // 2) * 8
    pixels_available = len(pixel_coords)

    if pixels_needed + 6 > pixels_available:  # +6 for calibration pixels
        raise ValueError(
            f"Not enough pixels to encode data: need {pixels_needed + 6} pixels "
            f"for {bytes_needed} bytes + calibration, but only have {pixels_available} pixels available"
        )

    # Place encoded data first
    for i, (row, col) in enumerate(pixel_coords):
        if i < len(encoded_colors):
            image[row, col] = encoded_colors[i]

    # Place calibration pixels at the very end of data regions (last 6 positions)
    calibration_colors = [
        (255, 255, 255),  # White
        (0, 0, 255),      # Red
        (0, 255, 0),      # Green
        (255, 0, 0),      # Blue
        (0, 0, 0),        # Black
        (255, 255, 255),  # White
    ]

    for i, calibration_color in enumerate(calibration_colors):
        coord_index = pixels_available - 6 + i  # Last 6 positions
        row, col = pixel_coords[coord_index]
        image[row, col] = calibration_color

    return image


def calculate_minimum_image_size(
    data_bytes: bytes,
    tag_data_gap: int = 1,
    data_padding: int = 4,
    start_size: int = 20,
) -> int:
    """Calculate the minimum square image size needed to fit all data.

    Args:
        data_bytes: Bytes to encode.
        tag_data_gap: Number of pixels gap between tags and data areas.
        data_padding: Number of pixels to pad the data areas from the image edges.
        start_size: Starting image size to test from.

    Returns:
        Minimum square image size that can accommodate the data.
    """
    pixels_needed = ((len(data_bytes) + 1) // 2) * 8 + 6  # +6 for calibration pixels at fixed positions

    image_size = start_size
    while True:
        data_regions = get_data_regions(
            image_size, image_size, tag_data_gap, data_padding
        )
        pixel_coords: list[tuple[int, int]] = []
        for row_slice, col_slice in data_regions:
            for row in range(row_slice.start, row_slice.stop):
                for col in range(col_slice.start, col_slice.stop):
                    pixel_coords.append((row, col))

        if len(pixel_coords) >= pixels_needed:
            return image_size

        image_size += 2

        if image_size > 1000:
            raise ValueError(
                f"Cannot find suitable image size for {len(data_bytes)} bytes of data"
            )

