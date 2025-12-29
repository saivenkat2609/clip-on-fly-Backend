"""
Fitness Processing Strategy Plugin

Defines optimal processing for fitness content
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class FitnessStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for fitness videos

    Optimizations:
    - Full-body framing
    - Simple subtitles (coaching cues)
    - Vertical format (full body view)
    - Preserve movement clarity
    - Motivational presentation
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="fitness_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="Fitness Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for fitness content",
            priority=5,
            target_category="fitness",
            tags=["fitness", "workout", "exercise"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for fitness videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing (body tracking)
            'smart_framing': True,
            'framing_config': {
                'mode': 'body_tracking',
                'priority': 'full_body',
                'padding': 0.15,
                'smooth_transitions': True,
                'max_pan_speed': 0.5
            },

            # Subtitle configuration
            'subtitle_mode': 'simple',  # Coaching cues
            'subtitle_config': {
                'style': 'motivational',
                'position': 'top_third',  # Keep exercise visible
                'size': 'large',
                'color': 'white',
                'outline': True,
                'background': 'semi_transparent',
                'animation': None
            },

            # Aspect ratios (vertical for full body)
            'aspect_ratios': ['9:16', '1:1'],
            'primary_ratio': '9:16',

            # Cropping strategy
            'crop_strategy': 'body_centered',
            'auto_crop': True,
            'preserve_full_body': True,

            # Stabilization
            'stabilization': True,
            'stabilization_strength': 'medium',

            # Clip length (complete exercises/sets)
            'clip_length_range': (20.0, 60.0),
            'ideal_clip_length': 40.0,

            # Quality settings
            'quality': {
                'resolution': '1080p',
                'bitrate': 'high',
                'fps': 30
            },

            # Additional optimizations
            'additional_config': {
                'enhance_audio': True,  # Clear coaching
                'remove_silence': True,
                'fade_transitions': True,
                'add_intro_outro': True,
                'intro_duration': 2.0,
                'outro_duration': 2.0,
                'color_grading': 'vibrant',
                'saturation_boost': 1.1,
                'clarity_boost': 1.15
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': True,
                'caption_style': 'motivational',
                'add_effects': True,
                'effect_types': ['rep_counter', 'timer'],
                'add_stickers': False,
                'add_music': True,
                'music_style': 'workout',
                'music_volume': 0.25,
                'add_call_to_action': True
            }
        }

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate processing configuration

        Args:
            config: Configuration to validate

        Returns:
            True if valid
        """
        required_keys = ['smart_framing', 'subtitle_mode', 'aspect_ratios']
        return all(key in config for key in required_keys)
