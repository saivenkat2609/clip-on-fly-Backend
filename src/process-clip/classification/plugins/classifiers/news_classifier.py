"""
News Classifier Plugin

Identifies news and journalism content:
- Formal language
- News keywords
- Professional delivery
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class NewsClassifier(IClassifierPlugin):
    """
    Classifies videos as news content

    Detection signals:
    - News keywords (according to, reported, breaking, officials, statement)
    - Formal/professional speech pattern
    - High speech density (continuous reporting)
    - Low motion (professional setup)
    - Centered, professional framing

    Examples: News reports, journalism, official statements
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="news_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="News Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies news and journalism content using NLP + objects",
            priority=6,
            requires_features=["transcript", "visual"],
            target_category="news",
            tags=["news", "journalism", "reporting", "objects"]
        )
        self._min_confidence = 0.65

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is news content

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
            'category': 'news',
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
        Calculate confidence score for news classification

        Args:
            transcript: Transcript features
            visual: Visual features
            objects: Object detection features (optional)

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: News keywords (CRITICAL)
        keywords = transcript.get('keywords', [])
        has_news = 'news' in keywords

        keyword_score = 1.0 if has_news else 0.2

        signals['news_keywords'] = keyword_score
        weights['news_keywords'] = 0.35

        # Signal 2: Speech pattern (continuous, formal)
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        speech_density = transcript.get('speech_density', 0.0)

        pattern_score = {
            'continuous': 1.0,  # News reporting is continuous
            'bursts': 0.3,
            'sparse': 0.2,
            'unknown': 0.3
        }.get(speech_pattern, 0.3)

        # High speech density is typical
        if speech_density >= 0.7:
            pattern_score = min(1.0, pattern_score + 0.2)

        signals['formal_delivery'] = pattern_score
        weights['formal_delivery'] = 0.25

        # Signal 3: Motion level (low/static - professional setup)
        motion_category = visual.get('motion_category', 'unknown')
        motion_score = {
            'static': 1.0,  # News desk
            'low': 0.9,
            'moderate': 0.4,  # Maybe field reporting
            'high': 0.2,
            'unknown': 0.5
        }.get(motion_category, 0.5)

        signals['professional_setup'] = motion_score
        weights['professional_setup'] = 0.20

        # Signal 4: Composition (professional framing)
        has_face = visual.get('has_faces', False)
        composition_type = visual.get('composition_type', 'unknown')

        # News typically has professional talking head
        if composition_type == 'talking_head':
            composition_score = 1.0
        elif composition_type == 'centered' and has_face:
            composition_score = 0.9
        elif composition_type == 'wide_shot':
            composition_score = 0.5  # Could be field reporting
        else:
            composition_score = 0.4

        signals['professional_framing'] = composition_score
        weights['professional_framing'] = 0.15
        # Signal: Object Detection (news objects - STRONG SIGNAL)
        has_news_objects = objects.get('has_news_objects', False)
        detected_objects = objects.get('detected_objects', {})

        object_score = 0.5  # Default

        if has_news_objects:
            # Check for specific news objects
            news_object_count = 0
            news_objs_list = []

            for obj in ['person', 'tv', 'laptop', 'book', 'chair']:
                if obj in detected_objects:
                    news_object_count += 1
                    news_objs_list.append(obj)

            # Strong signal if multiple objects detected
            if news_object_count >= 2:
                object_score = 0.9
            el            if news_object_count == 1:
                object_score = 0.7
            else:
                object_score = 0.6

        # Use object detection category score
        category_scores = objects.get('category_scores', {})
        news_object_score = category_scores.get('news', 0.0)
        if news_object_score > 0.3:
            object_score = max(object_score, news_object_score)

        signals['news_objects'] = object_score
        weights['news_objects'] = 0.2



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
            'has_news_keywords': has_news,
            'speech_pattern': speech_pattern,
            'speech_density': speech_density,
            'motion_category': motion_category,
            'composition_type': composition_type
        ,
            'has_news_objects': has_news_objects,
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
        if signals.get('news_objects', 0) >= 0.8:
            detected = objects.get('detected_objects', {})
            news_objs = [obj for obj in ['person', 'tv', 'laptop'] if obj in detected]
            if news_objs:
                factors.append(f'News setting detected: tv, chai{", ".join(news_objs)}')
            else:
                factors.append('News objects detected in scene')


        if signals.get('news_keywords', 0) >= 0.8:
            factors.append('News/journalism vocabulary detected')

        if signals.get('formal_delivery', 0) >= 0.8:
            factors.append('Formal, continuous delivery style')

        if signals.get('professional_setup', 0) >= 0.8:
            factors.append('Professional studio/field setup')

        if signals.get('professional_framing', 0) >= 0.8:
            factors.append('Professional news framing')

        if 'news' in keywords:
            factors.append('Explicit news indicators present')

        if not factors:
            factors.append('Some news characteristics present')

        return factors
