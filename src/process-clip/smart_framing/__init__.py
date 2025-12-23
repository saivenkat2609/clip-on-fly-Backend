"""
Smart Framing Module for Opus Clip

This module provides face detection and intelligent video cropping capabilities
for focusing videos on active speakers.

Modules:
    face_detection: Core face detection using MediaPipe
    face_detection_improved: Enhanced MediaPipe with validation
    face_detection_retinaface: RetinaFace for maximum accuracy
    face_detector_factory: Unified interface for all detectors
    speaker_tracking: Correlate faces with speech timestamps
    smart_crop: Calculate dynamic crop coordinates with sticky crop support
    ffmpeg_smart_crop: Generate FFmpeg filters and process videos
    subtitles: Create karaoke and simple ASS subtitle files
"""

__version__ = "0.4.0"
__author__ = "Opus Clip Team"

# Phase 1: Face detection
from .face_detection import FaceDetector

# Enhanced face detection (v0.3.0+)
from .face_detector_factory import create_detector, FaceDetectorFactory

# Phase 2: Speaker correlation and smart cropping
from .speaker_tracking import (
    correlate_faces_with_speech,
    detect_multi_speaker_segments,
    identify_primary_speaker
)

from .smart_crop import (
    calculate_smart_crop,
    calculate_center_crop,
    smooth_crop_transitions,
    ASPECT_RATIOS
)

from .ffmpeg_smart_crop import (
    process_clip_with_smart_framing,
    generate_crop_filter_expression,
    build_ffmpeg_command
)

# Phase 4: Subtitle generation (v0.4.0+)
from .subtitles import (
    create_karaoke_ass,
    create_simple_ass,
    create_subtitles,
    has_word_timestamps,
    escape_ass_text,
    format_ass_time
)

__all__ = [
    # Face detection (original)
    'FaceDetector',

    # Face detection (enhanced - v0.3.0+)
    'create_detector',
    'FaceDetectorFactory',

    # Speaker tracking
    'correlate_faces_with_speech',
    'detect_multi_speaker_segments',
    'identify_primary_speaker',

    # Smart crop (with sticky crop - v0.4.0+)
    'calculate_smart_crop',
    'calculate_center_crop',
    'smooth_crop_transitions',
    'ASPECT_RATIOS',

    # FFmpeg integration
    'process_clip_with_smart_framing',
    'generate_crop_filter_expression',
    'build_ffmpeg_command',

    # Subtitles (v0.4.0+)
    'create_karaoke_ass',
    'create_simple_ass',
    'create_subtitles',
    'has_word_timestamps',
    'escape_ass_text',
    'format_ass_time',
]
