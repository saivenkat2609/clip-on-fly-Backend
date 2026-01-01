"""
Visual Feature Extractor Plugin

Extracts features from video frames:
- Motion intensity
- Scene changes
- Face detection
- Color analysis
- Composition (center bias, rule of thirds)
"""

from typing import Dict, Any, List, Optional
from classification.core import IFeatureExtractorPlugin, PluginMetadata, PluginType


class VisualExtractorPlugin(IFeatureExtractorPlugin):
    """
    Extracts visual features from video frames

    This plugin analyzes frames to detect:
    - Motion patterns (static, moderate, high motion)
    - Face presence and positioning
    - Scene complexity and changes
    - Color distribution
    - Visual composition

    Cost: MODERATE (requires video frame extraction)
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="visual_extractor_v1",
            plugin_type=PluginType.FEATURE_EXTRACTOR,
            name="Visual Feature Extractor",
            version="1.0.0",
            author="OpusClip Team",
            description="Extracts motion, faces, and composition from video frames",
            priority=2,  # Medium priority (moderate cost)
            cost_estimate_ms=500.0,  # ~500ms for frame analysis
            provides_features=["visual"],
            tags=["video", "frames", "faces"]
        )
        self._cv2 = None
        self._face_cascade = None

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize OpenCV and face detection models

        Args:
            config: Configuration dictionary

        Returns:
            True if initialization successful
        """
        self._config = config
        try:
            import cv2
            self._cv2 = cv2

            # Load face detection cascade
            cascade_path = config.get(
                'face_cascade_path',
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self._face_cascade = cv2.CascadeClassifier(cascade_path)

            self._initialized = True
            return True
        except ImportError:
            print("[VisualExtractor] OpenCV not available")
            self._initialized = False
            return False
        except Exception as e:
            print(f"[VisualExtractor] Initialization failed: {e}")
            self._initialized = False
            return False

    def extract(self, video_path: str, clip_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract visual features from video

        Args:
            video_path: Path to video file
            clip_info: Clip metadata

        Returns:
            Dictionary of extracted visual features
        """
        if not self._cv2:
            return self._get_fallback_features()

        try:
            # Sample frames from video
            frames = self._sample_frames(video_path, num_samples=10)

            if not frames:
                return self._get_fallback_features()

            # Analyze frames
            motion_intensity = self._calculate_motion(frames)
            scene_changes = self._detect_scene_changes(frames)
            face_info = self._detect_faces(frames)
            color_info = self._analyze_colors(frames)
            composition = self._analyze_composition(frames, face_info)

            visual_features = {
                'motion_intensity': motion_intensity,
                'motion_category': self._categorize_motion(motion_intensity),
                'scene_change_count': scene_changes,
                'has_faces': face_info['has_faces'],
                'face_count_avg': face_info['avg_face_count'],
                'face_position': face_info['dominant_position'],
                'face_size_ratio': face_info['avg_face_size_ratio'],
                'dominant_colors': color_info['dominant_colors'],
                'color_variance': color_info['variance'],
                'composition_type': composition['type'],
                'center_bias': composition['center_bias'],
                'frame_count_analyzed': len(frames)
            }

            print(f"[VisualExtractor] >>> Extracted Visual Features:")
            print(f"  Motion: intensity={motion_intensity:.2f}, category={visual_features['motion_category']}")
            print(f"  Scene changes: {scene_changes}")
            print(f"  Faces: detected={face_info['has_faces']}, avg_count={face_info['avg_face_count']:.1f}, position={face_info['dominant_position']}, size={face_info['avg_face_size_ratio']:.3f}")
            print(f"  Composition: type={composition['type']}, center_bias={composition['center_bias']:.2f}")
            print(f"  Colors: variance={color_info['variance']:.0f}")
            print(f"  Frames analyzed: {len(frames)}")

            return visual_features

        except Exception as e:
            print(f"[VisualExtractor] Error during extraction: {e}")
            return self._get_fallback_features()

    def _sample_frames(self, video_path: str, num_samples: int = 10) -> List[Any]:
        """
        Sample frames evenly from video

        Args:
            video_path: Path to video
            num_samples: Number of frames to sample

        Returns:
            List of frame arrays
        """
        frames = []
        cap = self._cv2.VideoCapture(video_path)

        try:
            total_frames = int(cap.get(self._cv2.CAP_PROP_FRAME_COUNT))
            if total_frames == 0:
                return frames

            # Sample evenly across video
            interval = max(1, total_frames // num_samples)

            for i in range(0, total_frames, interval):
                cap.set(self._cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if ret:
                    frames.append(frame)
                if len(frames) >= num_samples:
                    break

        finally:
            cap.release()

        return frames

    def _calculate_motion(self, frames: List[Any]) -> float:
        """
        Calculate motion intensity between frames

        Args:
            frames: List of video frames

        Returns:
            Motion intensity score (0.0 to 1.0)
        """
        if len(frames) < 2:
            return 0.0

        motion_scores = []

        for i in range(len(frames) - 1):
            # Convert to grayscale
            gray1 = self._cv2.cvtColor(frames[i], self._cv2.COLOR_BGR2GRAY)
            gray2 = self._cv2.cvtColor(frames[i + 1], self._cv2.COLOR_BGR2GRAY)

            # Calculate absolute difference
            diff = self._cv2.absdiff(gray1, gray2)

            # Normalize motion score
            motion_score = diff.mean() / 255.0
            motion_scores.append(motion_score)

        return sum(motion_scores) / len(motion_scores) if motion_scores else 0.0

    def _categorize_motion(self, motion_intensity: float) -> str:
        """
        Categorize motion level

        Args:
            motion_intensity: Motion intensity score

        Returns:
            Category: 'static', 'low', 'moderate', 'high'
        """
        if motion_intensity < 0.05:
            return 'static'
        elif motion_intensity < 0.15:
            return 'low'
        elif motion_intensity < 0.35:
            return 'moderate'
        else:
            return 'high'

    def _detect_scene_changes(self, frames: List[Any]) -> int:
        """
        Detect number of scene changes

        Args:
            frames: List of video frames

        Returns:
            Count of detected scene changes
        """
        if len(frames) < 2:
            return 0

        scene_changes = 0
        threshold = 0.3  # Significant difference threshold

        for i in range(len(frames) - 1):
            # Calculate histogram difference
            hist1 = self._cv2.calcHist([frames[i]], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist2 = self._cv2.calcHist([frames[i + 1]], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])

            hist1 = self._cv2.normalize(hist1, hist1).flatten()
            hist2 = self._cv2.normalize(hist2, hist2).flatten()

            # Compare histograms
            diff = self._cv2.compareHist(hist1, hist2, self._cv2.HISTCMP_CORREL)

            if diff < (1.0 - threshold):
                scene_changes += 1

        return scene_changes

    def _detect_faces(self, frames: List[Any]) -> Dict[str, Any]:
        """
        Detect faces across frames

        Args:
            frames: List of video frames

        Returns:
            Dictionary with face detection info
        """
        if not self._face_cascade:
            return {
                'has_faces': False,
                'avg_face_count': 0,
                'dominant_position': 'unknown',
                'avg_face_size_ratio': 0.0
            }

        face_counts = []
        face_positions = []
        face_sizes = []

        for frame in frames:
            gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
            faces = self._face_cascade.detectMultiScale(gray, 1.1, 4)

            face_counts.append(len(faces))

            # Analyze face positions and sizes
            frame_h, frame_w = frame.shape[:2]
            for (x, y, w, h) in faces:
                # Position relative to frame center
                center_x = (x + w/2) / frame_w
                center_y = (y + h/2) / frame_h
                face_positions.append((center_x, center_y))

                # Size relative to frame
                face_area = (w * h) / (frame_w * frame_h)
                face_sizes.append(face_area)

        has_faces = sum(face_counts) > 0
        avg_face_count = sum(face_counts) / len(face_counts) if face_counts else 0

        # Determine dominant position
        dominant_position = 'unknown'
        if face_positions:
            avg_x = sum(p[0] for p in face_positions) / len(face_positions)
            avg_y = sum(p[1] for p in face_positions) / len(face_positions)

            if 0.35 <= avg_x <= 0.65 and 0.25 <= avg_y <= 0.55:
                dominant_position = 'center'
            elif avg_x < 0.35:
                dominant_position = 'left'
            elif avg_x > 0.65:
                dominant_position = 'right'
            else:
                dominant_position = 'other'

        avg_face_size_ratio = sum(face_sizes) / len(face_sizes) if face_sizes else 0.0

        return {
            'has_faces': has_faces,
            'avg_face_count': avg_face_count,
            'dominant_position': dominant_position,
            'avg_face_size_ratio': avg_face_size_ratio
        }

    def _analyze_colors(self, frames: List[Any]) -> Dict[str, Any]:
        """
        Analyze color distribution

        Args:
            frames: List of video frames

        Returns:
            Dictionary with color analysis
        """
        all_pixels = []

        for frame in frames:
            # Sample pixels (don't use all for performance)
            sampled = frame[::10, ::10].reshape(-1, 3)
            all_pixels.append(sampled)

        if not all_pixels:
            return {'dominant_colors': [], 'variance': 0.0}

        import numpy as np
        pixels = np.vstack(all_pixels)

        # Calculate variance (higher = more diverse colors)
        variance = float(np.var(pixels))

        # Find dominant colors (simple approach)
        mean_color = pixels.mean(axis=0)
        dominant_colors = [int(c) for c in mean_color]

        return {
            'dominant_colors': dominant_colors,
            'variance': variance
        }

    def _analyze_composition(self, frames: List[Any], face_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze visual composition

        Args:
            frames: List of video frames
            face_info: Face detection information

        Returns:
            Dictionary with composition analysis
        """
        # Determine composition type based on face position and size
        composition_type = 'unknown'
        center_bias = 0.0

        if face_info['has_faces']:
            face_size = face_info['avg_face_size_ratio']
            position = face_info['dominant_position']

            if position == 'center' and face_size > 0.15:
                composition_type = 'talking_head'
                center_bias = 0.9
            elif position == 'center':
                composition_type = 'centered'
                center_bias = 0.7
            elif face_size < 0.05:
                composition_type = 'wide_shot'
                center_bias = 0.3
            else:
                composition_type = 'medium_shot'
                center_bias = 0.5
        else:
            composition_type = 'no_face'
            center_bias = 0.5

        return {
            'type': composition_type,
            'center_bias': center_bias
        }

    def _get_fallback_features(self) -> Dict[str, Any]:
        """
        Return default features when extraction fails

        Returns:
            Dictionary with default values
        """
        return {
            'motion_intensity': 0.0,
            'motion_category': 'unknown',
            'scene_change_count': 0,
            'has_faces': False,
            'face_count_avg': 0,
            'face_position': 'unknown',
            'face_size_ratio': 0.0,
            'dominant_colors': [],
            'color_variance': 0.0,
            'composition_type': 'unknown',
            'center_bias': 0.5,
            'frame_count_analyzed': 0
        }
