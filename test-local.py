#!/usr/bin/env python3
"""
Local test script with classification system
Usage:
1. Place input video at: test-data/input.mp4
2. Run: docker run --rm -v "%CD%/test-data:/data" -v "%CD%/test-output:/output" opus-process-clip:latest python /var/task/test-local.py
"""
import sys
sys.path.insert(0, '/var/task')
import json
import os

# Test video processing with classification and smart framing
from lambda_function import (
    process_clip_with_smart_framing_lambda,
    process_clip_with_karaoke_subtitles,
    process_clip_with_simple_subtitles,
    extract_clip_no_subs,
    get_video_dimensions
)

# Try to load classification system
try:
    from classification_integration import (
        initialize_classification,
        classify_and_configure_processing
    )
    CLASSIFICATION_AVAILABLE = True
    print("[Test] Classification system available")
except ImportError as e:
    CLASSIFICATION_AVAILABLE = False
    print(f"[Test] Classification not available: {e}")

# Load test event from JSON file
with open('/test-event.json', 'r') as f:
    event = json.load(f)

clip = event['clip']

video_path = '/data/input.mp4'
output_path = '/output/output.mp4'

print(f"Processing {video_path}...")
print(f"Clip: {clip['start']}s - {clip['end']}s")

# Detect actual video dimensions
video_width, video_height = get_video_dimensions(video_path)
print(f"Detected video dimensions: {video_width}x{video_height}")

# Initialize and run classification
processing_config = None
if CLASSIFICATION_AVAILABLE:
    print("\n[Test] Running classification...")
    classification_service = initialize_classification()

    if classification_service:
        processing_config = classify_and_configure_processing(
            service=classification_service,
            clip_info=clip,
            video_path=video_path,  # Full classification with video
            use_quick_mode=False
        )

        if processing_config and processing_config.get('classified'):
            print(f"\n[Test] ✓ Classification Results:")
            print(f"  Category: {processing_config['category']}")
            print(f"  Confidence: {processing_config['confidence']:.2f}")
            print(f"  Smart framing recommended: {processing_config['use_smart_framing']}")
            print(f"  Subtitle mode: {processing_config['subtitle_mode']}")
            print(f"  Primary aspect ratio: {processing_config['primary_ratio']}")
        else:
            print("[Test] No classification detected, using defaults")
    else:
        print("[Test] Classification service failed to initialize")

print(f"\n[Test] Starting video processing...\n")

try:
    # Get processing settings from classification or defaults
    use_smart_framing = processing_config.get('use_smart_framing', True) if processing_config else True
    subtitle_mode = processing_config.get('subtitle_mode', 'karaoke') if processing_config else 'karaoke'
    aspect_ratio = processing_config.get('primary_ratio', '9:16') if processing_config else '9:16'

    # Check if we have word-level timestamps for karaoke
    has_word_timestamps = (
        clip.get('segments') and
        any(seg.get('words') for seg in clip['segments'])
    )

    # Apply classification-based processing strategy
    if subtitle_mode == 'none':
        # No subtitles (e.g., dance videos)
        print(f"[Test] Processing without subtitles (recommended by classifier)")
        extract_clip_no_subs(
            video_path, clip['start'], clip['end'],
            output_path, aspect_ratio,
            video_width, video_height
        )
    elif use_smart_framing and os.environ.get('ENABLE_SMART_FRAMING', 'false').lower() == 'true':
        # Smart framing with subtitles
        print(f"[Test] Processing with SMART FRAMING (recommended by classifier)")
        process_clip_with_smart_framing_lambda(
            video_path=video_path,
            clip=clip,
            output_path=output_path,
            aspect_ratio=aspect_ratio,
            video_width=video_width,
            video_height=video_height,
            is_lambda=False
        )
    elif subtitle_mode == 'karaoke' and has_word_timestamps:
        # Karaoke subtitles
        print(f"[Test] Processing with KARAOKE subtitles (recommended by classifier)")
        process_clip_with_karaoke_subtitles(
            video_path, clip, output_path,
            aspect_ratio, video_width, video_height,
            is_lambda=False, template={}
        )
    elif subtitle_mode == 'simple' or (subtitle_mode == 'karaoke' and not has_word_timestamps):
        # Simple subtitles
        print(f"[Test] Processing with SIMPLE subtitles (recommended by classifier)")
        process_clip_with_simple_subtitles(
            video_path, clip, output_path,
            aspect_ratio, video_width, video_height,
            is_lambda=False, template={}
        )
    else:
        # Fallback: no subtitles
        print(f"[Test] Processing without subtitles (fallback)")
        extract_clip_no_subs(
            video_path, clip['start'], clip['end'],
            output_path, aspect_ratio,
            video_width, video_height
        )

    # Check output file size
    import os
    if os.path.exists(output_path):
        size = os.path.getsize(output_path)
        print(f"\n✓ Success! Output: {output_path}")
        print(f"File size: {size:,} bytes ({size/1024/1024:.2f} MB)")
        if size < 1000:
            print("⚠ WARNING: File is very small, likely corrupted!")
    else:
        print(f"\n✗ Error: Output file not created at {output_path}")
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
