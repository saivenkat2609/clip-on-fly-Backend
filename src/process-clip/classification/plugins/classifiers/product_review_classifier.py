"""
Product Review Classifier Plugin

Identifies product review and unboxing content:
- Product demonstration
- Review language
- Close-up shots of products
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class ProductReviewClassifier(IClassifierPlugin):
    """
    Classifies videos as product review content

    Detection signals:
    - Demonstrative language (showing, features, quality)
    - Moderate motion (handling products)
    - Mix of face and product close-ups
    - Instructional tone
    - Review/comparison keywords

    Examples: Product reviews, unboxings, comparisons, demonstrations
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="product_review_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="Product Review Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies product review and unboxing content",
            priority=4,
            requires_features=["transcript", "visual"],
            target_category="product_review",
            tags=["product", "review", "unboxing"]
        )
        self._min_confidence = 0.65

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is product review content

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
            'category': 'product_review',
            'confidence': confidence,
            'reasoning': reasoning
        }

    def _calculate_confidence(
        self,
        transcript: Dict[str, Any],
        visual: Dict[str, Any]
    ) -> tuple[float, Dict[str, Any]]:
        """
        Calculate confidence score for product review classification

        Args:
            transcript: Transcript features
            visual: Visual features

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: Demonstrative/review keywords
        # Check for tutorial keywords as proxy (reviews are instructional)
        keywords = transcript.get('keywords', [])
        has_tutorial = 'tutorial' in keywords

        # Look for demonstrative language patterns
        keyword_score = 0.7 if has_tutorial else 0.3

        signals['demonstrative_language'] = keyword_score
        weights['demonstrative_language'] = 0.30

        # Signal 2: Speech pattern (continuous explanation)
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        speech_density = transcript.get('speech_density', 0.0)

        pattern_score = {
            'continuous': 1.0,  # Explaining features
            'bursts': 0.6,
            'sparse': 0.3,
            'unknown': 0.4
        }.get(speech_pattern, 0.4)

        # Good speech density for reviews
        if 0.5 <= speech_density <= 0.8:
            pattern_score = min(1.0, pattern_score + 0.2)

        signals['speech_pattern'] = pattern_score
        weights['speech_pattern'] = 0.25

        # Signal 3: Motion (moderate - handling/showing product)
        motion_category = visual.get('motion_category', 'unknown')
        motion_score = {
            'static': 0.5,  # Could be static product shots
            'low': 0.8,
            'moderate': 1.0,  # Perfect for product handling
            'high': 0.4,
            'unknown': 0.5
        }.get(motion_category, 0.5)

        signals['product_handling'] = motion_score
        weights['product_handling'] = 0.20

        # Signal 4: Scene changes (switching between face and product)
        scene_changes = visual.get('scene_change_count', 0)

        # Reviews often cut between face and product
        if scene_changes >= 3:
            scene_score = 1.0
        elif scene_changes >= 1:
            scene_score = 0.7
        else:
            scene_score = 0.4

        signals['camera_variety'] = scene_score
        weights['camera_variety'] = 0.15

        # Signal 5: Composition (mix of face and close-ups)
        has_face = visual.get('has_faces', False)
        composition_type = visual.get('composition_type', 'unknown')

        # Reviews can be face + product shots
        if has_face and composition_type in ['talking_head', 'centered']:
            composition_score = 0.9  # Likely reviewing to camera
        elif composition_type in ['medium_shot', 'wide_shot']:
            composition_score = 0.8  # Showing product
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
            'key_factors': self._get_key_factors(signals),
            'speech_pattern': speech_pattern,
            'speech_density': speech_density,
            'motion_category': motion_category,
            'scene_changes': scene_changes,
            'composition_type': composition_type
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

        if signals.get('demonstrative_language', 0) >= 0.7:
            factors.append('Demonstrative/explanatory language')

        if signals.get('speech_pattern', 0) >= 0.8:
            factors.append('Detailed explanation pattern')

        if signals.get('product_handling', 0) >= 0.8:
            factors.append('Motion consistent with product demonstration')

        if signals.get('camera_variety', 0) >= 0.8:
            factors.append('Multiple angles/views (typical of reviews)')

        if not factors:
            factors.append('Some product review characteristics present')

        return factors
