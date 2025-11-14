"""Module for generating images with AprilTags in corners."""

import cv2
import numpy as np
import os


def load_april_tag() -> np.ndarray:
    """Load the AprilTag image (tag16_05_00000.png) and remove outer rim pixels.

    Returns:
        A numpy array representing the cropped AprilTag pattern.
    """
    tag_path = "tag16_05_00000.png"
    if not os.path.exists(tag_path):
        raise FileNotFoundError(f"AprilTag image not found: {tag_path}")

    # Load the AprilTag image
    tag = cv2.imread(tag_path)
    if tag is None:
        raise ValueError(f"Failed to load AprilTag image from {tag_path}")

    # Convert to grayscale for consistency with original tracking square format
    tag_gray = cv2.cvtColor(tag, cv2.COLOR_BGR2GRAY)

    # Remove outer rim of pixels (crop 1 pixel from each side)
    cropped_tag = tag_gray[1:-1, 1:-1]

    return cropped_tag


def generate_april_tags_image(
    image_width: int,
    image_height: int,
    padding: int = 1,
    tag_data_gap: int = 1,
    data_padding: int = 1
) -> np.ndarray:
    """Generate an image with AprilTags in all 4 corners.

    Args:
        image_width: Width of the output image.
        image_height: Height of the output image.
        padding: Number of pixels to pad the tags from the image edges.
        tag_data_gap: Number of pixels gap between tags and data areas.
        data_padding: Number of pixels to pad the data areas from the image edges.

    Returns:
        A numpy array representing the color image with AprilTags in corners.
    """
    # Create white background image
    image = np.full((image_height, image_width, 3), 255, dtype=np.uint8)

    # Load AprilTag pattern (grayscale)
    april_tag = load_april_tag()
    tag_size = april_tag.shape[0]  # Should be 8

    # Define corner regions for AprilTags
    corners = [
        (slice(padding, padding+tag_size), slice(padding, padding+tag_size)),  # Top-left
        (slice(padding, padding+tag_size), slice(image_width-padding-tag_size, image_width-padding)),  # Top-right
        (slice(image_height-padding-tag_size, image_height-padding), slice(padding, padding+tag_size)),  # Bottom-left
        (slice(image_height-padding-tag_size, image_height-padding), slice(image_width-padding-tag_size, image_width-padding))  # Bottom-right
    ]

    # Place AprilTags at corners (convert grayscale to RGB by replicating across channels)
    for row_slice, col_slice in corners:
        # Place grayscale AprilTag in all RGB channels (keeps it black/white)
        for channel in range(3):
            image[row_slice, col_slice, channel] = april_tag

    return image


def get_data_regions(
    image_width: int,
    image_height: int,
    padding: int = 1,
    tag_data_gap: int = 1,
    data_padding: int = 1
) -> list[tuple[slice, slice]]:
    """Get the valid data regions where data can be placed between AprilTags.

    Args:
        image_width: Width of the image.
        image_height: Height of the image.
        padding: Number of pixels to pad the tags from the image edges.
        tag_data_gap: Number of pixels gap between tags and data areas.
        data_padding: Number of pixels to pad the data areas from the image edges.

    Returns:
        List of tuples containing (row_slice, col_slice) for each valid data region.
    """
    # Load AprilTag to get tag size
    april_tag = load_april_tag()
    tag_size = april_tag.shape[0]  # Should be 8

    # Define regions for data (data_padding from walls, configurable gap from tags)
    data_regions = [
        # Top area (above the top tags, with configurable gap)
        (slice(data_padding, data_padding+tag_size+tag_data_gap), slice(data_padding+tag_size+tag_data_gap, image_width-data_padding-tag_size-tag_data_gap)),
        # Bottom area (below the bottom tags, with configurable gap)
        (slice(image_height-data_padding-tag_size-tag_data_gap, image_height-data_padding), slice(data_padding+tag_size+tag_data_gap, image_width-data_padding-tag_size-tag_data_gap)),
        # Left area (left of the left tags, with configurable gap)
        (slice(data_padding+tag_size+tag_data_gap, image_height-data_padding-tag_size-tag_data_gap), slice(data_padding, data_padding+tag_size+tag_data_gap)),
        # Right area (right of the right tags, with configurable gap)
        (slice(data_padding+tag_size+tag_data_gap, image_height-data_padding-tag_size-tag_data_gap), slice(image_width-data_padding-tag_size-tag_data_gap, image_width-data_padding)),
        # Center area (between all four tags, with configurable gap from each)
        (slice(data_padding+tag_size+tag_data_gap, image_height-data_padding-tag_size-tag_data_gap), slice(data_padding+tag_size+tag_data_gap, image_width-data_padding-tag_size-tag_data_gap))
    ]

    # Filter out invalid regions (where start >= stop)
    valid_regions = []
    for row_slice, col_slice in data_regions:
        if row_slice.start < row_slice.stop and col_slice.start < col_slice.stop:
            # Ensure slices are within image bounds
            valid_row_slice = slice(max(0, row_slice.start), min(image_height, row_slice.stop))
            valid_col_slice = slice(max(0, col_slice.start), min(image_width, col_slice.stop))
            valid_regions.append((valid_row_slice, valid_col_slice))

    return valid_regions


def save_april_tags_image(
    filename: str,
    image_width: int = 500,
    image_height: int = 500,
    padding: int = 1,
    tag_data_gap: int = 1,
    data_padding: int = 1
) -> None:
    """Generate and save a color image with AprilTags in corners.

    Args:
        filename: Output filename for the image.
        image_width: Width of the output image.
        image_height: Height of the output image.
        padding: Number of pixels to pad the tags from the image edges.
        tag_data_gap: Number of pixels gap between tags and data areas.
        data_padding: Number of pixels to pad the data areas from the image edges.
    """
    image = generate_april_tags_image(image_width, image_height, padding, tag_data_gap, data_padding)
    cv2.imwrite(filename, image)
    print(f"AprilTags image saved to {filename}")


if __name__ == "__main__":
    # Example usage
    save_april_tags_image(
        "april_tags.png",
        image_width=40,
        image_height=40,
        padding=4,
        tag_data_gap=1,  # Example with 0 pixel gap between tags and random data
        data_padding=4  # Example with 1 pixel padding for random data from edges
    )