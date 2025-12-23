"""
FFmpeg Smart Crop Integration Module

This module generates FFmpeg filter expressions for dynamic cropping
and processes videos with smart framing.

Key Features:
- Generates timeline-based crop filters
- Supports dynamic crop positions over time
- Integrates stabilization (optional)
- Handles subtitle overlays
- Optimized for Lambda execution
"""

import subprocess
import os
from typing import List, Dict, Tuple, Optional
from .ffmpeg_smart_crop_optimized import optimize_crop_timeline


# FFmpeg binary path (get from environment or use Lambda default)
FFMPEG_PATH = os.environ.get('FFMPEG_PATH', '/usr/local/bin/ffmpeg')

print(f"[FFmpegSmartCrop] Using FFmpeg binary at: {FFMPEG_PATH}")
def process_clip_with_smart_framing(
    video_path: str,
    output_path: str,
    clip_start: float,
    clip_end: float,
    crop_timeline: List[Dict],
    crop_dims: Tuple[int, int],
    target_dims: Tuple[int, int],
    subtitle_path: Optional[str] = None,
    stabilize: bool = True,
    preset: str = 'fast'
) -> str:
    """
    Process video clip with smart framing using FFmpeg.

    This is the main function that takes all the calculated crop data
    and executes FFmpeg to produce the final cropped video.

    Args:
        video_path: Input video file path
        output_path: Output video file path
        clip_start: Clip start time in seconds
        clip_end: Clip end time in seconds
        crop_timeline: Crop coordinates timeline from smart_crop module
        crop_dims: (crop_width, crop_height) from smart_crop module
        target_dims: (target_width, target_height) for final output
        subtitle_path: Optional subtitle file path (.ass or .srt)
        stabilize: Whether to apply stabilization
        preset: FFmpeg encoding preset ('ultrafast', 'fast', 'medium')

    Returns:
        Path to processed video file

    Raises:
        Exception: If FFmpeg processing fails
    """
    print(f"[FFmpegSmartCrop] Processing clip: {clip_start:.2f}s to {clip_end:.2f}s")
    print(f"[FFmpegSmartCrop] Crop: {crop_dims}, Target: {target_dims}")
    print(f"[FFmpegSmartCrop] Keyframes: {len(crop_timeline)}")

    crop_w, crop_h = crop_dims
    target_w, target_h = target_dims

    # OPTIMIZE: Limit keyframes to prevent FFmpeg expression overflow
    crop_timeline = optimize_crop_timeline(
        crop_timeline,
        max_keyframes=50,  # FFmpeg limit for nested expressions
        preserve_transcript_keyframes=True
    )

    # Build filter chain
    filters = []

    # 1. Smart crop filter
    crop_filter = generate_crop_filter_expression(
        crop_timeline,
        crop_w,
        crop_h,
        clip_start
    )
    filters.append(crop_filter)

    # 2. Scale to target dimensions with Lanczos (sharper than default)
    # flags=lanczos provides better quality scaling (sharper edges)
    scale_filter = f"scale={target_w}:{target_h}:flags=lanczos"
    filters.append(scale_filter)
    print(f"[FFmpegSmartCrop] Using Lanczos scaling for sharper output")

    # 3. Stabilization (optional)
    if stabilize:
        deshake_filter = "deshake=rx=16:ry=16"
        filters.append(deshake_filter)
        print(f"[FFmpegSmartCrop] Stabilization enabled")

    # 4. Subtitles (if provided)
    if subtitle_path and os.path.exists(subtitle_path):
        # Escape path for FFmpeg (Windows paths need special handling)
        subtitle_path_escaped = subtitle_path.replace('\\', '\\\\').replace(':', '\\:')
        subtitle_filter = f"subtitles='{subtitle_path_escaped}'"
        filters.append(subtitle_filter)
        print(f"[FFmpegSmartCrop] Subtitles: {subtitle_path}")

    # Combine all filters
    filter_complex = ','.join(filters)

    # Build FFmpeg command
    cmd = build_ffmpeg_command(
        video_path,
        output_path,
        clip_start,
        clip_end,
        filter_complex,
        preset
    )

    print(f"[FFmpegSmartCrop] Executing FFmpeg...")
    print(f"[FFmpegSmartCrop] Command: {' '.join(cmd[:10])}...")  # Print first part

    # Execute FFmpeg
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )

    if result.returncode != 0:
        print(f"[FFmpegSmartCrop] ERROR: FFmpeg failed")
        print(f"[FFmpegSmartCrop] STDERR: {result.stderr[-500:]}")  # Last 500 chars
        raise Exception(f"FFmpeg processing failed: {result.stderr[-200:]}")

    print(f"[FFmpegSmartCrop] ✓ Success: {output_path}")
    return output_path


def generate_crop_filter_expression(
    crop_timeline: List[Dict],
    crop_w: int,
    crop_h: int,
    clip_start: float
) -> str:
    """
    Generate FFmpeg crop filter with timeline-based positioning.

    Uses FFmpeg's expression system to dynamically adjust crop position
    based on timestamp.

    Args:
        crop_timeline: List of crop keyframes
        crop_w: Crop width
        crop_h: Crop height
        clip_start: Clip start time (to adjust timestamps)

    Returns:
        FFmpeg crop filter string
    """
    if len(crop_timeline) == 1:
        # Static crop (single position)
        crop = crop_timeline[0]
        return f"crop={crop_w}:{crop_h}:{crop['crop_x']}:{crop['crop_y']}"

    # Dynamic crop with timeline expressions
    return generate_timeline_crop_expression(
        crop_timeline,
        crop_w,
        crop_h,
        clip_start
    )


def generate_timeline_crop_expression(
    crop_timeline: List[Dict],
    crop_w: int,
    crop_h: int,
    clip_start: float
) -> str:
    """
    Generate timeline-based crop expression using FFmpeg's 'between' function.

    Example output:
        crop=w=1080:h=1920:x='if(between(t,0,5),540,if(between(t,5,10),640,740))':y='...'

    Args:
        crop_timeline: Crop keyframes
        crop_w: Crop width
        crop_h: Crop height
        clip_start: Clip start time

    Returns:
        FFmpeg crop filter with time-based expressions
    """
    # Build time-based if expressions
    x_conditions = []
    y_conditions = []

    for i, crop in enumerate(crop_timeline):
        # Adjust timestamp relative to clip start
        start_time = crop['timestamp']

        # Determine end time for this segment
        if i + 1 < len(crop_timeline):
            end_time = crop_timeline[i + 1]['timestamp']
        else:
            end_time = start_time + 999  # Large value for last segment

        # Create condition: between(t, start, end)
        condition = f"between(t,{start_time:.2f},{end_time:.2f})"

        x_conditions.append((condition, crop['crop_x']))
        y_conditions.append((condition, crop['crop_y']))

    # Build nested if expressions
    x_expr = build_nested_if_expression(x_conditions, crop_timeline[0]['crop_x'])
    y_expr = build_nested_if_expression(y_conditions, crop_timeline[0]['crop_y'])

    # FFmpeg crop filter
    return f"crop=w={crop_w}:h={crop_h}:x='{x_expr}':y='{y_expr}'"


def build_nested_if_expression(
    conditions: List[Tuple[str, int]],
    default_value: int
) -> str:
    """
    Build nested if expression for FFmpeg.

    Converts:
        [(cond1, val1), (cond2, val2), (cond3, val3)]
    Into:
        "if(cond1,val1,if(cond2,val2,if(cond3,val3,default)))"

    Args:
        conditions: List of (condition, value) tuples
        default_value: Fallback value

    Returns:
        Nested if expression string
    """
    if not conditions:
        return str(default_value)

    # Build from inside out
    expr = str(default_value)

    for condition, value in reversed(conditions):
        expr = f"if({condition},{value},{expr})"

    return expr


def build_ffmpeg_command(
    input_path: str,
    output_path: str,
    start_sec: float,
    end_sec: float,
    filter_complex: str,
    preset: str = 'fast'
) -> List[str]:
    """
    Build complete FFmpeg command with all parameters.

    Args:
        input_path: Input video path
        output_path: Output video path
        start_sec: Start time
        end_sec: End time
        filter_complex: Video filter string
        preset: Encoding preset

    Returns:
        List of command arguments
    """
    duration = end_sec - start_sec

    cmd = [
        FFMPEG_PATH,
        '-ss', str(start_sec),           # Seek to start position
        '-i', input_path,                 # Input file
        '-t', str(duration),              # Duration
        '-vf', filter_complex,            # Video filters
        '-c:v', 'libx264',               # Video codec
        '-preset', preset,                # Encoding preset
        '-crf', '20',                     # Quality (18-28, lower = better)
        '-pix_fmt', 'yuv420p',           # Pixel format (maximum compatibility)
        '-c:a', 'aac',                   # Audio codec
        '-b:a', '128k',                  # Audio bitrate
        '-ar', '44100',                  # Audio sample rate
        '-ac', '2',                      # Audio channels (stereo)
        '-max_muxing_queue_size', '1024', # Prevent muxing errors
        '-movflags', '+faststart',       # Web-optimized MP4
        '-threads', '0',                 # Use all CPU threads
        '-y',                            # Overwrite output
        output_path
    ]

    return cmd


def generate_simple_crop_filter(
    crop_x: int,
    crop_y: int,
    crop_w: int,
    crop_h: int,
    target_w: int,
    target_h: int
) -> str:
    """
    Generate simple static crop filter (fallback).

    Args:
        crop_x, crop_y: Crop position
        crop_w, crop_h: Crop dimensions
        target_w, target_h: Target output dimensions

    Returns:
        FFmpeg filter string
    """
    return f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={target_w}:{target_h}"


def validate_crop_parameters(
    crop_x: int,
    crop_y: int,
    crop_w: int,
    crop_h: int,
    video_width: int,
    video_height: int
) -> bool:
    """
    Validate crop parameters are within video bounds.

    Args:
        crop_x, crop_y: Crop position
        crop_w, crop_h: Crop dimensions
        video_width, video_height: Video dimensions

    Returns:
        True if valid, False otherwise
    """
    if crop_x < 0 or crop_y < 0:
        return False

    if crop_x + crop_w > video_width:
        return False

    if crop_y + crop_h > video_height:
        return False

    if crop_w <= 0 or crop_h <= 0:
        return False

    return True


def estimate_processing_time(
    duration: float,
    preset: str = 'fast',
    stabilize: bool = True
) -> float:
    """
    Estimate FFmpeg processing time.

    Args:
        duration: Clip duration in seconds
        preset: Encoding preset
        stabilize: Whether stabilization is enabled

    Returns:
        Estimated processing time in seconds
    """
    # Base processing speed (varies by preset)
    preset_multipliers = {
        'ultrafast': 0.3,  # ~0.3x duration
        'fast': 0.5,       # ~0.5x duration
        'medium': 0.8,     # ~0.8x duration
        'slow': 1.5        # ~1.5x duration
    }

    multiplier = preset_multipliers.get(preset, 0.5)

    # Stabilization adds ~20% overhead
    if stabilize:
        multiplier *= 1.2

    return duration * multiplier
