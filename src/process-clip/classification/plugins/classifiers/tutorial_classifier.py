"""
Tutorial Classifier Plugin

Identifies tutorial/how-to videos:
- Instructional language
- Step-by-step explanations
- Educational keywords
- Continuous speech pattern
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class TutorialClassifier(IClassifierPlugin):
    """
    Classifies videos as tutorial/educational content

    Detection signals:
    - Tutorial keywords (first, next, step, how to, show you, make sure)
    - Continuous speech pattern (explaining)
    - High speech density
    - Moderate motion (demonstrating)
    - Instructional tone

    Examples: How-to guides, software tutorials, educational content
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="tutorial_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="Tutorial Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies tutorial and educational content using NLP + objects",
            priority=2,
            requires_features=["transcript", "visual"],
            target_category="tutorial",
            tags=["tutorial", "educational", "howto", "objects"]
        )
        self._min_confidence = 0.65

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is tutorial content

        Args:
            features: Dictionary of extracted features

        Returns:
            Classification result or None if confidence too low
        """
        transcript_features = features.get('transcript', {})
        visual_features = features.get('visual', {})
        object_features = features.get(\'objects\') or {}

        confidence, reasoning = self._calculate_confidence(
            transcript_features,
            visual_features,
            object_features
        )

        if confidence < self._min_confidence:
            return None

        return {
            'category': 'tutorial',
            'confidence': confidence,
            'reasoning': reasoning
        }

    def _calculate_confidence(
        self,
        transcript: Dict[str, Any],
        visual: Dict[str, Any],
        objects: Dict[str, Any]
    ) -> tuple[float, Dict[str, Any]]:
        """
        Calculate confidence score for tutorial classification

        Args:
            transcript: Transcript features
            visual: Visual features
            objects: Object detection features (optional)

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: Tutorial keywords (CRITICAL)
        keywords = transcript.get('keywords', [])
        has_tutorial = 'tutorial' in keywords

        keyword_score = 1.0 if has_tutorial else 0.1

        signals['tutorial_keywords'] = keyword_score
        weights['tutorial_keywords'] = 0.35

        # Signal 2: Speech pattern (continuous for explanations)
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        pattern_score = {
            'continuous': 1.0,  # Perfect for tutorials
            'bursts': 0.5,
            'sparse': 0.2,
            'unknown': 0.3
        }.get(speech_pattern, 0.3)

        signals['speech_pattern'] = pattern_score
        weights['speech_pattern'] = 0.25

        # Signal 3: Speech density (should be high - explaining)
        speech_density = transcript.get('speech_density', 0.0)
        speech_score = 0.0
        if speech_density >= 0.7:
            speech_score = 1.0
        elif speech_density >= 0.5:
            speech_score = 0.8
        elif speech_density >= 0.3:
            speech_score = 0.5
        else:
            speech_score = 0.2

        signals['speech_density'] = speech_score
        weights['speech_density'] = 0.20

        # Signal 4: Motion level (moderate for demonstrations)
        motion_category = visual.get('motion_category', 'unknown')
        motion_score = {
            'static': 0.6,  # Could be screen recording
            'low': 0.8,
            'moderate': 1.0,  # Perfect for demonstrations
            'high': 0.4,
            'unknown': 0.5
        }.get(motion_category, 0.5)

        signals['motion_level'] = motion_score
        weights['motion_level'] = 0.15
        # Signal: Object Detection (tutorial objects - STRONG SIGNAL)
        has_tutorial_objects = objects.get('has_tutorial_objects', False)
        detected_objects = objects.get('detected_objects', {})

        object_score = 0.5  # Default

        if has_tutorial_objects:
            # Check for specific tutorial objects
            tutorial_object_count = 0
            tutorial_objs_list = []

            for obj in ['book', 'laptop', 'keyboard', 'mouse', 'tv']:
                if obj in detected_objects:
                    tutorial_object_count += 1
                    tutorial_objs_list.append(obj)

            # Strong signal if multiple objects detected
            if tutorial_object_count >= 2:
                object_score = 0.9
            el            if tutorial_object_count == 1:
                object_score = 0.7
            else:
                object_score = 0.6

        # Use object detection category score
        category_scores = objects.get('category_scores', {})
        tutorial_object_score = category_scores.get('tutorial', 0.0)
        if tutorial_object_score > 0.3:
            object_score = max(object_score, tutorial_object_score)

        signals['tutorial_objects'] = object_score
        weights['tutorial_objects'] = 0.2



        # Calculate weighted confidence
        total_weight = sum(weights.values())
        confidence = sum(
            signals[key] * weights[key]
            for key in signals
        ) / total_weight

        # Prepare reasoning
        reasoning = {
            'signals': signals,
            'key_factors': self._get_key_factors(signals, keywords, objects),
            'has_tutorial_keywords': has_tutorial,
            'speech_pattern': speech_pattern,
            'speech_density': speech_density,
            'motion_category': motion_category
        ,
            'has_tutorial_objects': has_tutorial_objects,
            'detected_objects': list(detected_objects.keys())[:5]
        }

        return confidence, reasoning

    def _get_key_factors(self, signals: Dict[str, float], keywords: list, objects: Dict[str, Any]) -> list:
        """
        Extract key factors that contributed to classification

        Args:
            signals: Signal scores dictionary
            keywords: Detected keywords
            objects: Object detection features

        Returns:
            List of key factor descriptions
        """
        factors = []

        # Object detection is strongest signal
        if signals.get('tutorial_objects', 0) >= 0.8:
            detected = objects.get('detected_objects', {})
            tutorial_objs = [obj for obj in ['book', 'laptop', 'keyboard'] if obj in detected]
            if tutorial_objs:
                factors.append(f'Tutorial materials detected: book, lapto{", ".join(tutorial_objs)}')
            else:
                factors.append('Tutorial objects detected in scene')


        if signals.get('tutorial_keywords', 0) >= 0.8:
            factors.append('Strong tutorial/instructional language detected')

        if signals.get('speech_pattern', 0) >= 0.8:
            factors.append('Continuous explanatory speech pattern')

        if signals.get('speech_density', 0) >= 0.8:
            factors.append('High speech density (detailed explanation)')

        if signals.get('motion_level', 0) >= 0.8:
            factors.append('Motion consistent with demonstrations')

        if 'tutorial' in keywords:
            factors.append('Explicit tutorial indicators present')

        if not factors:
            factors.append('Some tutorial characteristics present')

        return factors
