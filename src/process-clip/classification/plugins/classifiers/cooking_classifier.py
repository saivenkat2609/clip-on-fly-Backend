"""
Cooking Classifier Plugin

Identifies cooking/recipe videos:
- Hands working with food and utensils
- Kitchen setting
- Instructional language
- Moderate motion
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class CookingClassifier(IClassifierPlugin):
    """
    Classifies videos as cooking/recipe format

    Detection signals:
    - Cooking-related keywords (mix, add, cook, ingredients)
    - Moderate motion (hands working)
    - Instructional speech pattern
    - Step-by-step language

    Examples: Recipe videos, cooking tutorials, food prep
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="cooking_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="Cooking Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies cooking and recipe videos",
            priority=3,
            requires_features=["transcript", "visual"],
            target_category="cooking",
            tags=["cooking", "recipe", "tutorial"]
        )
        self._min_confidence = 0.65

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is cooking content

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
            'category': 'cooking',
            'confidence': confidence,
            'reasoning': reasoning
        }

    def _calculate_confidence(
        self,
        transcript: Dict[str, Any],
        visual: Dict[str, Any]
    ) -> tuple[float, Dict[str, Any]]:
        """
        Calculate confidence score for cooking classification

        Args:
            transcript: Transcript features
            visual: Visual features

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: Cooking keywords (CRITICAL)
        keywords = transcript.get('keywords', [])
        has_cooking = 'cooking' in keywords
        has_tutorial = 'tutorial' in keywords

        keyword_score = 0.0
        if has_cooking:
            keyword_score = 1.0
        elif has_tutorial:
            keyword_score = 0.4  # Could be cooking tutorial

        signals['cooking_keywords'] = keyword_score
        weights['cooking_keywords'] = 0.40

        # Signal 2: Instructional language
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        pattern_score = {
            'continuous': 0.8,  # Step-by-step instructions
            'bursts': 0.6,
            'sparse': 0.3,
            'unknown': 0.3
        }.get(speech_pattern, 0.3)

        signals['instructional_pattern'] = pattern_score
        weights['instructional_pattern'] = 0.20

        # Signal 3: Motion level (moderate for hand movements)
        motion_category = visual.get('motion_category', 'unknown')
        motion_score = {
            'static': 0.3,
            'low': 0.5,
            'moderate': 1.0,  # Perfect for cooking
            'high': 0.4,
            'unknown': 0.3
        }.get(motion_category, 0.3)

        signals['motion_level'] = motion_score
        weights['motion_level'] = 0.20

        # Signal 4: Composition (usually no face or face not centered)
        composition_type = visual.get('composition_type', 'unknown')
        composition_score = {
            'no_face': 0.9,  # Common for overhead/POV cooking shots
            'wide_shot': 0.7,
            'medium_shot': 0.6,
            'talking_head': 0.3,  # Less likely for cooking
            'centered': 0.5,
            'unknown': 0.5
        }.get(composition_type, 0.5)

        signals['composition'] = composition_score
        weights['composition'] = 0.20

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
            'has_cooking_keywords': has_cooking,
            'has_tutorial_keywords': has_tutorial,
            'motion_category': motion_category,
            'speech_pattern': speech_pattern
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

        if signals.get('cooking_keywords', 0) >= 0.8:
            factors.append('Strong cooking-related vocabulary detected')

        if signals.get('instructional_pattern', 0) >= 0.7:
            factors.append('Instructional speech pattern (step-by-step)')

        if signals.get('motion_level', 0) >= 0.8:
            factors.append('Moderate motion consistent with food preparation')

        if signals.get('composition', 0) >= 0.7:
            factors.append('Visual composition typical of cooking videos')

        if 'cooking' in keywords and 'tutorial' in keywords:
            factors.append('Combined cooking and tutorial indicators')

        if not factors:
            factors.append('Some cooking characteristics present')

        return factors
