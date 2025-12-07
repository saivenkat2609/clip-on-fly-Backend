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
    smart_crop: Calculate dynamic crop coordinates
    ffmpeg_smart_crop: Generate FFmpeg filters and process videos
"""

__version__ = "0.3.0"
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

    # Smart crop
    'calculate_smart_crop',
    'calculate_center_crop',
    'smooth_crop_transitions',
    'ASPECT_RATIOS',

    # FFmpeg integration
    'process_clip_with_smart_framing',
    'generate_crop_filter_expression',
    'build_ffmpeg_command',
]
