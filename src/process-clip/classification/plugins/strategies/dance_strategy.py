"""
Dance Processing Strategy Plugin

Defines optimal processing for dance content
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class DanceStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for dance videos

    Optimizations:
    - Preserve full body framing
    - No subtitles (music-focused)
    - Vertical format priority (full-body view)
    - High quality to capture movement
    - Preserve music audio
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="dance_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="Dance Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for dance content",
            priority=5,
            target_category="dance",
            tags=["dance", "choreography", "performance"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for dance videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing (body tracking)
            'smart_framing': True,
            'framing_config': {
                'mode': 'body_tracking',
                'priority': 'full_body',
                'padding': 0.1,  # Minimal padding
                'smooth_transitions': True,
                'max_pan_speed': 0.6  # Follow movement
            },

            # Subtitle configuration
            'subtitle_mode': 'none',  # No subtitles for dance
            'subtitle_config': None,

            # Aspect ratios (vertical priority for full body)
            'aspect_ratios': ['9:16', '1:1'],
            'primary_ratio': '9:16',

            # Cropping strategy
            'crop_strategy': 'body_centered',
            'auto_crop': True,
            'preserve_full_body': True,

            # Stabilization
            'stabilization': False,  # Preserve choreography dynamics

            # Clip length (complete routines/segments)
            'clip_length_range': (15.0, 60.0),
            'ideal_clip_length': 30.0,

            # Quality settings (high for motion)
            'quality': {
                'resolution': '1080p',
                'bitrate': 'very_high',
                'fps': 60  # Smooth dance movements
            },

            # Additional optimizations
            'additional_config': {
                'enhance_audio': False,  # Keep music pure
                'remove_silence': False,
                'fade_transitions': True,
                'add_intro_outro': False,
                'color_grading': 'vibrant',
                'saturation_boost': 1.15
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': False,
                'caption_style': None,
                'add_effects': False,  # Keep performance pure
                'add_stickers': False,
                'add_music': False,  # Already has music
                'preserve_original_audio': True,
                'audio_quality': 'high'
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
        required_keys = ['subtitle_mode', 'aspect_ratios', 'quality']
        return all(key in config for key in required_keys)
