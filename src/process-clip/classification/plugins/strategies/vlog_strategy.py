"""
Vlog Processing Strategy Plugin

Defines optimal processing for vlog/lifestyle videos
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class VlogStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for vlog videos

    Optimizations:
    - Smart framing to track subject (face + activities)
    - Karaoke subtitles for engagement
    - Multiple aspect ratios (versatile content)
    - Light stabilization for handheld footage
    - Natural, casual feel
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="vlog_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="Vlog Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for vlog and lifestyle content",
            priority=4,
            target_category="vlog",
            tags=["vlog", "lifestyle", "casual"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for vlog videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing (flexible - follow subject)
            'smart_framing': True,
            'framing_config': {
                'mode': 'adaptive',  # Switch between face and action
                'priority': 'subject',
                'padding': 0.2,
                'smooth_transitions': True,
                'max_pan_speed': 0.5
            },

            # Subtitle configuration
            'subtitle_mode': 'karaoke',
            'subtitle_config': {
                'style': 'casual',
                'position': 'bottom_third',
                'size': 'large',
                'color': 'white',
                'outline': True,
                'animation': 'scale'
            },

            # Aspect ratios (all formats work for vlogs)
            'aspect_ratios': ['9:16', '1:1', '16:9'],
            'primary_ratio': '9:16',

            # Cropping strategy
            'crop_strategy': 'adaptive',
            'auto_crop': True,

            # Stabilization (helpful for handheld)
            'stabilization': True,
            'stabilization_strength': 'medium',

            # Clip length
            'clip_length_range': (20.0, 50.0),
            'ideal_clip_length': 35.0,

            # Quality settings
            'quality': {
                'resolution': '1080p',
                'bitrate': 'high',
                'fps': 30
            },

            # Additional optimizations
            'additional_config': {
                'enhance_audio': True,
                'remove_silence': True,  # Cut dead air
                'fade_transitions': True,
                'add_intro_outro': False,
                'color_grading': 'natural',
                'vignette': False
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': True,
                'caption_style': 'dynamic',
                'add_effects': False,
                'add_stickers': False,
                'add_music': False,  # Voice is primary
                'preserve_authenticity': True
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
