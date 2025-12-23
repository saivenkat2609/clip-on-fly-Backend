"""
Crop Validation Visualization Tool - With Improved Face Detection

This script uses the IMPROVED MediaPipe detector with validation layer to:
1. Show detected face bounding boxes (green) with better accuracy
2. Show calculated crop regions (blue) that follow faces
3. Demonstrate reduced false positives
4. Show better detection of small/distant faces

Usage:
    python tests/visualize_crop_improved.py <video_path> <duration>

Example:
    python tests/visualize_crop_improved.py path/to/video.mp4 30
"""

import sys
import os
import cv2
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import IMPROVED detector
from smart_framing.face_detection_improved import ImprovedMediaPipeFaceDetector
from smart_framing.speaker_tracking import correlate_faces_with_speech
from smart_framing.smart_crop import calculate_smart_crop


def load_transcript_from_file(transcript_path: str, max_duration: float = None) -> list:
    """
    Load transcript from JSON file.

    Args:
        transcript_path: Path to transcription JSON file
        max_duration: Optional max duration to clip segments

    Returns:
        List of transcript segments
    """
    import json

    if not os.path.exists(transcript_path):
        print(f"⚠️  Transcript file not found: {transcript_path}")
        print("   Using mock transcript as fallback...")
        return create_mock_transcript(max_duration or 60.0)

    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        segments = data.get('segments', [])

        # Filter segments within duration
        if max_duration:
            segments = [s for s in segments if s['start'] < max_duration]

        print(f"✅ Loaded {len(segments)} transcript segments from file")
        return segments

    except Exception as e:
        print(f"⚠️  Error loading transcript: {e}")
        print("   Using mock transcript as fallback...")
        return create_mock_transcript(max_duration or 60.0)


def create_mock_transcript(duration: float, num_segments: int = 3) -> list:
    """Create mock transcript segments."""
    segments = []
    segment_duration = duration / num_segments

    mock_texts = [
        "Welcome everyone to today's discussion.",
        "Let me explain the key concepts we'll cover.",
        "This is really important for understanding the topic.",
        "Now let's move on to the next section.",
        "In conclusion, these are the main takeaways.",
    ]

    for i in range(num_segments):
        start = i * segment_duration
        end = (i + 1) * segment_duration

        segments.append({
            'start': start,
            'end': end,
            'text': mock_texts[i % len(mock_texts)],
            'words': []
        })

    return segments


def visualize_crop_with_improved_detection(
    video_path: str,
    max_duration: float = 30.0,
    target_aspect: str = '9:16'
):
    """
    Create visualization using IMPROVED face detection.

    Args:
        video_path: Path to video file
        max_duration: Duration to process
        target_aspect: Target aspect ratio
    """
    print("=" * 80)
    print("CROP VALIDATION - IMPROVED MEDIAPIPE DETECTION")
    print("=" * 80)
    print()

    if not os.path.exists(video_path):
        print(f"❌ ERROR: Video not found: {video_path}")
        return False

    output_dir = Path("tests/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Detect faces with IMPROVED detector
    print("🔍 Step 1: Detecting faces with IMPROVED MediaPipe...")
    print("   Features:")
    print("   - Full-range model (better for distant faces)")
    print("   - Validation layer (filters false positives)")
    print("   - Temporal consistency (reduces flickering)")
    print()

    detector = ImprovedMediaPipeFaceDetector(
        confidence_threshold=0.7,        # Higher = fewer false positives
        min_face_size=30,                # Minimum face size in pixels
        max_face_size=None,              # Auto-detect max size
        use_full_range_model=True        # Better for small/distant faces
    )

    detections = detector.detect_faces_in_video(
        video_path,
        start_sec=0,
        end_sec=max_duration,
        sample_rate=2,
        enable_temporal_filtering=True   # Reduces false positives
    )

    stats = detector.get_face_statistics(detections)
    print()
    print("📊 Detection Statistics:")
    print(f"   Total frames: {stats['total_frames']}")
    print(f"   Frames with faces: {stats['frames_with_faces']}")
    print(f"   Total faces detected: {stats['total_faces']}")
    print(f"   Coverage: {stats['coverage_percent']:.1f}%")
    print(f"   Avg confidence: {stats['avg_confidence']:.3f}")
    print()

    # Step 2: Correlate with speech
    print("📝 Step 2: Correlating faces with speech...")

    # Try to find transcript file
    video_dir = os.path.dirname(video_path)
    transcript_path = os.path.join(video_dir, "transription.json")

    if not os.path.exists(transcript_path):
        transcript_path = os.path.join(video_dir, "transcription.json")

    transcript_segments = load_transcript_from_file(transcript_path, max_duration)

    speaker_activity = correlate_faces_with_speech(
        detections,
        transcript_segments,
        clip_start=0
    )
    print(f"✅ Identified {len(speaker_activity)} speaker segments")
    print()

    # Step 3: Calculate crop positions
    print("📐 Step 3: Calculating smart crop positions...")
    cap = cv2.VideoCapture(video_path)
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    print(f"   Video: {video_width}x{video_height} @ {fps:.2f}fps")

    crop_timeline, crop_dims = calculate_smart_crop(
        speaker_activity,
        video_width,
        video_height,
        target_aspect=target_aspect,
        smoothing_sigma=0.5,
        face_timeline=detections,
        enable_motion_keyframes=True,
        motion_threshold=100,
        max_keyframe_interval=3.0
    )
    print(f"✅ Generated {len(crop_timeline)} crop keyframes")
    print(f"   Crop size: {crop_dims[0]}x{crop_dims[1]}")
    print()

    # Step 4: Create visualization
    print("🎨 Step 4: Creating visualization video...")
    output_path = output_dir / "crop_validation_improved.mp4"

    cap = cv2.VideoCapture(video_path)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (video_width, video_height))

    # Create lookup dicts
    detections_by_frame = {d['frame_num']: d['faces'] for d in detections}

    frame_num = 0
    current_time = 0
    current_keyframe_idx = 0

    # Print keyframe summary
    print(f"📊 Keyframe Summary:")
    print(f"   Total keyframes: {len(crop_timeline)}")
    transcript_kf = sum(1 for kf in crop_timeline if kf.get('source') == 'transcript')
    motion_kf = sum(1 for kf in crop_timeline if kf.get('source') == 'motion')
    print(f"   Transcript keyframes: {transcript_kf}")
    print(f"   Motion keyframes: {motion_kf}")
    print()

    while current_time < max_duration:
        ret, frame = cap.read()
        if not ret:
            break

        # Create visualization overlay
        overlay = frame.copy()

        # Draw detected face bounding boxes (GREEN)
        if frame_num in detections_by_frame:
            faces = detections_by_frame[frame_num]
            for i, face in enumerate(faces):
                bbox = face['bbox']
                confidence = face['confidence']

                # Draw rectangle
                cv2.rectangle(
                    overlay,
                    (bbox['x'], bbox['y']),
                    (bbox['x'] + bbox['w'], bbox['y'] + bbox['h']),
                    (0, 255, 0),  # Green
                    2
                )

                # Draw face center (RED DOT)
                center_x = bbox['x'] + bbox['w'] // 2
                center_y = bbox['y'] + bbox['h'] // 2
                cv2.circle(overlay, (center_x, center_y), 5, (0, 0, 255), -1)

                # Add confidence label with background
                conf_text = f"Face {i+1}: {confidence:.2f}"
                text_size = cv2.getTextSize(conf_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]

                # Background for text
                cv2.rectangle(
                    overlay,
                    (bbox['x'], bbox['y'] - text_size[1] - 10),
                    (bbox['x'] + text_size[0], bbox['y']),
                    (0, 0, 0),
                    -1
                )

                cv2.putText(
                    overlay,
                    conf_text,
                    (bbox['x'], bbox['y'] - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

        # Find active crop region
        active_crop = None
        active_keyframe_idx = None
        is_keyframe_boundary = False

        for i, crop in enumerate(crop_timeline):
            start_time = crop['timestamp']
            if i + 1 < len(crop_timeline):
                end_time = crop_timeline[i + 1]['timestamp']
            else:
                end_time = start_time + 999

            if start_time <= current_time < end_time:
                active_crop = crop
                active_keyframe_idx = i

                if abs(current_time - start_time) < 0.1:
                    is_keyframe_boundary = True
                break

        # Draw crop region (BLUE)
        if active_crop:
            crop_color = (255, 255, 0) if is_keyframe_boundary else (255, 0, 0)
            crop_thickness = 5 if is_keyframe_boundary else 3

            cv2.rectangle(
                overlay,
                (active_crop['crop_x'], active_crop['crop_y']),
                (active_crop['crop_x'] + active_crop['crop_w'],
                 active_crop['crop_y'] + active_crop['crop_h']),
                crop_color,
                crop_thickness
            )

            # Add crop info panel
            panel_height = 120
            panel = overlay.copy()
            cv2.rectangle(panel,
                         (active_crop['crop_x'], active_crop['crop_y'] - panel_height),
                         (active_crop['crop_x'] + 450, active_crop['crop_y']),
                         (0, 0, 0), -1)
            cv2.addWeighted(panel, 0.6, overlay, 0.4, 0, overlay)

            # Crop info
            y_offset = active_crop['crop_y'] - 90
            cv2.putText(overlay, f"Keyframe #{active_keyframe_idx}",
                       (active_crop['crop_x'] + 10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

            y_offset += 20
            cv2.putText(overlay, f"Position: ({active_crop['crop_x']}, {active_crop['crop_y']})",
                       (active_crop['crop_x'] + 10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

            y_offset += 20
            cv2.putText(overlay, f"Size: {active_crop['crop_w']}x{active_crop['crop_h']}",
                       (active_crop['crop_x'] + 10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

            y_offset += 20
            kf_source = active_crop.get('source', 'transcript')
            source_color = (255, 255, 0) if kf_source == 'motion' else (255, 255, 255)
            cv2.putText(overlay, f"Source: {kf_source.upper()}",
                       (active_crop['crop_x'] + 10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, source_color, 2)

            y_offset += 20
            cv2.putText(overlay, f"Time: {active_crop['timestamp']:.2f}s",
                       (active_crop['crop_x'] + 10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

            # Draw target face center if available
            if 'face_center' in active_crop and active_crop['face_center']:
                face_cx, face_cy = active_crop['face_center']
                cv2.circle(overlay, (face_cx, face_cy), 10, (255, 255, 0), 2)
                cv2.putText(overlay, "Target", (face_cx + 15, face_cy),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

            # New keyframe indicator
            if is_keyframe_boundary:
                cv2.putText(
                    overlay,
                    ">>> NEW KEYFRAME! <<<",
                    (video_width // 2 - 150, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 255),
                    3
                )

        # Add legend with background
        legend_x = 10
        legend_y = 30
        legend_width = 400
        legend_height = 160

        legend_panel = overlay.copy()
        cv2.rectangle(legend_panel,
                     (legend_x, legend_y - 20),
                     (legend_x + legend_width, legend_y + legend_height),
                     (0, 0, 0), -1)
        cv2.addWeighted(legend_panel, 0.7, overlay, 0.3, 0, overlay)

        cv2.putText(overlay, "IMPROVED MEDIAPIPE DETECTION", (legend_x + 10, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.putText(overlay, "GREEN: Detected Faces (validated)", (legend_x + 10, legend_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(overlay, "BLUE: Active Crop Region", (legend_x + 10, legend_y + 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        cv2.putText(overlay, "YELLOW: Keyframe Boundary", (legend_x + 10, legend_y + 75),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
        cv2.putText(overlay, "RED: Face Center", (legend_x + 10, legend_y + 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        cv2.putText(overlay, "CYAN: Target Face", (legend_x + 10, legend_y + 125),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

        # Add frame info at bottom
        info_bg = overlay.copy()
        cv2.rectangle(info_bg, (0, video_height - 50), (video_width, video_height), (0, 0, 0), -1)
        cv2.addWeighted(info_bg, 0.7, overlay, 0.3, 0, overlay)

        info_text = f"Frame: {frame_num} | Time: {current_time:.2f}s"
        if active_keyframe_idx is not None:
            info_text += f" | KF: #{active_keyframe_idx}/{len(crop_timeline)-1}"

        faces_count = len(detections_by_frame.get(frame_num, []))
        info_text += f" | Faces: {faces_count}"

        cv2.putText(
            overlay,
            info_text,
            (10, video_height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

        out.write(overlay)
        frame_num += 1
        current_time = frame_num / fps

    cap.release()
    out.release()

    print(f"✅ Visualization saved to: {output_path}")
    print()
    print("=" * 80)
    print("VALIDATION CHECKLIST")
    print("=" * 80)
    print()
    print("Open the video and verify:")
    print("  ✅ GREEN boxes around all visible faces")
    print("  ✅ No false positives (boxes on non-faces)")
    print("  ✅ Small/distant faces are detected")
    print("  ✅ BLUE crop region follows the active speaker")
    print("  ✅ Smooth transitions between keyframes")
    print("  ✅ Hard cuts at speaker changes (yellow)")
    print()
    print("Improvements vs Original MediaPipe:")
    print("  ✓ Fewer false positives (validation layer)")
    print("  ✓ Better small face detection (full-range model)")
    print("  ✓ More stable tracking (temporal filtering)")
    print("  ✓ Higher confidence scores")
    print()

    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python tests/visualize_crop_improved.py <video_path> [duration]")
        print()
        print("Example:")
        print("  python tests/visualize_crop_improved.py video.mp4 30")
        print()
        print("This uses IMPROVED MediaPipe with:")
        print("  - Better validation (fewer false positives)")
        print("  - Full-range detection (better for small faces)")
        print("  - Temporal filtering (more stable)")
        sys.exit(1)

    video_path = sys.argv[1]
    max_duration = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0

    print()
    print("🚀 Using IMPROVED MediaPipe Face Detection")
    print("   Lambda-friendly (~30MB) with enhanced accuracy")
    print()

    success = visualize_crop_with_improved_detection(video_path, max_duration)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
