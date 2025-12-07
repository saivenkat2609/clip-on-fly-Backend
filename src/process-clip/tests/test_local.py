"""
Local Test Script for Smart Framing Face Detection

This script tests the face detection module locally before deploying to Lambda.

Usage:
    python tests/test_local.py <video_path>

    Example:
    python tests/test_local.py tests/sample_clips/test_video.mp4

Output:
    - Console output with detection statistics
    - Annotated video saved to tests/output/annotated_video.mp4
"""

import sys
import os
import time
from pathlib import Path

# Add parent directory to path to import smart_framing module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smart_framing.face_detection import FaceDetector


def test_face_detection(video_path: str, max_duration: float = 60.0):
    """
    Test face detection on a video file.

    Args:
        video_path: Path to video file
        max_duration: Maximum duration to process in seconds (default: 60)
    """
    print("=" * 70)
    print("SMART FRAMING - LOCAL FACE DETECTION TEST")
    print("=" * 70)
    print()

    # Verify video file exists
    if not os.path.exists(video_path):
        print(f"❌ ERROR: Video file not found: {video_path}")
        print()
        print("Please place a test video in: tests/sample_clips/")
        return False

    print(f"📹 Video file: {video_path}")
    print()

    # Initialize detector
    print("🔧 Initializing face detector...")
    detector = FaceDetector(confidence_threshold=0.6)
    print()

    # Run face detection
    print("🔍 Running face detection...")
    print(f"   Processing first {max_duration} seconds of video")
    print(f"   Sampling rate: every 2nd frame")
    print()

    start_time = time.time()
    try:
        detections = detector.detect_faces_in_video(
            video_path,
            start_sec=0,
            end_sec=max_duration,
            sample_rate=2
        )
    except Exception as e:
        print(f"❌ ERROR during face detection: {str(e)}")
        return False

    detection_time = time.time() - start_time
    print()

    # Display results
    print("=" * 70)
    print("DETECTION RESULTS")
    print("=" * 70)
    print()

    if not detections:
        print("❌ No frames processed")
        return False

    # Get statistics
    stats = detector.get_face_statistics(detections)

    print(f"✅ Total frames processed: {stats['total_frames']}")
    print(f"✅ Frames with faces: {stats['frames_with_faces']}")
    print(f"✅ Total faces detected: {stats['total_faces']}")
    print(f"✅ Average faces per frame: {stats['avg_faces_per_frame']:.2f}")
    print(f"✅ Average confidence: {stats['avg_confidence']:.2f}")
    print(f"✅ Face coverage: {stats['coverage_percent']:.1f}%")
    print()
    print(f"⏱️  Processing time: {detection_time:.2f} seconds")
    print(f"⏱️  Video duration processed: {max_duration:.2f} seconds")
    print(f"⏱️  Processing speed: {max_duration/detection_time:.2f}x realtime" if detection_time > 0 else "⏱️  Processing speed: N/A")
    print()

    # Show sample detections
    print("📋 Sample detections (first 10 frames with faces):")
    print()

    sample_count = 0
    for detection in detections:
        if detection['faces'] and sample_count < 10:
            timestamp = detection['timestamp']
            face_count = len(detection['faces'])
            print(f"   Frame {detection['frame_num']} @ {timestamp:.2f}s: {face_count} face(s)")

            for i, face in enumerate(detection['faces']):
                bbox = face['bbox']
                conf = face['confidence']
                print(f"      Face {i+1}: bbox=({bbox['x']}, {bbox['y']}, {bbox['w']}, {bbox['h']}) conf={conf:.2f}")

            sample_count += 1

    print()

    # Create annotated video
    print("=" * 70)
    print("CREATING ANNOTATED VIDEO")
    print("=" * 70)
    print()

    output_dir = Path("tests/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "annotated_video.mp4"

    print(f"💾 Saving annotated video to: {output_path}")
    print(f"   Output will contain only the processed segment (0s to {max_duration:.1f}s)")
    print("   (This may take a moment...)")
    print()

    viz_start_time = time.time()
    try:
        detector.visualize_detections(
            video_path,
            detections,
            str(output_path),
            start_sec=0,
            end_sec=max_duration
        )
    except Exception as e:
        print(f"❌ ERROR creating annotated video: {str(e)}")
        return False

    viz_time = time.time() - viz_start_time
    print(f"⏱️  Video annotation time: {viz_time:.2f} seconds")
    print()

    print()
    print("=" * 70)
    print("TEST COMPLETE!")
    print("=" * 70)
    print()
    print("✅ Face detection is working!")
    print()
    print("Next steps:")
    print("  1. Open the annotated video to verify face detection quality")
    print(f"     Location: {output_path}")
    print("  2. Check that bounding boxes appear around detected faces")
    print("  3. If detection looks good, proceed with Phase 2 (complete test suite)")
    print()

    # Provide quality assessment
    if stats['coverage_percent'] < 50:
        print("⚠️  WARNING: Face coverage is low (<50%)")
        print("   - Check if video has visible faces")
        print("   - Try adjusting confidence threshold")
    elif stats['avg_confidence'] < 0.7:
        print("⚠️  WARNING: Average confidence is low (<0.7)")
        print("   - Detection may have false positives")
        print("   - Consider increasing confidence threshold")
    else:
        print("🎉 Detection quality looks good!")

    print()
    return True


def main():
    """Main entry point for test script."""
    if len(sys.argv) < 2:
        print("❌ ERROR: No video file specified")
        print()
        print("Usage:")
        print("  python tests/test_local.py <video_path>")
        print()
        print("Example:")
        print("  python tests/test_local.py tests/sample_clips/test_video.mp4")
        print()
        print("If you don't have a test video:")
        print("  1. Place a sample video (MP4) in: tests/sample_clips/")
        print("  2. Recommended: 30-60 second clip with visible speaker")
        print()
        sys.exit(1)

    video_path = sys.argv[1]

    # Optional: limit duration via command line argument
    max_duration = 60.0  # Default: first 60 seconds
    if len(sys.argv) > 2:
        try:
            max_duration = float(sys.argv[2])
        except ValueError:
            print(f"⚠️  WARNING: Invalid duration '{sys.argv[2]}', using default (60s)")

    success = test_face_detection(video_path, max_duration)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
