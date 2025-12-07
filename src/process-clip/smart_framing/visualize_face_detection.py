"""
Face Detection Visualization Tool

This script creates visualizations showing detected faces from different models:
1. GREEN boxes: MediaPipe Original detections
2. BLUE boxes: MediaPipe Improved detections
3. RED boxes: RetinaFace detections
4. Shows confidence scores and face centers

Helps validate which detector works best for your videos.

Usage:
    python visualize_face_detection.py <video_path> <duration> [detector]

Examples:
    python visualize_face_detection.py video.mp4 10
    python visualize_face_detection.py video.mp4 10 retinaface
    python visualize_face_detection.py video.mp4 10 comparison
"""

import sys
import os
import cv2
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smart_framing.face_detector_factory import create_detector


def visualize_single_detector(
    video_path: str,
    max_duration: float = 30.0,
    detector_backend: str = 'retinaface',
    confidence_threshold: float = 0.75
):
    """
    Visualize face detection from a single detector.

    Args:
        video_path: Path to video file
        max_duration: Duration to process
        detector_backend: Which detector to use
        confidence_threshold: Detection confidence threshold
    """
    print("=" * 80)
    print(f"FACE DETECTION VISUALIZATION - {detector_backend.upper()}")
    print("=" * 80)
    print()

    if not os.path.exists(video_path):
        print(f"❌ ERROR: Video not found: {video_path}")
        return False

    output_dir = Path("smart_framing/visualization_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create detector
    print(f"🔧 Creating {detector_backend} detector...")
    detector = create_detector(
        backend=detector_backend,
        confidence_threshold=confidence_threshold,
        min_face_size=30
    )
    print()

    # Detect faces
    print("🔍 Detecting faces in video...")
    detections = detector.detect_faces_in_video(
        video_path,
        start_sec=0,
        end_sec=max_duration,
        sample_rate=2
    )

    stats = detector.get_face_statistics(detections)
    print()
    print("📊 Detection Statistics:")
    print(f"   Total frames processed: {stats['total_frames']}")
    print(f"   Frames with faces: {stats['frames_with_faces']}")
    print(f"   Total faces detected: {stats['total_faces']}")
    print(f"   Coverage: {stats['coverage_percent']:.1f}%")
    print(f"   Avg confidence: {stats['avg_confidence']:.3f}")
    print(f"   Avg face size: {stats.get('avg_face_size_px', 0):.0f}px²")
    print()

    # Create visualization
    print("🎨 Creating visualization video...")
    output_path = output_dir / f"detection_{detector_backend}.mp4"

    cap = cv2.VideoCapture(video_path)
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (video_width, video_height))

    # Create lookup dict
    detections_by_frame = {d['frame_num']: d['faces'] for d in detections}

    frame_num = 0
    current_time = 0

    # Color based on detector
    color_map = {
        'mediapipe': (0, 255, 0),  # Green
        'mediapipe_improved': (255, 0, 0),  # Blue
        'retinaface': (0, 0, 255)  # Red
    }
    color = color_map.get(detector_backend, (255, 255, 255))

    while current_time < max_duration:
        ret, frame = cap.read()
        if not ret:
            break

        overlay = frame.copy()

        # Draw detected faces
        if frame_num in detections_by_frame:
            faces = detections_by_frame[frame_num]

            for i, face in enumerate(faces):
                bbox = face['bbox']
                confidence = face['confidence']

                # Draw bounding box
                cv2.rectangle(
                    overlay,
                    (bbox['x'], bbox['y']),
                    (bbox['x'] + bbox['w'], bbox['y'] + bbox['h']),
                    color,
                    3
                )

                # Draw face center
                center_x = bbox['x'] + bbox['w'] // 2
                center_y = bbox['y'] + bbox['h'] // 2
                cv2.circle(overlay, (center_x, center_y), 5, color, -1)

                # Draw cross at center for better visibility
                cross_size = 10
                cv2.line(overlay,
                        (center_x - cross_size, center_y),
                        (center_x + cross_size, center_y),
                        color, 2)
                cv2.line(overlay,
                        (center_x, center_y - cross_size),
                        (center_x, center_y + cross_size),
                        color, 2)

                # Add confidence label
                conf_text = f"Face {i+1}: {confidence:.3f}"
                label_y = max(bbox['y'] - 10, 20)

                # Add background for text
                text_size = cv2.getTextSize(conf_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(
                    overlay,
                    (bbox['x'], label_y - text_size[1] - 5),
                    (bbox['x'] + text_size[0], label_y + 5),
                    (0, 0, 0),
                    -1
                )

                cv2.putText(
                    overlay,
                    conf_text,
                    (bbox['x'], label_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2
                )

                # Add face size info
                size_text = f"{bbox['w']}x{bbox['h']}"
                cv2.putText(
                    overlay,
                    size_text,
                    (bbox['x'], bbox['y'] + bbox['h'] + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2
                )

        # Add info panel
        panel_h = 160
        panel = overlay.copy()
        cv2.rectangle(panel, (10, 10), (400, panel_h), (0, 0, 0), -1)
        cv2.addWeighted(panel, 0.7, overlay, 0.3, 0, overlay)

        # Add detector info
        info_y = 30
        cv2.putText(overlay, f"Detector: {detector_backend.upper()}", (20, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        info_y += 25
        cv2.putText(overlay, f"Confidence: {confidence_threshold}", (20, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        info_y += 25
        faces_in_frame = len(detections_by_frame.get(frame_num, []))
        cv2.putText(overlay, f"Faces in frame: {faces_in_frame}", (20, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        info_y += 25
        cv2.putText(overlay, f"Frame: {frame_num}", (20, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        info_y += 25
        cv2.putText(overlay, f"Time: {current_time:.2f}s", (20, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Add statistics in bottom right
        stats_x = video_width - 250
        stats_y = video_height - 100
        cv2.rectangle(overlay, (stats_x, stats_y), (video_width - 10, video_height - 10),
                     (0, 0, 0), -1)

        stats_y += 25
        cv2.putText(overlay, f"Total faces: {stats['total_faces']}", (stats_x + 10, stats_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        stats_y += 20
        cv2.putText(overlay, f"Coverage: {stats['coverage_percent']:.1f}%", (stats_x + 10, stats_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        stats_y += 20
        cv2.putText(overlay, f"Avg conf: {stats['avg_confidence']:.3f}", (stats_x + 10, stats_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        out.write(overlay)
        frame_num += 1
        current_time = frame_num / fps

    cap.release()
    out.release()

    print(f"✅ Visualization saved to: {output_path}")
    print()

    return True


def visualize_comparison(
    video_path: str,
    max_duration: float = 30.0
):
    """
    Create side-by-side comparison of all detectors.

    Args:
        video_path: Path to video file
        max_duration: Duration to process
    """
    print("=" * 80)
    print("FACE DETECTION COMPARISON VISUALIZATION")
    print("=" * 80)
    print()

    if not os.path.exists(video_path):
        print(f"❌ ERROR: Video not found: {video_path}")
        return False

    output_dir = Path("smart_framing/visualization_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define detectors to compare
    detectors_config = [
        {
            'name': 'MediaPipe Original',
            'backend': 'mediapipe',
            'color': (0, 255, 0),  # Green
            'params': {'confidence_threshold': 0.6}
        },
        {
            'name': 'MediaPipe Improved',
            'backend': 'mediapipe_improved',
            'color': (255, 0, 0),  # Blue
            'params': {'confidence_threshold': 0.7, 'min_face_size': 30}
        },
        {
            'name': 'RetinaFace',
            'backend': 'retinaface',
            'color': (0, 0, 255),  # Red
            'params': {'confidence_threshold': 0.75, 'min_face_size': 30}
        }
    ]

    # Detect faces with each detector
    all_detections = []
    all_stats = []

    for config in detectors_config:
        print(f"🔍 Testing {config['name']}...")

        try:
            detector = create_detector(
                backend=config['backend'],
                **config['params']
            )

            detections = detector.detect_faces_in_video(
                video_path,
                start_sec=0,
                end_sec=max_duration,
                sample_rate=2
            )

            stats = detector.get_face_statistics(detections)

            all_detections.append({
                'name': config['name'],
                'backend': config['backend'],
                'color': config['color'],
                'detections': detections,
                'stats': stats
            })
            all_stats.append(stats)

            print(f"   ✅ {stats['total_faces']} faces detected, {stats['coverage_percent']:.1f}% coverage")

        except Exception as e:
            print(f"   ❌ Error with {config['name']}: {e}")
            import traceback
            traceback.print_exc()

    print()

    # Create comparison video (overlay all detections)
    print("🎨 Creating comparison visualization...")
    output_path = output_dir / "detection_comparison.mp4"

    cap = cv2.VideoCapture(video_path)
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (video_width, video_height))

    # Create lookup dicts for each detector
    detections_by_detector = []
    for det_data in all_detections:
        detections_by_frame = {d['frame_num']: d['faces'] for d in det_data['detections']}
        detections_by_detector.append({
            'name': det_data['name'],
            'color': det_data['color'],
            'by_frame': detections_by_frame
        })

    frame_num = 0
    current_time = 0

    while current_time < max_duration:
        ret, frame = cap.read()
        if not ret:
            break

        overlay = frame.copy()

        # Draw detections from each detector with different colors
        for det_idx, det_data in enumerate(detections_by_detector):
            if frame_num in det_data['by_frame']:
                faces = det_data['by_frame'][frame_num]
                color = det_data['color']

                for face in faces:
                    bbox = face['bbox']

                    # Draw bounding box with offset for visibility
                    offset = det_idx * 3  # Offset each detector slightly
                    cv2.rectangle(
                        overlay,
                        (bbox['x'] + offset, bbox['y'] + offset),
                        (bbox['x'] + bbox['w'] + offset, bbox['y'] + bbox['h'] + offset),
                        color,
                        2
                    )

                    # Draw face center
                    center_x = bbox['x'] + bbox['w'] // 2
                    center_y = bbox['y'] + bbox['h'] // 2
                    cv2.circle(overlay, (center_x, center_y), 3, color, -1)

        # Add legend
        legend_y = 30
        for det_idx, det_data in enumerate(detections_by_detector):
            faces_in_frame = len(det_data['by_frame'].get(frame_num, []))
            legend_text = f"{det_data['name']}: {faces_in_frame} faces"

            # Background for text
            text_size = cv2.getTextSize(legend_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(overlay,
                         (10, legend_y + det_idx * 30 - text_size[1] - 5),
                         (10 + text_size[0] + 10, legend_y + det_idx * 30 + 5),
                         (0, 0, 0), -1)

            cv2.putText(overlay, legend_text,
                       (15, legend_y + det_idx * 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, det_data['color'], 2)

        # Add frame info
        info_text = f"Frame: {frame_num} | Time: {current_time:.2f}s"
        cv2.rectangle(overlay, (10, video_height - 40), (300, video_height - 10),
                     (0, 0, 0), -1)
        cv2.putText(overlay, info_text, (15, video_height - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        out.write(overlay)
        frame_num += 1
        current_time = frame_num / fps

    cap.release()
    out.release()

    print(f"✅ Comparison visualization saved to: {output_path}")
    print()

    # Print comparison summary
    print("=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print()
    print(f"{'Detector':<25} {'Faces':<10} {'Coverage':<12} {'Confidence':<12}")
    print("-" * 80)

    for det_data in all_detections:
        stats = det_data['stats']
        print(
            f"{det_data['name']:<25} "
            f"{stats['total_faces']:<10} "
            f"{stats['coverage_percent']:>6.1f}%     "
            f"{stats['avg_confidence']:<12.3f}"
        )

    print()
    print("Color Legend:")
    print("  GREEN:  MediaPipe Original")
    print("  BLUE:   MediaPipe Improved")
    print("  RED:    RetinaFace")
    print()

    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python visualize_face_detection.py <video_path> [duration] [detector]")
        print()
        print("Examples:")
        print("  python visualize_face_detection.py video.mp4 10")
        print("  python visualize_face_detection.py video.mp4 10 retinaface")
        print("  python visualize_face_detection.py video.mp4 10 comparison")
        print()
        print("Detectors: mediapipe, mediapipe_improved, retinaface, comparison")
        sys.exit(1)

    video_path = sys.argv[1]
    max_duration = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    detector = sys.argv[3] if len(sys.argv) > 3 else 'retinaface'

    if detector == 'comparison':
        success = visualize_comparison(video_path, max_duration)
    else:
        success = visualize_single_detector(video_path, max_duration, detector)

    if success:
        print("=" * 80)
        print("✅ DONE!")
        print("=" * 80)
        print()
        print("Check the output in: smart_framing/visualization_output/")
        print()
        print("What to look for:")
        print("  ✅ Bounding boxes should surround all visible faces")
        print("  ✅ No boxes around non-faces (false positives)")
        print("  ✅ Small/distant faces should be detected")
        print("  ✅ Confidence scores should be reasonable (0.7+)")
        print()
        print("If you see issues:")
        print("  - False positives: Increase confidence_threshold")
        print("  - Missing faces: Use retinaface backend or lower threshold")
        print("  - Try comparison mode to see all detectors side-by-side")
        print()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
