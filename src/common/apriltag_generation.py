"""AprilTag generation utilities."""

import cv2
import numpy as np
from pathlib import Path


def load_april_tag() -> np.ndarray:
    """Load the AprilTag image (tag36_11_00000.png) and remove outer rim pixels.

    Returns:
        A numpy array representing the cropped AprilTag pattern.
    """
    tag_path = Path(__file__).parent / "tag36_11_00000.png"
    if not tag_path.exists():
        raise FileNotFoundError(f"AprilTag image not found: {tag_path}")

    tag = cv2.imread(str(tag_path))
    if tag is None:
        raise ValueError(f"Failed to load AprilTag image from {tag_path}")

    tag_gray = cv2.cvtColor(tag, cv2.COLOR_BGR2GRAY)

    cropped_tag = tag_gray[1:-1, 1:-1]

    return cropped_tag


def generate_april_tags_image(
    image_width: int, image_height: int, padding: int = 1
) -> np.ndarray:
    """Generate an image with AprilTags (tag36h11 family) in all 4 corners.

    Args:
        image_width: Width of the output image.
        image_height: Height of the output image.
        padding: Number of pixels to pad the tags from the image edges.

    Returns:
        A numpy array representing the color image with AprilTags in corners.

    Raises:
        ValueError: If the image dimensions cannot accommodate the tags and padding.
    """
    image = np.full((image_height, image_width, 3), 255, dtype=np.uint8)

    april_tag = load_april_tag()
    tag_size = april_tag.shape[0]

    if image_width < (2 * padding) + tag_size or image_height < (2 * padding) + tag_size:
        raise ValueError(
            "Image dimensions are too small for the AprilTag and padding: "
            f"width={image_width}, height={image_height}, padding={padding}, tag_size={tag_size}"
        )

    corners = [
        (
            slice(padding, padding + tag_size),
            slice(padding, padding + tag_size),
        ),
        (
            slice(padding, padding + tag_size),
            slice(image_width - padding - tag_size, image_width - padding),
        ),
        (
            slice(image_height - padding - tag_size, image_height - padding),
            slice(padding, padding + tag_size),
        ),
        (
            slice(image_height - padding - tag_size, image_height - padding),
            slice(image_width - padding - tag_size, image_width - padding),
        ),
    ]

    for row_slice, col_slice in corners:
        for channel in range(3):
            image[row_slice, col_slice, channel] = april_tag

    return image
