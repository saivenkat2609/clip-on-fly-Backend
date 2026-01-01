"""
Gaming Classifier Plugin

Identifies gaming videos:
- Gaming-specific vocabulary
- High motion/action
- Reaction language
- Burst speech pattern
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class GamingClassifier(IClassifierPlugin):
    """
    Classifies videos as gaming content

    Detection signals:
    - Gaming keywords (gg, clutch, lets go, nice, op, noob)
    - High motion or frequent scene changes
    - Burst speech pattern (reactions to gameplay)
    - Reaction keywords (oh my god, what, no way)
    - Moderate to high audio intensity

    Examples: Gameplay, gaming reactions, esports clips
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="gaming_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="Gaming Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies gaming and esports content",
            priority=2,
            requires_features=["transcript"],  # Can work with transcript only
            target_category="gaming",
            tags=["gaming", "esports", "gameplay"]
        )
        self._min_confidence = 0.50  # Lower threshold for transcript-only

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is gaming content

        Args:
            features: Dictionary of extracted features

        Returns:
            Classification result or None if confidence too low
        """
        transcript_features = features.get('transcript', {})
        visual_features = features.get('visual') or {}  # Handle None
        audio_features = features.get('audio') or {}  # Handle None

        confidence, reasoning = self._calculate_confidence(
            transcript_features,
            visual_features,
            audio_features
        )

        if confidence < self._min_confidence:
            return None

        return {
            'category': 'gaming',
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
        Calculate confidence score for gaming classification

        Args:
            transcript: Transcript features
            visual: Visual features
            audio: Audio features

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: Gaming keywords + semantic similarity (CRITICAL)
        keywords = transcript.get('keywords', [])
        has_gaming = 'gaming' in keywords
        has_reaction = 'reaction' in keywords

        # Use NLP semantic similarity if available
        category_similarity = transcript.get('category_similarity', {})
        gaming_similarity = category_similarity.get('gaming', 0.0)

        keyword_score = 0.0
        if has_gaming:
            keyword_score = 1.0
        elif has_reaction:
            keyword_score = 0.5  # Reactions common in gaming

        # Boost score with semantic similarity (if NLP is available)
        if gaming_similarity > 0.5:
            keyword_score = max(keyword_score, gaming_similarity)

        # Additional boost for gaming-specific entities/topics
        entities = transcript.get('entities', {})
        topics = transcript.get('topics', [])

        # Check for game-related named entities or topics
        gaming_indicators = ['game', 'player', 'match', 'level', 'battle', 'fight']
        topic_match = any(indicator in ' '.join(topics).lower() for indicator in gaming_indicators)
        if topic_match:
            keyword_score = min(1.0, keyword_score + 0.2)

        signals['gaming_keywords'] = keyword_score
        weights['gaming_keywords'] = 0.35

        # Signal 2: Speech pattern + excitement level (bursts for reactions)
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        pattern_score = {
            'bursts': 1.0,  # Perfect for gaming reactions
            'sparse': 0.7,
            'continuous': 0.4,  # Less common but possible (commentary)
            'unknown': 0.3
        }.get(speech_pattern, 0.3)

        # Use NLP excitement level if available
        excitement_level = transcript.get('excitement_level', 0.0)
        if excitement_level > 0.5:
            pattern_score = min(1.0, pattern_score + 0.2)

        signals['speech_pattern'] = pattern_score
        weights['speech_pattern'] = 0.20

        # Signal 3: Motion/scene changes (high for action games)
        motion_category = visual.get('motion_category', 'unknown')
        scene_changes = visual.get('scene_change_count', 0)

        motion_score = {
            'high': 1.0,
            'moderate': 0.8,
            'low': 0.4,
            'static': 0.2,
            'unknown': 0.3
        }.get(motion_category, 0.3)

        # Boost for many scene changes
        if scene_changes > 3:
            motion_score = min(1.0, motion_score + 0.2)

        signals['motion_action'] = motion_score
        weights['motion_action'] = 0.20

        # Signal 4: Audio intensity (gaming usually loud/energetic)
        intensity_category = audio.get('intensity_category', 'unknown')
        intensity_score = {
            'very_loud': 1.0,
            'loud': 0.9,
            'moderate': 0.6,
            'quiet': 0.3,
            'unknown': 0.5
        }.get(intensity_category, 0.5)

        signals['audio_intensity'] = intensity_score
        weights['audio_intensity'] = 0.15

        # Signal 5: Composition (can vary - sometimes face, sometimes not)
        composition_type = visual.get('composition_type', 'unknown')
        has_face = visual.get('has_faces', False)

        # Gaming can be either face cam or pure gameplay
        if not has_face:
            composition_score = 0.8  # Pure gameplay
        elif composition_type in ['talking_head', 'centered']:
            composition_score = 0.7  # Face cam + gameplay
        else:
            composition_score = 0.5

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
            'key_factors': self._get_key_factors(signals, keywords),
            'has_gaming_keywords': has_gaming,
            'has_reaction_keywords': has_reaction,
            'speech_pattern': speech_pattern,
            'motion_category': motion_category,
            'scene_changes': scene_changes,
            'audio_intensity': intensity_category
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

        if signals.get('gaming_keywords', 0) >= 0.8:
            factors.append('Strong gaming vocabulary detected')

        if signals.get('speech_pattern', 0) >= 0.8:
            factors.append('Burst speech pattern (typical of gaming reactions)')

        if signals.get('motion_action', 0) >= 0.8:
            factors.append('High motion and action typical of gameplay')

        if signals.get('audio_intensity', 0) >= 0.8:
            factors.append('High audio energy consistent with gaming content')

        if 'gaming' in keywords and 'reaction' in keywords:
            factors.append('Gaming reaction content detected')

        if not factors:
            factors.append('Some gaming characteristics present')

        return factors
