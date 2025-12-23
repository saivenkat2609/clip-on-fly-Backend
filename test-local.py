#!/usr/bin/env python3
"""
Simple local test script for smart framing
Usage:
1. Place input video at: test-data/input.mp4
2. Run: docker run --rm -v "%CD%/test-data:/data" -v "%CD%/test-output:/output" opus-process-clip:latest python /var/task/test-local.py
"""
import sys
sys.path.insert(0, '/var/task')
import json

# Test video processing with SMART FRAMING
from lambda_function import process_clip_with_smart_framing_lambda, get_video_dimensions

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

try:
    # Use SMART FRAMING with face detection and speaker tracking
    process_clip_with_smart_framing_lambda(
        video_path=video_path,
        clip=clip,
        output_path=output_path,
        aspect_ratio='9:16',
        video_width=video_width,
        video_height=video_height,
        is_lambda=False
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
