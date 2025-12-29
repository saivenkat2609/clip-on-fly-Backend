"""
Talking Head Classifier Plugin

Identifies talking head videos:
- Person speaking directly to camera
- Face-centered composition
- Low motion (mostly static)
- High speech density
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class TalkingHeadClassifier(IClassifierPlugin):
    """
    Classifies videos as talking head format

    Detection signals:
    - Face present in center of frame
    - Face takes up significant portion (15-40%)
    - Low motion (mostly static)
    - High speech density (>70%)
    - Continuous speech pattern
    - Single person typically

    Examples: Commentary, interviews, educational content, vlogs
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="talking_head_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="Talking Head Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies person speaking directly to camera",
            priority=1,  # High priority - very common format
            requires_features=["transcript", "visual"],
            target_category="talking_head",
            tags=["face", "speech", "static"]
        )
        self._min_confidence = 0.6

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is talking head format

        Args:
            features: Dictionary of extracted features

        Returns:
            Classification result or None if confidence too low
        """
        # Extract relevant features
        transcript_features = features.get('transcript', {})
        visual_features = features.get('visual', {})

        # Calculate confidence score
        confidence, reasoning = self._calculate_confidence(
            transcript_features,
            visual_features
        )

        if confidence < self._min_confidence:
            return None

        return {
            'category': 'talking_head',
            'confidence': confidence,
            'reasoning': reasoning
        }

    def _calculate_confidence(
        self,
        transcript: Dict[str, Any],
        visual: Dict[str, Any]
    ) -> tuple[float, Dict[str, Any]]:
        """
        Calculate confidence score for talking head classification

        Args:
            transcript: Transcript features
            visual: Visual features

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: Face detection (CRITICAL)
        has_face = visual.get('has_faces', False)
        face_position = visual.get('face_position', 'unknown')
        face_size_ratio = visual.get('face_size_ratio', 0.0)

        face_score = 0.0
        if has_face and face_position == 'center' and 0.15 <= face_size_ratio <= 0.5:
            face_score = 1.0  # Perfect talking head composition
        elif has_face and face_position == 'center':
            face_score = 0.7  # Face centered but wrong size
        elif has_face:
            face_score = 0.3  # Face present but not centered

        signals['face_detection'] = face_score
        weights['face_detection'] = 0.35

        # Signal 2: Motion level (should be low/static)
        motion_category = visual.get('motion_category', 'unknown')
        motion_score = {
            'static': 1.0,
            'low': 0.9,
            'moderate': 0.4,
            'high': 0.1,
            'unknown': 0.3
        }.get(motion_category, 0.3)

        signals['motion_level'] = motion_score
        weights['motion_level'] = 0.15

        # Signal 3: Speech density + semantic similarity (should be high)
        speech_density = transcript.get('speech_density', 0.0)
        speech_score = 0.0
        if speech_density >= 0.7:
            speech_score = 1.0
        elif speech_density >= 0.5:
            speech_score = 0.7
        elif speech_density >= 0.3:
            speech_score = 0.4
        else:
            speech_score = 0.1

        # Use NLP semantic similarity if available
        category_similarity = transcript.get('category_similarity', {})
        talking_head_similarity = category_similarity.get('talking_head', 0.0)

        # Boost with semantic understanding
        if talking_head_similarity > 0.6:
            speech_score = max(speech_score, talking_head_similarity)

        signals['speech_density'] = speech_score
        weights['speech_density'] = 0.25

        # Signal 4: Speech pattern + NLP topics (should be continuous)
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        pattern_score = {
            'continuous': 1.0,
            'bursts': 0.6,
            'sparse': 0.2,
            'unknown': 0.3
        }.get(speech_pattern, 0.3)

        # Check NLP topics for conversation/discussion indicators
        topics = transcript.get('topics', [])
        keywords = transcript.get('keywords', [])

        # Talking head indicators in topics/keywords
        talking_indicators = ['speaking', 'talking', 'interview', 'discussion', 'commentary']
        has_talking_indicators = any(
            indicator in ' '.join(topics + keywords).lower()
            for indicator in talking_indicators
        )
        if has_talking_indicators:
            pattern_score = min(1.0, pattern_score + 0.15)

        signals['speech_pattern'] = pattern_score
        weights['speech_pattern'] = 0.15

        # Signal 5: Composition type
        composition_type = visual.get('composition_type', 'unknown')
        composition_score = {
            'talking_head': 1.0,
            'centered': 0.7,
            'medium_shot': 0.5,
            'wide_shot': 0.2,
            'no_face': 0.0,
            'unknown': 0.3
        }.get(composition_type, 0.3)

        signals['composition'] = composition_score
        weights['composition'] = 0.10

        # Calculate weighted confidence
        total_weight = sum(weights.values())
        confidence = sum(
            signals[key] * weights[key]
            for key in signals
        ) / total_weight

        # Prepare reasoning
        reasoning = {
            'signals': signals,
            'key_factors': self._get_key_factors(signals),
            'face_detected': has_face,
            'face_position': face_position,
            'face_size_ratio': face_size_ratio,
            'motion_category': motion_category,
            'speech_density': speech_density,
            'speech_pattern': speech_pattern
        }

        return confidence, reasoning

    def _get_key_factors(self, signals: Dict[str, float]) -> list:
        """
        Extract key factors that contributed to classification

        Args:
            signals: Signal scores dictionary

        Returns:
            List of key factor descriptions
        """
        factors = []

        if signals.get('face_detection', 0) >= 0.7:
            factors.append('Face centered and well-framed')
        elif signals.get('face_detection', 0) >= 0.3:
            factors.append('Face detected but not optimally positioned')

        if signals.get('motion_level', 0) >= 0.8:
            factors.append('Minimal camera/subject motion')

        if signals.get('speech_density', 0) >= 0.7:
            factors.append('High speech density (continuous talking)')

        if signals.get('speech_pattern', 0) >= 0.8:
            factors.append('Continuous speech pattern')

        if signals.get('composition', 0) >= 0.7:
            factors.append('Professional talking head composition')

        if not factors:
            factors.append('Some talking head characteristics present')

        return factors
