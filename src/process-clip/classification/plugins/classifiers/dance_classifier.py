"""
Dance Classifier Plugin

Identifies dance and choreography content:
- Very high motion
- Music synchronized
- Body movement focused
"""

from typing import Dict, Any, Optional
from classification.core import IClassifierPlugin, PluginMetadata, PluginType


class DanceClassifier(IClassifierPlugin):
    """
    Classifies videos as dance content

    Detection signals:
    - Very high motion intensity
    - Strong music presence
    - Minimal or no speech
    - Full-body or medium shots
    - Rhythmic movement patterns

    Examples: Dance performances, choreography, dance tutorials
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="dance_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="Dance Classifier",
            version="1.0.0",
            author="OpusClip Team",
            description="Identifies dance and choreography content using NLP + objects",
            priority=5,
            requires_features=["transcript", "visual", "audio"],
            target_category="dance",
            tags=["dance", "choreography", "performance", "objects"]
        )
        self._min_confidence = 0.70

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify if video is dance content

        Args:
            features: Dictionary of extracted features

        Returns:
            Classification result or None if confidence too low
        """
        transcript_features = features.get('transcript', {})
        visual_features = features.get('visual', {})
        object_features = features.get(\'objects\') or {}
        audio_features = features.get('audio', {})

        confidence, reasoning = self._calculate_confidence(
            transcript_features,
            visual_features,
            object_features,
            audio_features
        )

        if confidence < self._min_confidence:
            return None

        return {
            'category': 'dance',
            'confidence': confidence,
            'reasoning': reasoning
        }

    def _calculate_confidence(
        self,
        transcript: Dict[str, Any],
        visual: Dict[str, Any],
        objects: Dict[str, Any],
        audio: Dict[str, Any]
    ) -> tuple[float, Dict[str, Any]]:
        """
        Calculate confidence score for dance classification

        Args:
            transcript: Transcript features
            visual: Visual features
            objects: Object detection features (optional)
            audio: Audio features

        Returns:
            Tuple of (confidence_score, reasoning_dict)
        """
        signals = {}
        weights = {}

        # Signal 1: Music presence (CRITICAL - dance needs music)
        has_music = audio.get('has_music', False)
        music_confidence = audio.get('music_confidence', 0.0)

        music_score = 0.0
        if has_music and music_confidence > 0.7:
            music_score = 1.0
        elif has_music:
            music_score = 0.7
        else:
            music_score = 0.1  # Very unlikely dance without music

        signals['music_presence'] = music_score
        weights['music_presence'] = 0.30

        # Signal 2: Motion intensity (very high for dance)
        motion_category = visual.get('motion_category', 'unknown')
        motion_intensity = visual.get('motion_intensity', 0.0)

        motion_score = {
            'high': 1.0,  # Perfect for dance
            'moderate': 0.6,  # Maybe slow dance
            'low': 0.2,
            'static': 0.0,  # Can't be dance
            'unknown': 0.3
        }.get(motion_category, 0.3)

        # Extra boost for very high motion intensity
        if motion_intensity > 0.4:
            motion_score = min(1.0, motion_score + 0.2)

        signals['motion_intensity'] = motion_score
        weights['motion_intensity'] = 0.30

        # Signal 3: Speech pattern (should be minimal/sparse)
        speech_pattern = transcript.get('speech_pattern', 'unknown')
        speech_density = transcript.get('speech_density', 0.0)

        # Dance typically has very little speech
        if speech_density < 0.2:
            speech_score = 1.0  # Perfect
        elif speech_density < 0.4:
            speech_score = 0.6  # Maybe dance tutorial
        else:
            speech_score = 0.2  # Too much talking for pure dance

        signals['minimal_speech'] = speech_score
        weights['minimal_speech'] = 0.20

        # Signal 4: Composition (full body or medium shots)
        composition_type = visual.get('composition_type', 'unknown')
        face_size_ratio = visual.get('face_size_ratio', 0.0)

        # Dance shows body, not just face
        if composition_type in ['wide_shot', 'medium_shot']:
            composition_score = 1.0
        elif composition_type == 'no_face':
            composition_score = 0.8  # Could be dance
        elif face_size_ratio < 0.15:  # Small face = showing body
            composition_score = 0.9
        else:
            composition_score = 0.3  # Face-focused = less likely dance

        signals['body_composition'] = composition_score
        weights['body_composition'] = 0.15
        # Signal: Object Detection (dance objects - STRONG SIGNAL)
        has_dance_objects = objects.get('has_dance_objects', False)
        detected_objects = objects.get('detected_objects', {})

        object_score = 0.5  # Default

        if has_dance_objects:
            # Check for specific dance objects
            dance_object_count = 0
            dance_objs_list = []

            for obj in ['person']:
                if obj in detected_objects:
                    dance_object_count += 1
                    dance_objs_list.append(obj)

            # Strong signal if multiple objects detected
            if dance_object_count == 1:
                object_score = 0.8
            else:
                object_score = 0.6

        # Use object detection category score
        category_scores = objects.get('category_scores', {})
        dance_object_score = category_scores.get('dance', 0.0)
        if dance_object_score > 0.3:
            object_score = max(object_score, dance_object_score)

        signals['dance_objects'] = object_score
        weights['dance_objects'] = 0.15



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
            'has_music': has_music,
            'music_confidence': music_confidence,
            'motion_category': motion_category,
            'motion_intensity': motion_intensity,
            'speech_density': speech_density,
            'composition_type': composition_type
        ,
            'has_dance_objects': has_dance_objects,
            'detected_objects': list(detected_objects.keys())[:5]
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

        # Object detection is strongest signal
        if signals.get('dance_objects', 0) >= 0.8:
            detected = objects.get('detected_objects', {})
            dance_objs = [obj for obj in ['person'] if obj in detected]
            if dance_objs:
                factors.append(f'Full body detected in fram{", ".join(dance_objs)}')
            else:
                factors.append('Dance objects detected in scene')


        if signals.get('music_presence', 0) >= 0.8:
            factors.append('Strong music/soundtrack detected')

        if signals.get('motion_intensity', 0) >= 0.8:
            factors.append('Very high motion (choreographed movement)')

        if signals.get('minimal_speech', 0) >= 0.8:
            factors.append('Minimal dialogue (performance-focused)')

        if signals.get('body_composition', 0) >= 0.8:
            factors.append('Full-body framing typical of dance')

        if not factors:
            factors.append('Some dance characteristics present')

        return factors
