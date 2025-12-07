"""
Complete Smart Framing Pipeline Test

This script tests the full smart framing pipeline from face detection
through speaker correlation, smart crop calculation, and final FFmpeg processing.

Usage:
    python tests/test_complete_pipeline.py <video_path> [duration]

    Example:
    python tests/test_complete_pipeline.py tests/sample_clips/test_video.mp4 30

Output:
    - Console output with pipeline progress
    - Final cropped video: tests/output/smart_cropped_video.mp4
    - Annotated video (optional): tests/output/annotated_video.mp4
"""

import sys
import os
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smart_framing.face_detection import FaceDetector
from smart_framing.speaker_tracking import correlate_faces_with_speech
from smart_framing.smart_crop import calculate_smart_crop
from smart_framing.ffmpeg_smart_crop import process_clip_with_smart_framing


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
    """
    Create mock transcript segments for testing (fallback).

    Args:
        duration: Video duration in seconds
        num_segments: Number of transcript segments to create

    Returns:
        List of mock transcript segments
    """
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


def test_complete_pipeline(
    video_path: str,
    max_duration: float = 60.0,
    target_aspect: str = '9:16',
    ffmpeg_path: str = None
):
    """
    Test the complete smart framing pipeline.

    Args:
        video_path: Path to test video
        max_duration: Maximum duration to process
        target_aspect: Target aspect ratio
    """
    print("=" * 70)
    print("SMART FRAMING - COMPLETE PIPELINE TEST")
    print("=" * 70)
    print()

    # Verify video exists
    if not os.path.exists(video_path):
        print(f"❌ ERROR: Video file not found: {video_path}")
        return False

    # Set FFmpeg path if provided
    if ffmpeg_path:
        os.environ['FFMPEG_PATH'] = ffmpeg_path
        print(f"🔧 Using custom FFmpeg: {ffmpeg_path}")

    print(f"📹 Video file: {video_path}")
    print(f"🎯 Target aspect ratio: {target_aspect}")
    print(f"⏱️  Processing duration: {max_duration}s")
    print()

    # Setup output directory
    output_dir = Path("tests/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # PHASE 1: FACE DETECTION
    # ========================================================================
    print("=" * 70)
    print("PHASE 1: FACE DETECTION")
    print("=" * 70)
    print()

    detector = FaceDetector(confidence_threshold=0.6)

    phase1_start = time.time()
    detections = detector.detect_faces_in_video(
        video_path,
        start_sec=0,
        end_sec=max_duration,
        sample_rate=2
    )
    phase1_time = time.time() - phase1_start

    if not detections:
        print("❌ ERROR: No face detections")
        return False

    stats = detector.get_face_statistics(detections)
    print()
    print(f"✅ Detected faces in {stats['total_frames']} frames")
    print(f"✅ Face coverage: {stats['coverage_percent']:.1f}%")
    print(f"✅ Average confidence: {stats['avg_confidence']:.2f}")
    print(f"⏱️  Phase 1 time: {phase1_time:.2f}s")
    print()

    # DEBUG: Show sample face detections with coordinates
    print("🔍 DEBUG - Sample Face Detections (first 3 frames with faces):")
    face_count = 0
    for det in detections:
        if det['faces'] and face_count < 3:
            face = det['faces'][0]
            bbox = face['bbox']
            center_x = bbox['x'] + bbox['w'] // 2
            center_y = bbox['y'] + bbox['h'] // 2
            print(f"   Frame @ {det['timestamp']:.2f}s: bbox=({bbox['x']}, {bbox['y']}, {bbox['w']}, {bbox['h']}), center=({center_x}, {center_y}), conf={face['confidence']:.2f}")
            face_count += 1
    print()

    # ========================================================================
    # PHASE 2: SPEAKER CORRELATION
    # ========================================================================
    print("=" * 70)
    print("PHASE 2: SPEAKER CORRELATION")
    print("=" * 70)
    print()

    # Load real transcript or create mock
    print("📝 Loading transcript...")

    # Try to find transcript file in same directory as video
    video_dir = os.path.dirname(video_path)
    transcript_path = os.path.join(video_dir, "transription.json")  # Note: typo in original filename

    if not os.path.exists(transcript_path):
        # Try alternative spelling
        transcript_path = os.path.join(video_dir, "transcription.json")

    transcript_segments = load_transcript_from_file(transcript_path, max_duration)
    print()

    phase2_start = time.time()
    speaker_activity = correlate_faces_with_speech(
        detections,
        transcript_segments,
        clip_start=0
    )
    phase2_time = time.time() - phase2_start

    if not speaker_activity:
        print("⚠️  WARNING: No speaker activity identified")
        print("   Using center crop fallback")
        print()

    print(f"✅ Identified {len(speaker_activity)} speaker activity periods")
    print(f"⏱️  Phase 2 time: {phase2_time:.2f}s")
    print()

    # Show sample speaker activity
    print("📋 Sample speaker activity (first 3):")
    for i, activity in enumerate(speaker_activity[:3]):
        print(f"   {i+1}. {activity['start']:.2f}s-{activity['end']:.2f}s: "
              f"Face at {activity['face_center']}, "
              f"confidence={activity['confidence']:.2f}")
    print()

    # DEBUG: Detailed speaker activity
    print("🔍 DEBUG - Detailed Speaker Activity (first 3):")
    for i, activity in enumerate(speaker_activity[:3]):
        print(f"   Segment {i+1}:")
        print(f"      Time: {activity['start']:.2f}s to {activity['end']:.2f}s")
        print(f"      Face center: {activity['face_center']}")
        print(f"      Face bbox: {activity['face_bbox']}")
        print(f"      Confidence: {activity['confidence']:.2f}")
        print(f"      Text: '{activity['text'][:40]}...'")
    print()

    # ========================================================================
    # PHASE 3: SMART CROP CALCULATION
    # ========================================================================
    print("=" * 70)
    print("PHASE 3: SMART CROP CALCULATION")
    print("=" * 70)
    print()

    # Get video dimensions from the video file
    import cv2
    cap = cv2.VideoCapture(video_path)
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    print(f"📐 Video dimensions: {video_width}x{video_height}")
    print()

    phase3_start = time.time()
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
    phase3_time = time.time() - phase3_start

    print()
    print(f"✅ Generated {len(crop_timeline)} crop keyframes")
    print(f"✅ Crop dimensions: {crop_dims[0]}x{crop_dims[1]}")
    print(f"⏱️  Phase 3 time: {phase3_time:.2f}s")
    print()

    # Show sample crop positions
    print("📋 Sample crop positions (first 3):")
    for i, crop in enumerate(crop_timeline[:3]):
        print(f"   {i+1}. t={crop['timestamp']:.2f}s: "
              f"x={crop['crop_x']}, y={crop['crop_y']}")
    print()

    # DEBUG: Detailed crop positions with validation
    print("🔍 DEBUG - Detailed Crop Positions (first 3):")
    for i, crop in enumerate(crop_timeline[:3]):
        print(f"   Keyframe {i+1}:")
        print(f"      Timestamp: {crop['timestamp']:.2f}s")
        print(f"      Crop position: ({crop['crop_x']}, {crop['crop_y']})")
        print(f"      Crop size: {crop['crop_w']}x{crop['crop_h']}")
        print(f"      Crop bounds: x={crop['crop_x']} to {crop['crop_x']+crop['crop_w']}, y={crop['crop_y']} to {crop['crop_y']+crop['crop_h']}")
        print(f"      Video bounds: {video_width}x{video_height}")
        print(f"      Valid: {crop['crop_x'] >= 0 and crop['crop_y'] >= 0 and crop['crop_x']+crop['crop_w'] <= video_width and crop['crop_y']+crop['crop_h'] <= video_height}")
        if 'speaker_text' in crop:
            print(f"      Text: '{crop['speaker_text']}'")
    print()

    # ========================================================================
    # PHASE 4: FFMPEG PROCESSING
    # ========================================================================
    print("=" * 70)
    print("PHASE 4: FFMPEG PROCESSING")
    print("=" * 70)
    print()

    output_path = output_dir / "smart_cropped_video.mp4"

    # Determine target dimensions based on aspect ratio
    aspect_ratios = {
        '9:16': (1080, 1920),
        '16:9': (1920, 1080),
        '1:1': (1080, 1080),
    }
    target_dims = aspect_ratios.get(target_aspect, (1080, 1920))

    print(f"💾 Output path: {output_path}")
    print(f"🎬 Target dimensions: {target_dims[0]}x{target_dims[1]}")
    print(f"🎯 Applying {len(crop_timeline)} crop keyframes")
    print()

    phase4_start = time.time()
    try:
        process_clip_with_smart_framing(
            video_path=video_path,
            output_path=str(output_path),
            clip_start=0,
            clip_end=max_duration,
            crop_timeline=crop_timeline,
            crop_dims=crop_dims,
            target_dims=target_dims,
            subtitle_path=None,  # No subtitles for now
            stabilize=True,
            preset='fast'
        )
    except Exception as e:
        print(f"❌ ERROR during FFmpeg processing: {str(e)}")
        return False

    phase4_time = time.time() - phase4_start

    print()
    print(f"✅ Video processing complete!")
    print(f"⏱️  Phase 4 time: {phase4_time:.2f}s")
    print()

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("=" * 70)
    print("PIPELINE COMPLETE!")
    print("=" * 70)
    print()

    total_time = phase1_time + phase2_time + phase3_time + phase4_time

    print("📊 Performance Summary:")
    print(f"   Phase 1 (Face Detection):     {phase1_time:.2f}s ({phase1_time/total_time*100:.1f}%)")
    print(f"   Phase 2 (Speaker Correlation): {phase2_time:.2f}s ({phase2_time/total_time*100:.1f}%)")
    print(f"   Phase 3 (Smart Crop Calc):     {phase3_time:.2f}s ({phase3_time/total_time*100:.1f}%)")
    print(f"   Phase 4 (FFmpeg Processing):   {phase4_time:.2f}s ({phase4_time/total_time*100:.1f}%)")
    print(f"   {'─' * 50}")
    print(f"   Total:                         {total_time:.2f}s")
    print()

    print(f"📈 Processing Speed: {max_duration/total_time:.2f}x realtime")
    print()

    print("📂 Output Files:")
    print(f"   ✅ Smart cropped video: {output_path}")
    print()

    print("🎉 SUCCESS! Smart framing pipeline is working!")
    print()
    print("Next steps:")
    print("  1. Open the cropped video to verify quality")
    print("  2. Test with different videos and durations")
    print("  3. Adjust smoothing and crop parameters if needed")
    print("  4. Ready for Lambda integration!")
    print()

    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("❌ ERROR: No video file specified")
        print()
        print("Usage:")
        print("  python tests/test_complete_pipeline.py <video_path> [duration] [ffmpeg_path]")
        print()
        print("Examples:")
        print("  python tests/test_complete_pipeline.py tests/sample_clips/test_video.mp4 30")
        print("  python tests/test_complete_pipeline.py tests/sample_clips/test_video.mp4 30 C:\\ffmpeg\\bin\\ffmpeg.exe")
        print()
        sys.exit(1)

    video_path = sys.argv[1]

    # Optional duration parameter
    max_duration = 60.0
    if len(sys.argv) > 2:
        try:
            max_duration = float(sys.argv[2])
        except ValueError:
            print(f"⚠️  WARNING: Invalid duration '{sys.argv[2]}', using default (60s)")

    # Optional FFmpeg path parameter
    ffmpeg_path = None
    if len(sys.argv) > 3:
        ffmpeg_path = sys.argv[3]

    success = test_complete_pipeline(video_path, max_duration, ffmpeg_path=ffmpeg_path)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
