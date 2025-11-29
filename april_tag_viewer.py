"""AprilTag detection and display using OpenCV.

This script can either:
- Open a camera feed for real-time detection and display
- Process a single image file and display detected AprilTags

Usage:
    python april_tag_viewer.py                    # Camera mode
    python april_tag_viewer.py --image path/to/image.jpg  # Image mode
"""

import argparse
import cv2
import numpy as np
import pupil_apriltags as apriltag


def draw_detections(frame: np.ndarray, detections: list) -> np.ndarray:
    """Draw AprilTag detections on a frame.

    Args:
        frame: The image frame to draw on
        detections: List of AprilTag detections

    Returns:
        The frame with detections drawn
    """
    frame_copy = frame.copy()

    for detection in detections:
        # Get corners as integers
        corners = detection.corners.astype(int)

        # Draw the bounding box (polygon around tag corners)
        cv2.polylines(frame_copy, [corners], True, (0, 255, 0), 2)

        # Draw the tag center as a red dot
        center = detection.center.astype(int)
        cv2.circle(frame_copy, tuple(center), 5, (0, 0, 255), -1)

        # Draw the tag ID near the center
        cv2.putText(
            frame_copy,
            f"ID: {detection.tag_id}",
            tuple(center + np.array([10, -10])),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        # Optionally show hamming distance
        cv2.putText(
            frame_copy,
            f"Hamming: {detection.hamming}",
            tuple(center + np.array([10, 10])),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    # Display detection count in top-left corner
    cv2.putText(
        frame_copy,
        f"Detections: {len(detections)}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )

    return frame_copy


def main() -> None:
    """Main function to run the AprilTag detection viewer."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="AprilTag detection viewer")
    parser.add_argument(
        "--image",
        "-i",
        type=str,
        help="Path to image file to process (camera mode if not provided)",
    )
    args = parser.parse_args()

    # Initialize the AprilTag detector
    detector = apriltag.Detector(
        families="tag36h11",
        nthreads=4,
        quad_decimate=1.0,
        quad_sigma=0.0,
        refine_edges=1,
        decode_sharpening=0.25,
        debug=0,
    )

    if args.image:
        # Image mode: process a single image
        print(f"Processing image: {args.image}")

        # Load the image
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"Error: Could not load image from {args.image}")
            return

        # Convert to grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect AprilTags
        detections = detector.detect(gray)

        # Draw detections on the frame
        frame_with_detections = draw_detections(frame, detections)

        # resize the frame to 1/4 size
        frame_with_detections = cv2.resize(
            frame_with_detections, (0, 0), fx=0.25, fy=0.25
        )

        print(f"Found {len(detections)} AprilTag(s) in the image.")

        # Display the result
        window_title = f"AprilTag Detection - {args.image} - Press ESC to exit"
        cv2.imshow(window_title, frame_with_detections)

        # Wait for ESC key to exit
        while (cv2.waitKey(0) & 0xFF) != 27:
            pass
        cv2.destroyAllWindows()

    else:
        # Camera mode: real-time detection
        cap = cv2.VideoCapture(0)  # Use default camera (index 0)

        if not cap.isOpened():
            print("Error: Could not open camera")
            return

        print("AprilTag Viewer started. Press ESC to exit.")
        print("Detected tags will be highlighted with green borders and ID labels.")

        try:
            while True:
                # Capture frame-by-frame
                ret, frame = cap.read()

                if not ret:
                    print("Error: Failed to capture frame")
                    break

                # Convert to grayscale for detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Detect AprilTags
                detections = detector.detect(gray)

                # Draw detections on the frame
                frame_with_detections = draw_detections(frame, detections)

                # Display the frame
                cv2.imshow("AprilTag Viewer - Press ESC to exit", frame_with_detections)

                # Wait for key press (1ms delay)
                key = cv2.waitKey(1) & 0xFF

                if key == 27:  # ESC key
                    print("Exiting...")
                    break

        finally:
            # Release the capture and close windows
            cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
