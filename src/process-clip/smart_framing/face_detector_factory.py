"""
Face Detector Factory

Unified interface for creating face detectors with different backends.
Allows easy switching between detection models based on requirements.

Supported backends:
- 'mediapipe': Original MediaPipe implementation
- 'mediapipe_improved': Enhanced MediaPipe with validation
- 'retinaface': RetinaFace for maximum accuracy

Usage:
    detector = FaceDetectorFactory.create('retinaface', confidence_threshold=0.7)
    detections = detector.detect_faces_in_video('video.mp4')
"""

from typing import Literal, Optional
from enum import Enum


class DetectorBackend(str, Enum):
    """Available face detection backends."""
    MEDIAPIPE = "mediapipe"
    MEDIAPIPE_IMPROVED = "mediapipe_improved"
    RETINAFACE = "retinaface"
    MTCNN = "mtcnn"  # Lambda-friendly, best balance


class FaceDetectorFactory:
    """
    Factory for creating face detector instances.

    Provides a unified interface to create different face detection models
    with consistent API.
    """

    @staticmethod
    def create(
        backend: str = "mtcnn",
        confidence_threshold: float = 0.9,
        min_face_size: int = 20,
        max_face_size: Optional[int] = None,
        **kwargs
    ):
        """
        Create a face detector with specified backend.

        Args:
            backend: Detection backend to use
                    - 'mtcnn': MTCNN (RECOMMENDED - Lambda-friendly, accurate, few false positives)
                    - 'mediapipe_improved': Enhanced MediaPipe (balanced)
                    - 'mediapipe': Original MediaPipe (fast, may have false positives)
                    - 'retinaface': RetinaFace (most accurate but TOO HEAVY for Lambda)
            confidence_threshold: Minimum confidence for detection (0.0-1.0)
                                Higher = fewer false positives, may miss some faces
                                Recommended: 0.9 for MTCNN, 0.7 for MediaPipe, 0.75 for RetinaFace
            min_face_size: Minimum face size in pixels to filter noise
            max_face_size: Maximum face size in pixels (None = auto-detect)
            **kwargs: Additional backend-specific parameters

        Returns:
            Face detector instance with unified API

        Example:
            # Create MTCNN detector (recommended for Lambda)
            detector = FaceDetectorFactory.create(
                backend='mtcnn',
                confidence_threshold=0.9,
                min_face_size=20
            )

            # Detect faces
            detections = detector.detect_faces_in_video('video.mp4')
        """
        backend = backend.lower()

        if backend == DetectorBackend.MEDIAPIPE:
            return FaceDetectorFactory._create_mediapipe(
                confidence_threshold,
                min_face_size,
                max_face_size,
                **kwargs
            )

        elif backend == DetectorBackend.MEDIAPIPE_IMPROVED:
            return FaceDetectorFactory._create_mediapipe_improved(
                confidence_threshold,
                min_face_size,
                max_face_size,
                **kwargs
            )

        elif backend == DetectorBackend.RETINAFACE:
            return FaceDetectorFactory._create_retinaface(
                confidence_threshold,
                min_face_size,
                max_face_size,
                **kwargs
            )

        elif backend == DetectorBackend.MTCNN:
            return FaceDetectorFactory._create_mtcnn(
                confidence_threshold,
                min_face_size,
                max_face_size,
                **kwargs
            )

        else:
            raise ValueError(
                f"Unknown backend '{backend}'. "
                f"Supported: {[b.value for b in DetectorBackend]}"
            )

    @staticmethod
    def _create_mediapipe(
        confidence_threshold: float,
        min_face_size: int,
        max_face_size: Optional[int],
        **kwargs
    ):
        """Create original MediaPipe detector."""
        from .face_detection import FaceDetector

        print(f"[Factory] Creating MediaPipe detector")
        print(f"  Note: Original MediaPipe may have false positives.")
        print(f"  Consider using 'mediapipe_improved' or 'retinaface' for better accuracy.")

        return FaceDetector(confidence_threshold=confidence_threshold)

    @staticmethod
    def _create_mediapipe_improved(
        confidence_threshold: float,
        min_face_size: int,
        max_face_size: Optional[int],
        **kwargs
    ):
        """Create improved MediaPipe detector."""
        from .face_detection_improved import ImprovedMediaPipeFaceDetector

        use_full_range = kwargs.get('use_full_range_model', True)

        print(f"[Factory] Creating Improved MediaPipe detector")
        return ImprovedMediaPipeFaceDetector(
            confidence_threshold=confidence_threshold,
            min_face_size=min_face_size,
            max_face_size=max_face_size,
            use_full_range_model=use_full_range
        )

    @staticmethod
    def _create_retinaface(
        confidence_threshold: float,
        min_face_size: int,
        max_face_size: Optional[int],
        **kwargs
    ):
        """Create RetinaFace detector."""
        from .face_detection_retinaface import RetinaFaceDetector

        nms_threshold = kwargs.get('nms_threshold', 0.4)

        print(f"[Factory] Creating RetinaFace detector")
        print(f"[Factory] ⚠️  WARNING: RetinaFace is ~500MB - NOT suitable for Lambda!")
        print(f"[Factory] Consider using 'mtcnn' backend for Lambda deployment")
        return RetinaFaceDetector(
            confidence_threshold=confidence_threshold,
            min_face_size=min_face_size,
            max_face_size=max_face_size,
            nms_threshold=nms_threshold
        )

    @staticmethod
    def _create_mtcnn(
        confidence_threshold: float,
        min_face_size: int,
        max_face_size: Optional[int],
        **kwargs
    ):
        """Create MTCNN detector (Lambda-friendly)."""
        from .face_detection_mtcnn import MTCNNFaceDetector

        scale_factor = kwargs.get('scale_factor', 0.709)

        print(f"[Factory] Creating MTCNN detector (Lambda-friendly)")
        return MTCNNFaceDetector(
            confidence_threshold=confidence_threshold,
            min_face_size=min_face_size,
            max_face_size=max_face_size,
            scale_factor=scale_factor
        )

    @staticmethod
    def get_recommended_config(use_case: str = "lambda") -> dict:
        """
        Get recommended configuration for common use cases.

        Args:
            use_case: One of:
                     - 'lambda': Lambda deployment (RECOMMENDED - lightweight, accurate)
                     - 'balanced': Good accuracy and speed
                     - 'accuracy': Maximum accuracy, slower (NOT for Lambda)
                     - 'speed': Fast processing, may miss some faces

        Returns:
            Dictionary with recommended configuration

        Example:
            config = FaceDetectorFactory.get_recommended_config('lambda')
            detector = FaceDetectorFactory.create(**config)
        """
        configs = {
            'lambda': {
                'backend': 'mtcnn',
                'confidence_threshold': 0.9,
                'min_face_size': 20,
                'scale_factor': 0.709
            },
            'balanced': {
                'backend': 'mediapipe_improved',
                'confidence_threshold': 0.7,
                'min_face_size': 30,
                'use_full_range_model': True
            },
            'accuracy': {
                'backend': 'retinaface',
                'confidence_threshold': 0.75,
                'min_face_size': 25,
                'nms_threshold': 0.4
            },
            'speed': {
                'backend': 'mediapipe',
                'confidence_threshold': 0.6,
                'min_face_size': 40
            }
        }

        if use_case not in configs:
            raise ValueError(
                f"Unknown use case '{use_case}'. "
                f"Supported: {list(configs.keys())}"
            )

        return configs[use_case]


def create_detector(backend: str = "mediapipe_improved", **kwargs):
    """
    Convenience function to create face detector.

    Args:
        backend: Backend to use ('mediapipe', 'mediapipe_improved', 'retinaface')
        **kwargs: Additional parameters passed to detector

    Returns:
        Face detector instance

    Example:
        # Quick creation
        detector = create_detector('retinaface', confidence_threshold=0.75)
    """
    return FaceDetectorFactory.create(backend=backend, **kwargs)
