"""Data region calculation utilities."""

from .apriltag_generation import load_april_tag


def get_data_regions(
    image_width: int, image_height: int, tag_data_gap: int = 1, data_padding: int = 1
) -> list[tuple[slice, slice]]:
    """Get the valid data regions where data can be placed between AprilTags.

    Uses three AprilTags in top-left, top-right, and bottom-left corners.
    Bottom-right corner is used for data, so the bottom region extends to the right edge.

    Args:
        image_width: Width of the image.
        image_height: Height of the image.
        tag_data_gap: Number of pixels gap between tags and data areas.
        data_padding: Number of pixels to pad the data areas from the image edges.

    Returns:
        List of tuples containing (row_slice, col_slice) for each valid data region.
    """
    april_tag = load_april_tag()
    tag_size = april_tag.shape[0]

    data_regions = [
        (
            slice(data_padding, data_padding + tag_size + tag_data_gap),
            slice(
                data_padding + tag_size + tag_data_gap,
                image_width - data_padding - tag_size - tag_data_gap,
            ),
        ),
        (
            slice(
                image_height - data_padding - tag_size - tag_data_gap,
                image_height - data_padding,
            ),
            slice(
                data_padding + tag_size + tag_data_gap,
                image_width - data_padding,
            ),
        ),
        (
            slice(
                data_padding + tag_size + tag_data_gap,
                image_height - data_padding - tag_size - tag_data_gap,
            ),
            slice(data_padding, data_padding + tag_size + tag_data_gap),
        ),
        (
            slice(
                data_padding + tag_size + tag_data_gap,
                image_height - data_padding - tag_size - tag_data_gap,
            ),
            slice(
                image_width - data_padding - tag_size - tag_data_gap,
                image_width - data_padding,
            ),
        ),
        (
            slice(
                data_padding + tag_size + tag_data_gap,
                image_height - data_padding - tag_size - tag_data_gap,
            ),
            slice(
                data_padding + tag_size + tag_data_gap,
                image_width - data_padding - tag_size - tag_data_gap,
            ),
        ),
    ]

    valid_regions = []
    for row_slice, col_slice in data_regions:
        if row_slice.start < row_slice.stop and col_slice.start < col_slice.stop:
            valid_row_slice = slice(
                max(0, row_slice.start), min(image_height, row_slice.stop)
            )
            valid_col_slice = slice(
                max(0, col_slice.start), min(image_width, col_slice.stop)
            )
            valid_regions.append((valid_row_slice, valid_col_slice))

    return valid_regions
