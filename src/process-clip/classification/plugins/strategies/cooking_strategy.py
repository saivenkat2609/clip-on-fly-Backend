"""
Cooking Processing Strategy Plugin

Defines optimal processing for cooking/recipe videos
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class CookingStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for cooking videos

    Optimizations:
    - Smart framing to track hands/food
    - Simple subtitles (don't obscure food)
    - Multiple aspect ratios (9:16, 1:1)
    - Crop to keep action centered
    - Possible stabilization for handheld shots
    - Longer clips to show complete steps
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="cooking_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="Cooking Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for cooking and recipe videos",
            priority=3,
            target_category="cooking",
            tags=["cooking", "recipe", "food"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for cooking videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing to track hands/food action
            'smart_framing': True,
            'framing_config': {
                'mode': 'action_tracking',
                'priority': 'center_mass',  # Track where action is
                'padding': 0.15,
                'smooth_transitions': True,
                'max_pan_speed': 0.5
            },

            # Subtitle configuration
            'subtitle_mode': 'simple',  # Don't distract from food
            'subtitle_config': {
                'style': 'minimal',
                'position': 'top_third',  # Keep bottom clear for food
                'size': 'medium',
                'color': 'white',
                'outline': True,
                'animation': None
            },

            # Aspect ratios
            'aspect_ratios': ['9:16', '1:1'],  # Vertical and square
            'primary_ratio': '9:16',

            # Cropping strategy
            'crop_strategy': 'action_centered',
            'auto_crop': True,

            # Stabilization (helpful for handheld cooking videos)
            'stabilization': True,
            'stabilization_strength': 'medium',

            # Clip length (longer to show complete steps)
            'clip_length_range': (25.0, 60.0),  # 25-60 seconds
            'ideal_clip_length': 45.0,

            # Quality settings
            'quality': {
                'resolution': '1080p',
                'bitrate': 'high',
                'fps': 30
            },

            # Additional optimizations
            'additional_config': {
                'enhance_audio': True,
                'remove_silence': False,  # Keep natural pacing
                'fade_transitions': True,  # Smooth between steps
                'add_intro_outro': False,
                'color_enhancement': True,  # Make food look appetizing
                'saturation_boost': 1.1  # Slightly boost colors
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': True,
                'caption_style': 'clean',
                'add_effects': False,
                'add_stickers': False,
                'add_music': True,  # Light background music
                'music_style': 'upbeat_background'
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
