"""Module for detecting April Tags in images and de-warping the detected area."""

import cv2
import numpy as np
import pupil_apriltags as apriltag


def dewarp_image(
    image: np.ndarray, corners: np.ndarray, output_size: tuple = (400, 400)
) -> np.ndarray:
    """Apply perspective transformation to dewarp the image.

    Args:
        image: Input image to dewarp.
        corners: Ordered corner points (top-left, top-right, bottom-right, bottom-left).
        output_size: Desired output size (width, height).

    Returns:
        Dewarped image.
    """
    dst_points = np.array(
        [
            [0, 0],
            [output_size[0] - 1, 0],
            [output_size[0] - 1, output_size[1] - 1],
            [0, output_size[1] - 1],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(corners.astype(np.float32), dst_points)
    return cv2.warpPerspective(image, matrix, output_size)


def find_outer_corners_from_tags(tags: list) -> np.ndarray:
    """Find the extreme corners from all detected April Tags.

    Args:
        tags: List of detected April Tag objects.

    Returns:
        Array of outer corner points [top-left, top-right, bottom-right, bottom-left].
    """
    if not tags:
        return np.array([])

    # Collect all corner points from all tags
    all_corners = []
    for tag in tags:
        all_corners.extend(tag.corners)

    all_corners = np.array(all_corners)

    # Find extreme corners
    outer_corners = np.array(
        [
            all_corners[np.argmin(all_corners.sum(axis=1))],  # top-left
            all_corners[np.argmax(all_corners[:, 0] - all_corners[:, 1])],  # top-right
            all_corners[np.argmax(all_corners.sum(axis=1))],  # bottom-right
            all_corners[
                np.argmin(all_corners[:, 0] - all_corners[:, 1])
            ],  # bottom-left
        ]
    )

    return outer_corners


def get_majority_color(cell: np.ndarray) -> tuple[int, int, int]:
    """Get the most common color in a cell.

    Args:
        cell: Image cell as numpy array.

    Returns:
        BGR tuple of the majority color.
    """
    if cell.size == 0:
        return (0, 0, 0)

    pixels = cell.reshape(-1, cell.shape[-1])
    unique_colors, counts = np.unique(pixels, axis=0, return_counts=True)
    majority_idx = np.argmax(counts)
    return tuple(unique_colors[majority_idx])


def process_image(image_path: str) -> None:
    """Process an image to detect April Tags and dewarp the area.

    Args:
        image_path: Path to the input image.
    """
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    grey_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Initialize April Tag detector
    detector = apriltag.Detector(
        families="tag16h5",
        nthreads=4,
        quad_decimate=1.0,
        quad_sigma=0.0,
        refine_edges=1,
        decode_sharpening=0.25,
        debug=0,
    )

    # Detect April Tags
    detections = detector.detect(grey_image)

    if not detections:
        print("No April Tags detected!")
        return

    print(f"Detected {len(detections)} April Tags")
    new_detections = [] 
    for detection in detections:
        if detection.tag_id == 0 and detection.hamming < 0.1:
            new_detections.append(detection)
            
    detections = new_detections
            
    print(f"Detected {len(detections)} April Tags")

    # Find outer corners from all detected tags
    outer_corners = find_outer_corners_from_tags(detections)
    print(f"Outer corners: {outer_corners}")

    if len(outer_corners) == 0:
        print("Could not determine outer corners from detected tags!")
        return

    # Display annotated image
    annotated_image = cv2.cvtColor(grey_image, cv2.COLOR_GRAY2BGR)

    # Draw detected April Tags
    for detection in detections:
        # Draw the tag outline
        corners = detection.corners.astype(int)
        cv2.polylines(annotated_image, [corners], True, (0, 255, 0), 3)

        # Draw tag ID
        center = detection.center.astype(int)
        cv2.putText(
            annotated_image,
            str(detection.tag_id),
            tuple(center),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 0, 0),
            2,
        )

    # Draw outer corners
    for corner in outer_corners.astype(int):
        cv2.circle(annotated_image, tuple(corner), 10, (0, 0, 255), -1)

    h, w = annotated_image.shape[:2]
    scale = 1000 / max(h, w)
    small_annotated = cv2.resize(annotated_image, (int(w * scale), int(h * scale)))

    # Dewarp the image
    dewarped_color = dewarp_image(image, outer_corners, output_size=(1500, 1500))

    # Create majority color grid
    total_cells = 30
    cell_size = dewarped_color.shape[0] // total_cells

    print(f"Grid size: {total_cells}x{total_cells} cells")
    print(f"Cell size: {cell_size} pixels/cell")
    
    annotated_image = dewarped_color.copy()
    # draw grid lines
    for i in range(total_cells):
        cv2.line(annotated_image, (0, i * cell_size), (dewarped_color.shape[1], i * cell_size), (0, 0, 255), 1)
        cv2.line(annotated_image, (i * cell_size, 0), (i * cell_size, dewarped_color.shape[0]), (0, 0, 255), 1)

    majority_color_grid = np.zeros_like(dewarped_color)

    for row in range(total_cells):
        for col in range(total_cells):
            y_start = row * cell_size
            y_end = min((row + 1) * cell_size, dewarped_color.shape[0])
            x_start = col * cell_size
            x_end = min((col + 1) * cell_size, dewarped_color.shape[1])

            cell = dewarped_color[y_start:y_end, x_start:x_end]
            majority_color = get_majority_color(cell)
            majority_color_grid[y_start:y_end, x_start:x_end] = majority_color

    # Display images
    cv2.imshow("Detected April Tags", small_annotated)
    cv2.imshow("Dewarped Image", cv2.resize(dewarped_color, (800, 800)))
    cv2.imshow("Majority Color Grid", cv2.resize(majority_color_grid, (800, 800)))
    cv2.imshow("Annotated Image", cv2.resize(annotated_image, (800, 800)))

    print("Press any key to close windows...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    process_image("IMG_2510.JPG")
