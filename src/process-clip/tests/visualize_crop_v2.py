"""
Crop Validation Visualization Tool V2 - Sticky Speaker Tracking

This script visualizes the V2 sticky speaker tracking approach:
1. Detected face bounding boxes (green) for ALL faces
2. Calculated crop regions (blue) locked to one speaker
3. Speaker IDs and tracking info
4. Switch indicators when crop switches speakers

This helps validate sticky speaker logic and movement-based switching.

Usage:
    python tests/visualize_crop_v2.py <video_path> <duration>
"""

import sys
import os
import cv2
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smart_framing.face_detection import FaceDetector
from smart_framing.speaker_tracking import correlate_faces_with_speech
from smart_framing.smart_crop_v2 import calculate_smart_crop


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


def visualize_crop_validation(
    video_path: str,
    max_duration: float = 30.0,
    target_aspect: str = '9:16'
):
    """
    Create visualization showing faces and crop regions.

    Args:
        video_path: Path to video file
        max_duration: Duration to process
        target_aspect: Target aspect ratio
    """
    print("=" * 70)
    print("CROP VALIDATION VISUALIZATION")
    print("=" * 70)
    print()

    if not os.path.exists(video_path):
        print(f"❌ ERROR: Video not found: {video_path}")
        return False

    output_dir = Path("tests/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Detect faces
    print("🔍 Step 1: Detecting faces...")
    detector = FaceDetector(confidence_threshold=0.6)
    detections = detector.detect_faces_in_video(
        video_path,
        start_sec=0,
        end_sec=max_duration,
        sample_rate=2
    )
    print(f"✅ Detected faces in {len(detections)} frames")
    print()

    # Step 2: Correlate with speech
    print("📝 Step 2: Loading transcript and correlating...")

    # Try to find transcript file in same directory as video
    video_dir = os.path.dirname(video_path)
    transcript_path = os.path.join(video_dir, "transription.json")  # Note: typo in original filename

    if not os.path.exists(transcript_path):
        # Try alternative spelling
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
    print("📐 Step 3: Calculating crop positions...")
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
        smoothing_sigma=0.5,  # Speech-first: hard cuts at speaker boundaries, light smoothing within segments
        face_timeline=detections,  # Pass face timeline for motion tracking
        enable_motion_keyframes=True,
        motion_threshold=100,  # 100px movement triggers keyframe
        max_keyframe_interval=3.0  # Max 3 seconds between keyframes
    )
    print(f"✅ Generated {len(crop_timeline)} crop keyframes")
    print(f"   Crop size: {crop_dims[0]}x{crop_dims[1]}")
    print()

    # Step 4: Create visualization
    print("🎨 Step 4: Creating visualization video (V2 - Sticky Speaker Tracking)...")
    output_path = output_dir / "crop_validation_v2.mp4"

    cap = cv2.VideoCapture(video_path)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (video_width, video_height))

    # Create lookup dicts
    detections_by_frame = {d['frame_num']: d['faces'] for d in detections}

    # Create crop lookup by timestamp
    crop_by_time = {}
    for crop in crop_timeline:
        crop_by_time[crop['timestamp']] = crop

    frame_num = 0
    current_time = 0
    current_keyframe_idx = 0

    # Print keyframe summary
    print(f"📊 Keyframe Summary:")
    print(f"   Total keyframes: {len(crop_timeline)}")
    for i, kf in enumerate(crop_timeline[:10]):  # Show first 10
        print(f"   KF{i}: t={kf['timestamp']:.2f}s, pos=({kf['crop_x']}, {kf['crop_y']})")
    if len(crop_timeline) > 10:
        print(f"   ... and {len(crop_timeline) - 10} more")
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
            for face in faces:
                bbox = face['bbox']
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

                # Add confidence label
                conf_text = f"{face['confidence']:.2f}"
                cv2.putText(
                    overlay,
                    conf_text,
                    (bbox['x'], bbox['y'] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

        # Find active crop region for this timestamp
        # IMPORTANT: Match FFmpeg's range-based logic (step function, not nearest)
        active_crop = None
        active_keyframe_idx = None
        is_keyframe_boundary = False

        for i, crop in enumerate(crop_timeline):
            # Determine the time range for this crop keyframe
            start_time = crop['timestamp']
            if i + 1 < len(crop_timeline):
                end_time = crop_timeline[i + 1]['timestamp']
            else:
                end_time = start_time + 999  # Last keyframe extends to end

            # Check if current time falls within this range
            if start_time <= current_time < end_time:
                active_crop = crop
                active_keyframe_idx = i

                # Check if we just entered this keyframe (within 0.1s)
                if abs(current_time - start_time) < 0.1:
                    is_keyframe_boundary = True
                    if i != current_keyframe_idx:
                        print(f"⏱️  Keyframe {i} active at t={current_time:.2f}s: crop=({crop['crop_x']}, {crop['crop_y']})")
                        current_keyframe_idx = i
                break

        # Draw crop region (BLUE) - ALWAYS show if we have an active crop
        if active_crop:
            # Main crop rectangle
            crop_color = (255, 255, 0) if is_keyframe_boundary else (255, 0, 0)  # Yellow at boundaries, Blue otherwise
            crop_thickness = 5 if is_keyframe_boundary else 3

            cv2.rectangle(
                overlay,
                (active_crop['crop_x'], active_crop['crop_y']),
                (active_crop['crop_x'] + active_crop['crop_w'],
                 active_crop['crop_y'] + active_crop['crop_h']),
                crop_color,
                crop_thickness
            )

            # Add crop info panel (semi-transparent background)
            panel_height = 90
            panel = overlay.copy()
            cv2.rectangle(panel,
                         (active_crop['crop_x'], active_crop['crop_y'] - panel_height),
                         (active_crop['crop_x'] + 400, active_crop['crop_y']),
                         (0, 0, 0), -1)
            cv2.addWeighted(panel, 0.6, overlay, 0.4, 0, overlay)

            # Crop position label
            crop_label = f"Keyframe #{active_keyframe_idx}: ({active_crop['crop_x']}, {active_crop['crop_y']})"
            cv2.putText(
                overlay,
                crop_label,
                (active_crop['crop_x'] + 10, active_crop['crop_y'] - 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                2
            )

            # Crop dimensions
            dims_label = f"Size: {active_crop['crop_w']}x{active_crop['crop_h']}"
            cv2.putText(
                overlay,
                dims_label,
                (active_crop['crop_x'] + 10, active_crop['crop_y'] - 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                2
            )

            # Keyframe timestamp and source
            kf_time_label = f"KF Time: {active_crop['timestamp']:.2f}s"
            kf_source = active_crop.get('source', 'transcript')
            if kf_source == 'motion':
                kf_time_label += f" [MOTION]"
            cv2.putText(
                overlay,
                kf_time_label,
                (active_crop['crop_x'] + 10, active_crop['crop_y'] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                2
            )

            # DEBUG: Draw face center if available
            if 'face_center' in active_crop and active_crop['face_center'] is not None:
                face_cx, face_cy = active_crop['face_center']
                # Draw larger cyan circle for face center from keyframe
                cv2.circle(overlay, (face_cx, face_cy), 10, (255, 255, 0), 2)  # Cyan circle
                cv2.putText(overlay, "KF Face", (face_cx + 15, face_cy),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

            # Add "NEW KEYFRAME!" indicator at boundaries
            if is_keyframe_boundary:
                cv2.putText(
                    overlay,
                    ">>> NEW KEYFRAME! <<<",
                    (video_width // 2 - 150, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 255),  # Cyan
                    3
                )

        # Add legend
        legend_y = 30
        cv2.putText(overlay, "GREEN: Face Detection", (10, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(overlay, "BLUE: Crop Region (Active)", (10, legend_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        cv2.putText(overlay, "YELLOW: Keyframe Boundary", (10, legend_y + 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
        cv2.putText(overlay, "RED: Detected Face Center", (10, legend_y + 75),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        cv2.putText(overlay, "CYAN: Keyframe Face Target", (10, legend_y + 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

        # Add frame info at bottom
        info_text = f"Frame: {frame_num} | Time: {current_time:.2f}s"
        if active_keyframe_idx is not None:
            info_text += f" | Active KF: #{active_keyframe_idx}/{len(crop_timeline)-1}"
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
    print("=" * 70)
    print("VALIDATION GUIDE")
    print("=" * 70)
    print()
    print("Open the visualization video and check:")
    print("  ✅ GREEN boxes should surround faces")
    print("  ✅ BLUE box (crop region) should center on face")
    print("  ✅ RED dot should be at face center")
    print("  ✅ BLUE box should follow face movement")
    print()
    print("If the BLUE box is at (0,0) or doesn't follow faces:")
    print("  ❌ Problem in speaker correlation or crop calculation")
    print()

    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python tests/visualize_crop.py <video_path> [duration]")
        print("Example: python tests/visualize_crop.py tests/sample_clips/test_video.mp4 30")
        sys.exit(1)

    video_path = sys.argv[1]
    max_duration = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0

    success = visualize_crop_validation(video_path, max_duration)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
