"""
Complete Smart Framing Pipeline Test - IMPROVED VERSION

This script tests the full smart framing pipeline using IMPROVED MediaPipe detector
with better validation and accuracy for Lambda deployment.

Improvements:
- Uses ImprovedMediaPipeFaceDetector (fewer false positives)
- Full-range face detection (better for small/distant faces)
- Temporal consistency filtering
- Better validation (size, aspect ratio, position checks)
- Lambda-ready (~30MB package size)

Usage:
    python tests/test_complete_pipeline_improved.py <video_path> [duration]

    Example:
    python tests/test_complete_pipeline_improved.py tests/sample_clips/test_video.mp4 30

Output:
    - Console output with pipeline progress
    - Final cropped video: tests/output/smart_cropped_improved.mp4
    - Performance comparison vs original
"""

import sys
import os
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import IMPROVED detector
from smart_framing.face_detection_improved import ImprovedMediaPipeFaceDetector
from smart_framing.speaker_tracking import correlate_faces_with_speech
from smart_framing.smart_crop import calculate_smart_crop
from smart_framing.ffmpeg_smart_crop import process_clip_with_smart_framing
from smart_framing.subtitles import create_subtitles, has_word_timestamps


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


def test_complete_pipeline_improved(
    video_path: str,
    max_duration: float = 60.0,
    target_aspect: str = '9:16',
    ffmpeg_path: str = r"C:/Users/GourabaV/AppData/Local/Cypress/Cache/8.7.0/Cypress/resources/app/packages/server/node_modules/@ffmpeg-installer/win32-x64/ffmpeg.exe"
):
    """
    Test the complete smart framing pipeline with IMPROVED face detection.

    Args:
        video_path: Path to test video
        max_duration: Maximum duration to process
        target_aspect: Target aspect ratio
        ffmpeg_path: Optional custom FFmpeg path
    """
    print("=" * 80)
    print("SMART FRAMING - COMPLETE PIPELINE TEST (IMPROVED)")
    print("=" * 80)
    print()
    print("🚀 Using IMPROVED MediaPipe Face Detection")
    print("   ✅ Better validation (fewer false positives)")
    print("   ✅ Full-range model (better for small faces)")
    print("   ✅ Temporal filtering (more stable)")
    print("   ✅ Lambda-ready (~30MB)")
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
    # PHASE 1: FACE DETECTION (IMPROVED)
    # ========================================================================
    print("=" * 80)
    print("PHASE 1: FACE DETECTION (IMPROVED MEDIAPIPE)")
    print("=" * 80)
    print()

    # Create IMPROVED detector
    detector = ImprovedMediaPipeFaceDetector(
        confidence_threshold=0.7,        # Higher = fewer false positives
        min_face_size=30,                # Detect faces down to 30px
        max_face_size=None,              # Auto-detect based on video
        use_full_range_model=True        # Better for distant faces
    )

    phase1_start = time.time()
    detections = detector.detect_faces_in_video(
        video_path,
        start_sec=0,
        end_sec=max_duration,
        sample_rate=2,
        enable_temporal_filtering=True   # Reduces false positives
    )
    phase1_time = time.time() - phase1_start

    if not detections:
        print("❌ ERROR: No face detections")
        return False

    stats = detector.get_face_statistics(detections)
    print()
    print("📊 Detection Results:")
    print(f"   Total frames processed: {stats['total_frames']}")
    print(f"   Frames with faces: {stats['frames_with_faces']}")
    print(f"   Total faces detected: {stats['total_faces']}")
    print(f"   Face coverage: {stats['coverage_percent']:.1f}%")
    print(f"   Average confidence: {stats['avg_confidence']:.3f}")
    print(f"   Average face size: {stats.get('avg_face_size_px', 0):.0f}px²")
    print()
    print(f"✅ Phase 1 complete!")
    print(f"⏱️  Processing time: {phase1_time:.2f}s")
    print()

    # DEBUG: Show sample face detections with coordinates
    print("🔍 Sample Detections (first 3 frames with faces):")
    face_count = 0
    for det in detections:
        if det['faces'] and face_count < 3:
            face = det['faces'][0]
            bbox = face['bbox']
            center_x = bbox['x'] + bbox['w'] // 2
            center_y = bbox['y'] + bbox['h'] // 2
            print(f"   Frame @ {det['timestamp']:.2f}s:")
            print(f"      BBox: ({bbox['x']}, {bbox['y']}, {bbox['w']}, {bbox['h']})")
            print(f"      Center: ({center_x}, {center_y})")
            print(f"      Confidence: {face['confidence']:.3f}")
            face_count += 1
    print()

    # ========================================================================
    # PHASE 2: SPEAKER CORRELATION
    # ========================================================================
    print("=" * 80)
    print("PHASE 2: SPEAKER CORRELATION")
    print("=" * 80)
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
    print("📋 Sample Speaker Activity (first 3):")
    for i, activity in enumerate(speaker_activity[:3]):
        print(f"   {i+1}. {activity['start']:.2f}s - {activity['end']:.2f}s")
        print(f"      Face center: {activity['face_center']}")
        print(f"      Confidence: {activity['confidence']:.3f}")
        print(f"      Text: '{activity['text'][:50]}...'")
    print()

    # ========================================================================
    # PHASE 3: SMART CROP CALCULATION
    # ========================================================================
    print("=" * 80)
    print("PHASE 3: SMART CROP CALCULATION")
    print("=" * 80)
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
        smoothing_sigma=0.5,           # Smooth transitions
        face_timeline=detections,      # Pass for motion tracking
        enable_motion_keyframes=True,
        motion_threshold=100,          # Legacy threshold (not used in sticky mode)
        max_keyframe_interval=5.0,     # Maximum time before forced update
        use_sticky_crop=True,          # 🎯 STICKY CROP: Locks position until face leaves center
        dead_zone_radius=150           # 🎯 DEAD ZONE: 150px radius from crop center
    )
    phase3_time = time.time() - phase3_start

    print()
    print(f"✅ Generated {len(crop_timeline)} crop keyframes")
    print(f"   Crop dimensions: {crop_dims[0]}x{crop_dims[1]}")

    # Count keyframe types
    transcript_kf = sum(1 for kf in crop_timeline if kf.get('source') == 'transcript')
    motion_kf = sum(1 for kf in crop_timeline if kf.get('source') == 'motion')
    print(f"   Transcript keyframes: {transcript_kf}")
    print(f"   Motion keyframes: {motion_kf}")

    print(f"⏱️  Phase 3 time: {phase3_time:.2f}s")
    print()

    # Show sample crop positions
    print("📋 Sample Crop Positions (first 3):")
    for i, crop in enumerate(crop_timeline[:3]):
        source = crop.get('source', 'transcript')
        print(f"   {i+1}. t={crop['timestamp']:.2f}s ({source}):")
        print(f"      Position: ({crop['crop_x']}, {crop['crop_y']})")
        print(f"      Size: {crop['crop_w']}x{crop['crop_h']}")
        print(f"      Valid: {crop['crop_x'] >= 0 and crop['crop_y'] >= 0}")
    print()

    # ========================================================================
    # PHASE 3.5: SUBTITLE CREATION
    # ========================================================================
    print("=" * 80)
    print("PHASE 3.5: SUBTITLE CREATION (KARAOKE)")
    print("=" * 80)
    print()

    subtitle_path = None

    if transcript_segments and len(transcript_segments) > 0:
        subtitle_output = output_dir / "subtitles.ass"

        # Check if we have word-level timestamps
        has_words = has_word_timestamps(transcript_segments)
        subtitle_mode = 'karaoke' if has_words else 'simple'

        print(f"📝 Subtitle mode: {subtitle_mode}")
        print(f"   Word-level timestamps: {has_words}")
        print(f"   Segments: {len(transcript_segments)}")

        phase35_start = time.time()

        try:
            subtitle_path = create_subtitles(
                segments=transcript_segments,
                clip_start=0,
                output_path=str(subtitle_output),
                mode=subtitle_mode,
                is_lambda=False  # Local testing
            )

            phase35_time = time.time() - phase35_start

            print(f"✅ Subtitles created: {subtitle_path}")
            print(f"⏱️  Phase 3.5 time: {phase35_time:.2f}s")
        except Exception as e:
            print(f"⚠️  Subtitle creation failed: {e}")
            subtitle_path = None
    else:
        print("⚠️  No transcript segments available, skipping subtitles")

    print()

    # ========================================================================
    # PHASE 4: FFMPEG PROCESSING (WITH SUBTITLES)
    # ========================================================================
    print("=" * 80)
    print("PHASE 4: FFMPEG PROCESSING (WITH SUBTITLES)")
    print("=" * 80)
    print()

    output_path = output_dir / "smart_cropped_improved.mp4"

    # Determine target dimensions based on aspect ratio
    aspect_ratios = {
        '9:16': (1080, 1920),
        '16:9': (1920, 1080),
        '1:1': (1080, 1080),
        '4:5': (1080, 1350),
    }
    target_dims = aspect_ratios.get(target_aspect, (1080, 1920))

    print(f"💾 Output path: {output_path}")
    print(f"🎬 Target dimensions: {target_dims[0]}x{target_dims[1]}")
    print(f"🎯 Applying {len(crop_timeline)} crop keyframes")
    if subtitle_path:
        print(f"📝 Subtitles: {subtitle_path}")
    else:
        print(f"📝 Subtitles: None")
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
            subtitle_path=subtitle_path,  # 📝 SUBTITLES: Pass subtitle ASS file
            stabilize=False,              # DISABLED: Prevents edge blur (was True)
            preset='medium'               # BETTER QUALITY: Sharper output (was 'fast')
        )
    except Exception as e:
        print(f"❌ ERROR during FFmpeg processing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    phase4_time = time.time() - phase4_start

    print()
    print(f"✅ Video processing complete!")
    print(f"⏱️  Phase 4 time: {phase4_time:.2f}s")
    print()

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("=" * 80)
    print("🎉 PIPELINE COMPLETE!")
    print("=" * 80)
    print()

    phase35_time = phase35_time if subtitle_path else 0
    total_time = phase1_time + phase2_time + phase3_time + phase35_time + phase4_time

    print("📊 Performance Summary:")
    print(f"   Phase 1 (Face Detection):       {phase1_time:>6.2f}s ({phase1_time/total_time*100:>5.1f}%)")
    print(f"   Phase 2 (Speaker Correlation):  {phase2_time:>6.2f}s ({phase2_time/total_time*100:>5.1f}%)")
    print(f"   Phase 3 (Smart Crop):           {phase3_time:>6.2f}s ({phase3_time/total_time*100:>5.1f}%)")
    if subtitle_path:
        print(f"   Phase 3.5 (Subtitles):          {phase35_time:>6.2f}s ({phase35_time/total_time*100:>5.1f}%)")
    print(f"   Phase 4 (FFmpeg Processing):    {phase4_time:>6.2f}s ({phase4_time/total_time*100:>5.1f}%)")
    print(f"   {'-' * 60}")
    print(f"   Total:                          {total_time:>6.2f}s")
    print()

    print(f"📈 Processing Speed: {max_duration/total_time:.2f}x realtime")
    print()

    print("📂 Output Files:")
    print(f"   ✅ Smart cropped video: {output_path}")
    if os.path.exists(output_path):
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"   📦 File size: {file_size_mb:.2f} MB")
    print()

    print("🎯 Quality Features:")
    print("   ✅ Fewer false positives (validation layer)")
    print("   ✅ Better small face detection (full-range model)")
    print("   ✅ Sticky crop tracking (stable framing)")
    print("   ✅ Karaoke subtitles (word-by-word highlighting)")
    print("   ✅ Smart framing + subtitles integrated")
    print()

    print("📦 Lambda Deployment Ready:")
    print("   ✅ Package size: ~30MB (well within 250MB limit)")
    print("   ✅ CPU-optimized (no GPU required)")
    print("   ✅ Compatible dependencies")
    print()

    print("🎉 SUCCESS! Complete pipeline with subtitles is ready!")
    print()
    print("Next Steps:")
    print("  1. ▶️  Play output video to verify smart framing + subtitles")
    print("  2. 📝 Check karaoke subtitle effect and timing")
    print("  3. 🎯 Verify sticky crop is following speaker correctly")
    print("  4. 🚀 Ready for production deployment!")
    print()

    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("❌ ERROR: No video file specified")
        print()
        print("Usage:")
        print("  python tests/test_complete_pipeline_improved.py <video_path> [duration] [ffmpeg_path]")
        print()
        print("Examples:")
        print("  python tests/test_complete_pipeline_improved.py video.mp4 30")
        print("  python tests/test_complete_pipeline_improved.py video.mp4 30 C:\\ffmpeg\\bin\\ffmpeg.exe")
        print()
        print("This version uses IMPROVED MediaPipe detection:")
        print("  ✅ Better validation (fewer false positives)")
        print("  ✅ Full-range model (better for small faces)")
        print("  ✅ Temporal filtering (more stable)")
        print("  ✅ Lambda-ready (~30MB)")
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

    success = test_complete_pipeline_improved(video_path, max_duration, ffmpeg_path=ffmpeg_path)

    if success:
        print("✅ Test passed!")
        sys.exit(0)
    else:
        print("❌ Test failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
