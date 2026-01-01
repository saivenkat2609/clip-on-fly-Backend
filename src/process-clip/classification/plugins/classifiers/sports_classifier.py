"""
Sports Classifier Plugin

Identifies sports and athletic content:
- High motion/action
- Sports commentary
- Fast-paced content
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class SportsClassifier(IClassifierPlugin):
    """
    Classifies videos as sports content

    Detection signals:
    - High motion intensity
    - Frequent scene changes
    - Sparse or burst speech (action-focused)
    - High audio intensity (crowd noise, impacts)
    - Low face presence (wide shots of action)

    Examples: Sports highlights, athletic performances, game clips
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="sports_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="Sports Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies sports and athletic content",
            priority=5,
            requires_features=["transcript", "visual", "audio"],
            target_category="sports",
            tags=["sports", "athletics", "action"]
        )
        self._min_confidence = 0.65

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is sports content

        Args:
            features: Dictionary of extracted features

        Returns:
            Classification result or None if confidence too low
        """
        transcript_features = features.get('transcript', {})
        visual_features = features.get('visual', {})
        audio_features = features.get('audio', {})

        confidence, reasoning = self._calculate_confidence(
            transcript_features,
            visual_features,
            audio_features
        )

        if confidence < self._min_confidence:
            return None

        return {
            'category': 'sports',
            'confidence': confidence,
            'reasoning': reasoning
        }

    def _calculate_confidence(
        self,
        transcript: Dict[str, Any],
        visual: Dict[str, Any],
        audio: Dict[str, Any]
    ) -> tuple[float, Dict[str, Any]]:
        """
        Calculate confidence score for sports classification

        Args:
            transcript: Transcript features
            visual: Visual features
            audio: Audio features

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: Motion intensity (CRITICAL - sports = high action)
        motion_category = visual.get('motion_category', 'unknown')
        scene_changes = visual.get('scene_change_count', 0)

        motion_score = {
            'high': 1.0,  # Perfect for sports
            'moderate': 0.6,
            'low': 0.2,
            'static': 0.1,
            'unknown': 0.3
        }.get(motion_category, 0.3)

        # Boost for many scene changes (camera cuts during action)
        if scene_changes > 5:
            motion_score = min(1.0, motion_score + 0.2)

        signals['motion_action'] = motion_score
        weights['motion_action'] = 0.35

        # Signal 2: Speech pattern (sparse/burst - focus on action)
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        speech_density = transcript.get('speech_density', 0.0)

        pattern_score = {
            'sparse': 1.0,  # Common in sports (action > talking)
            'bursts': 0.8,  # Commentary bursts
            'continuous': 0.3,
            'unknown': 0.4
        }.get(speech_pattern, 0.4)

        # Low speech density is typical for sports
        if speech_density < 0.4:
            pattern_score = min(1.0, pattern_score + 0.2)

        signals['speech_pattern'] = pattern_score
        weights['speech_pattern'] = 0.20

        # Signal 3: Audio intensity (high for crowd, impacts)
        intensity_category = audio.get('intensity_category', 'unknown')
        intensity_score = {
            'very_loud': 1.0,
            'loud': 0.9,
            'moderate': 0.5,
            'quiet': 0.2,
            'unknown': 0.5
        }.get(intensity_category, 0.5)

        signals['audio_intensity'] = intensity_score
        weights['audio_intensity'] = 0.20

        # Signal 4: Composition (wide shots, no centered face)
        has_face = visual.get('has_faces', False)
        composition_type = visual.get('composition_type', 'unknown')

        # Sports usually doesn't have centered talking heads
        if composition_type in ['wide_shot', 'no_face']:
            composition_score = 1.0
        elif composition_type == 'medium_shot':
            composition_score = 0.6
        elif not has_face:
            composition_score = 0.8
        else:
            composition_score = 0.3  # Face-focused = less likely sports

        signals['composition'] = composition_score
        weights['composition'] = 0.15

        # Signal 5: Music presence (often has music/soundtrack)
        has_music = audio.get('has_music', False)
        music_score = 0.8 if has_music else 0.5

        signals['has_music'] = music_score
        weights['has_music'] = 0.10

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
            'motion_category': motion_category,
            'scene_changes': scene_changes,
            'speech_pattern': speech_pattern,
            'speech_density': speech_density,
            'audio_intensity': intensity_category,
            'has_music': has_music
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

        if signals.get('motion_action', 0) >= 0.8:
            factors.append('High-intensity action and movement')

        if signals.get('speech_pattern', 0) >= 0.8:
            factors.append('Action-focused content (minimal dialogue)')

        if signals.get('audio_intensity', 0) >= 0.8:
            factors.append('High audio energy (crowd/impacts)')

        if signals.get('composition', 0) >= 0.8:
            factors.append('Wide-angle action shots')

        if not factors:
            factors.append('Some sports characteristics present')

        return factors
