"""
Reaction Classifier Plugin

Identifies reaction videos:
- Strong emotional reactions
- Reaction keywords
- Face-focused content
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class ReactionClassifier(IClassifierPlugin):
    """
    Classifies videos as reaction content

    Detection signals:
    - Reaction keywords (oh my god, what, no way, bro, yo, wow, crazy)
    - Burst speech pattern (reacting to events)
    - Face presence and expressions
    - Often has talking head composition
    - Emotional/excited delivery

    Examples: Reaction videos, commentary reactions, content reviews
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="reaction_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="Reaction Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies reaction and commentary content",
            priority=3,
            requires_features=["transcript", "visual"],
            target_category="reaction",
            tags=["reaction", "commentary", "response"]
        )
        self._min_confidence = 0.65

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is reaction content

        Args:
            features: Dictionary of extracted features

        Returns:
            Classification result or None if confidence too low
        """
        transcript_features = features.get('transcript', {})
        visual_features = features.get('visual', {})

        confidence, reasoning = self._calculate_confidence(
            transcript_features,
            visual_features
        )

        if confidence < self._min_confidence:
            return None

        return {
            'category': 'reaction',
            'confidence': confidence,
            'reasoning': reasoning
        }

    def _calculate_confidence(
        self,
        transcript: Dict[str, Any],
        visual: Dict[str, Any]
    ) -> tuple[float, Dict[str, Any]]:
        """
        Calculate confidence score for reaction classification

        Args:
            transcript: Transcript features
            visual: Visual features

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: Reaction keywords (CRITICAL)
        keywords = transcript.get('keywords', [])
        has_reaction = 'reaction' in keywords

        keyword_score = 1.0 if has_reaction else 0.2

        signals['reaction_keywords'] = keyword_score
        weights['reaction_keywords'] = 0.40

        # Signal 2: Speech pattern (bursts for reactions)
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        pattern_score = {
            'bursts': 1.0,  # Perfect for reactions
            'continuous': 0.5,  # Could be reaction commentary
            'sparse': 0.4,
            'unknown': 0.3
        }.get(speech_pattern, 0.3)

        signals['speech_pattern'] = pattern_score
        weights['speech_pattern'] = 0.25

        # Signal 3: Face presence (reactions are face-focused)
        has_face = visual.get('has_faces', False)
        face_position = visual.get('face_position', 'unknown')
        composition_type = visual.get('composition_type', 'unknown')

        face_score = 0.0
        if has_face and composition_type == 'talking_head':
            face_score = 1.0  # Perfect reaction setup
        elif has_face and face_position == 'center':
            face_score = 0.8
        elif has_face:
            face_score = 0.5
        else:
            face_score = 0.2  # Reactions usually show face

        signals['face_presence'] = face_score
        weights['face_presence'] = 0.20

        # Signal 4: Motion level (usually low/static - watching something)
        motion_category = visual.get('motion_category', 'unknown')
        motion_score = {
            'static': 0.9,  # Sitting and reacting
            'low': 1.0,  # Perfect
            'moderate': 0.5,
            'high': 0.3,
            'unknown': 0.5
        }.get(motion_category, 0.5)

        signals['motion_level'] = motion_score
        weights['motion_level'] = 0.15

        # Calculate weighted confidence
        total_weight = sum(weights.values())
        confidence = sum(
            signals[key] * weights[key]
            for key in signals
        ) / total_weight

        # Prepare reasoning
        reasoning = {
            'signals': signals,
            'key_factors': self._get_key_factors(signals, keywords),
            'has_reaction_keywords': has_reaction,
            'speech_pattern': speech_pattern,
            'has_face': has_face,
            'face_position': face_position,
            'motion_category': motion_category
        }

        return confidence, reasoning

    def _get_key_factors(self, signals: Dict[str, float], keywords: list) -> list:
        """
        Extract key factors that contributed to classification

        Args:
            signals: Signal scores dictionary
            keywords: Detected keywords

        Returns:
            List of key factor descriptions
        """
        factors = []

        if signals.get('reaction_keywords', 0) >= 0.8:
            factors.append('Strong reaction vocabulary detected')

        if signals.get('speech_pattern', 0) >= 0.8:
            factors.append('Burst speech pattern (reactive comments)')

        if signals.get('face_presence', 0) >= 0.8:
            factors.append('Face-centered composition (reaction setup)')

        if signals.get('motion_level', 0) >= 0.8:
            factors.append('Static framing (watching/reacting to content)')

        if 'reaction' in keywords:
            factors.append('Explicit reaction indicators present')

        if not factors:
            factors.append('Some reaction characteristics present')

        return factors
