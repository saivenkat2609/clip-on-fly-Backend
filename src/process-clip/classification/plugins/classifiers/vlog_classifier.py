"""
Vlog Classifier Plugin

Identifies vlog/daily life videos:
- Personal, casual content
- Mix of talking and B-roll
- Casual language
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class VlogClassifier(IClassifierPlugin):
    """
    Classifies videos as vlog content

    Detection signals:
    - Vlog keywords (today, I'm gonna, check out, so excited)
    - Casual, personal speech pattern
    - Mix of face and non-face shots
    - Variable motion (talking + activities)
    - First-person perspective language

    Examples: Daily vlogs, lifestyle content, personal updates
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="vlog_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="Vlog Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies vlog and lifestyle content using NLP + objects",
            priority=4,
            requires_features=["transcript", "visual"],
            target_category="vlog",
            tags=["vlog", "lifestyle", "personal", "objects"]
        )
        self._min_confidence = 0.60

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is vlog content

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
            'category': 'vlog',
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
        Calculate confidence score for vlog classification

        Args:
            transcript: Transcript features
            visual: Visual features
            objects: Object detection features (optional)

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: Vlog keywords (CRITICAL)
        keywords = transcript.get('keywords', [])
        has_vlog = 'vlog' in keywords

        keyword_score = 1.0 if has_vlog else 0.2

        signals['vlog_keywords'] = keyword_score
        weights['vlog_keywords'] = 0.30

        # Signal 2: Speech pattern (casual, continuous with pauses)
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        pattern_score = {
            'continuous': 0.8,
            'bursts': 0.9,  # Common in vlogs (talking + doing things)
            'sparse': 0.4,
            'unknown': 0.3
        }.get(speech_pattern, 0.3)

        signals['speech_pattern'] = pattern_score
        weights['speech_pattern'] = 0.20

        # Signal 3: Speech density (moderate - not too dense, not too sparse)
        speech_density = transcript.get('speech_density', 0.0)
        speech_score = 0.0
        if 0.4 <= speech_density <= 0.7:
            speech_score = 1.0  # Perfect vlog range
        elif 0.3 <= speech_density <= 0.8:
            speech_score = 0.7
        else:
            speech_score = 0.3

        signals['speech_density'] = speech_score
        weights['speech_density'] = 0.15

        # Signal 4: Motion level (variable - mix of static and action)
        motion_category = visual.get('motion_category', 'unknown')
        scene_changes = visual.get('scene_change_count', 0)

        # Vlogs often have scene changes (different locations/activities)
        motion_score = {
            'static': 0.4,
            'low': 0.7,
            'moderate': 1.0,  # Perfect for vlogs
            'high': 0.6,
            'unknown': 0.5
        }.get(motion_category, 0.5)

        # Boost for scene changes (common in vlogs)
        if scene_changes >= 2:
            motion_score = min(1.0, motion_score + 0.2)

        signals['motion_variety'] = motion_score
        weights['motion_variety'] = 0.15

        # Signal 5: Face presence (sometimes yes, sometimes no)
        has_face = visual.get('has_faces', False)
        face_position = visual.get('face_position', 'unknown')

        # Vlogs can be either face-to-camera or showing activities
        if has_face and face_position in ['center', 'other']:
            composition_score = 0.8
        elif not has_face:
            composition_score = 0.7  # B-roll is common
        else:
            composition_score = 0.5

        signals['composition'] = composition_score
        weights['composition'] = 0.15
        # Signal: Object Detection (vlog objects - STRONG SIGNAL)
        has_vlog_objects = objects.get('has_vlog_objects', False)
        detected_objects = objects.get('detected_objects', {})

        object_score = 0.5  # Default

        if has_vlog_objects:
            # Check for specific vlog objects
            vlog_object_count = 0
            vlog_objs_list = []

            for obj in ['person', 'car', 'bicycle', 'backpack', 'cell phone']:
                if obj in detected_objects:
                    vlog_object_count += 1
                    vlog_objs_list.append(obj)

            # Strong signal if multiple objects detected
            if vlog_object_count >= 3:
                object_score = 0.8
            el            if vlog_object_count >= 2:
                object_score = 0.7
            el            if vlog_object_count == 1:
                object_score = 0.6
            else:
                object_score = 0.6

        # Use object detection category score
        category_scores = objects.get('category_scores', {})
        vlog_object_score = category_scores.get('vlog', 0.0)
        if vlog_object_score > 0.3:
            object_score = max(object_score, vlog_object_score)

        signals['vlog_objects'] = object_score
        weights['vlog_objects'] = 0.15



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
            'has_vlog_keywords': has_vlog,
            'speech_pattern': speech_pattern,
            'speech_density': speech_density,
            'motion_category': motion_category,
            'scene_changes': scene_changes
        ,
            'has_vlog_objects': has_vlog_objects,
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
        if signals.get('vlog_objects', 0) >= 0.8:
            detected = objects.get('detected_objects', {})
            vlog_objs = [obj for obj in ['person', 'car', 'bicycle'] if obj in detected]
            if vlog_objs:
                factors.append(f'Lifestyle objects detected: car, backpac{", ".join(vlog_objs)}')
            else:
                factors.append('Vlog objects detected in scene')


        if signals.get('vlog_keywords', 0) >= 0.8:
            factors.append('Strong vlog vocabulary detected')

        if signals.get('speech_pattern', 0) >= 0.8:
            factors.append('Casual conversational speech pattern')

        if signals.get('motion_variety', 0) >= 0.8:
            factors.append('Mixed motion typical of lifestyle content')

        if 'vlog' in keywords:
            factors.append('Explicit vlog indicators present')

        if not factors:
            factors.append('Some vlog characteristics present')

        return factors
