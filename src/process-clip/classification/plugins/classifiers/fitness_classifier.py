"""
Fitness Classifier Plugin

Identifies fitness and workout content:
- Exercise keywords
- Instructional delivery
- Body movement
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class FitnessClassifier(IClassifierPlugin):
    """
    Classifies videos as fitness content

    Detection signals:
    - Fitness keywords (reps, sets, exercise, form, squeeze, workout, muscle)
    - Moderate to high motion (exercise movements)
    - Instructional speech pattern
    - Full-body or medium shots
    - Demonstrative delivery

    Examples: Workout videos, exercise tutorials, fitness coaching
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="fitness_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="Fitness Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies fitness and workout content",
            priority=5,
            requires_features=["transcript", "visual"],
            target_category="fitness",
            tags=["fitness", "workout", "exercise"]
        )
        self._min_confidence = 0.65

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is fitness content

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
            'category': 'fitness',
            'confidence': confidence,
            'reasoning': reasoning
        }

    def _calculate_confidence(
        self,
        transcript: Dict[str, Any],
        visual: Dict[str, Any]
    ) -> tuple[float, Dict[str, Any]]:
        """
        Calculate confidence score for fitness classification

        Args:
            transcript: Transcript features
            visual: Visual features

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: Fitness keywords (CRITICAL)
        keywords = transcript.get('keywords', [])
        has_fitness = 'fitness' in keywords

        keyword_score = 1.0 if has_fitness else 0.2

        signals['fitness_keywords'] = keyword_score
        weights['fitness_keywords'] = 0.35

        # Signal 2: Speech pattern (instructional, can be continuous or bursts)
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        pattern_score = {
            'continuous': 0.9,  # Explaining exercises
            'bursts': 1.0,  # Counting reps, coaching
            'sparse': 0.4,
            'unknown': 0.3
        }.get(speech_pattern, 0.3)

        signals['instructional_pattern'] = pattern_score
        weights['instructional_pattern'] = 0.20

        # Signal 3: Motion level (moderate/high for exercise)
        motion_category = visual.get('motion_category', 'unknown')
        motion_intensity = visual.get('motion_intensity', 0.0)

        motion_score = {
            'high': 1.0,  # Active workouts
            'moderate': 1.0,  # Perfect for fitness
            'low': 0.5,  # Maybe yoga/stretching
            'static': 0.3,  # Unlikely fitness
            'unknown': 0.5
        }.get(motion_category, 0.5)

        signals['exercise_motion'] = motion_score
        weights['exercise_motion'] = 0.25

        # Signal 4: Composition (full body or medium shots)
        composition_type = visual.get('composition_type', 'unknown')
        face_size_ratio = visual.get('face_size_ratio', 0.0)

        # Fitness shows body movement, not just face
        if composition_type in ['wide_shot', 'medium_shot']:
            composition_score = 1.0
        elif composition_type == 'no_face':
            composition_score = 0.8  # Could be body-only shots
        elif face_size_ratio < 0.15:
            composition_score = 0.9  # Small face = showing body
        else:
            composition_score = 0.4  # Face-focused = less likely fitness

        signals['body_framing'] = composition_score
        weights['body_framing'] = 0.20

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
            'has_fitness_keywords': has_fitness,
            'speech_pattern': speech_pattern,
            'motion_category': motion_category,
            'motion_intensity': motion_intensity,
            'composition_type': composition_type
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

        if signals.get('fitness_keywords', 0) >= 0.8:
            factors.append('Strong fitness/exercise vocabulary')

        if signals.get('instructional_pattern', 0) >= 0.8:
            factors.append('Instructional/coaching delivery')

        if signals.get('exercise_motion', 0) >= 0.8:
            factors.append('Motion consistent with exercise/workout')

        if signals.get('body_framing', 0) >= 0.8:
            factors.append('Full-body framing typical of fitness content')

        if 'fitness' in keywords:
            factors.append('Explicit fitness indicators present')

        if not factors:
            factors.append('Some fitness characteristics present')

        return factors
