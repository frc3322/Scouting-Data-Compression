"""Camera-based decoder for QR code testing system.

This script opens a camera feed and allows decoding AprilTag-encoded data
by pressing a button. Decoded CSV files are saved to an output folder with
audio feedback for success/failure.
"""

import cv2
import tempfile
import os
from pathlib import Path
from datetime import datetime

# Try to import Windows-only winsound module for audio feedback
try:
    import winsound
    AUDIO_AVAILABLE = True
except (ImportError, OSError):
    AUDIO_AVAILABLE = False
from decode_image_to_csv import decode_image_to_csv


def play_success_sound() -> None:
    """Play a success sound using Windows beep."""
    if AUDIO_AVAILABLE:
        winsound.Beep(800, 200)  # 800Hz for 200ms


def play_failure_sound() -> None:
    """Play a failure sound using Windows beep."""
    if AUDIO_AVAILABLE:
        winsound.Beep(400, 500)  # 400Hz for 500ms


def main() -> None:
    """Main function to run the camera decoder application."""
    # Create output directory for decoded CSV files
    output_dir = Path("decoded_csvs")
    output_dir.mkdir(exist_ok=True)

    # Initialize camera
    cap = cv2.VideoCapture(0)  # Use default camera (index 0)

    if not cap.isOpened():
        print("Error: Could not open camera")
        return

    print("Camera opened successfully. Press SPACE to capture and decode, ESC to exit.")
    print(f"Decoded CSV files will be saved to: {output_dir.absolute()}")

    try:
        while True:
            # Capture frame-by-frame
            ret, frame = cap.read()

            if not ret:
                print("Error: Failed to capture frame")
                break

            # Display the frame
            cv2.imshow('Camera Feed - Press SPACE to decode, ESC to exit', frame)

            # Wait for key press
            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC key
                print("Exiting...")
                break
            elif key == 32:  # SPACE key
                print("Capturing image and attempting to decode...")

                # Save current frame to temporary file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    temp_image_path = tmp_file.name

                # Save the frame as PNG
                cv2.imwrite(temp_image_path, frame)

                try:
                    # Attempt to decode the image
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    csv_output_path = output_dir / f"decoded_{timestamp}.csv"
                    decoded_csv_path = decode_image_to_csv(
                        image_path=temp_image_path,
                        output_csv_path=csv_output_path
                    )

                    print(f"Success! Decoded data saved to: {decoded_csv_path}")
                    play_success_sound()

                except Exception as e:
                    print(f"Decoding failed: {e}")
                    play_failure_sound()

                finally:
                    # Clean up temporary image file
                    try:
                        os.unlink(temp_image_path)
                    except OSError:
                        pass  # File may already be deleted

    finally:
        # Release the capture and close windows
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
