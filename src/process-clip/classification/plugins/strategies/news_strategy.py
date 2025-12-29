"""
News Processing Strategy Plugin

Defines optimal processing for news content
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class NewsStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for news videos

    Optimizations:
    - Professional framing
    - Simple, clear subtitles
    - Multiple formats for distribution
    - No stabilization (professional setup)
    - Clean, authoritative presentation
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="news_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="News Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for news content",
            priority=6,
            target_category="news",
            tags=["news", "journalism", "professional"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for news videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing (minimal - professional setup)
            'smart_framing': False,
            'framing_config': {
                'mode': 'static',
                'priority': 'center',
                'padding': 0.1,
                'smooth_transitions': False,
                'max_pan_speed': 0.0
            },

            # Subtitle configuration
            'subtitle_mode': 'simple',
            'subtitle_config': {
                'style': 'professional',
                'position': 'bottom_third',
                'size': 'medium',
                'color': 'white',
                'outline': True,
                'background': 'subtle',
                'animation': None,
                'font': 'sans-serif'
            },

            # Aspect ratios
            'aspect_ratios': ['9:16', '16:9', '1:1'],
            'primary_ratio': '16:9',  # News often horizontal

            # Cropping strategy
            'crop_strategy': 'center',
            'auto_crop': True,

            # Stabilization
            'stabilization': False,  # Professional setup

            # Clip length (news segments)
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
                'enhance_audio': True,  # Clear voice
                'remove_silence': False,  # Keep pacing
                'fade_transitions': False,
                'add_intro_outro': True,
                'intro_duration': 2.0,
                'outro_duration': 2.0,
                'color_grading': 'neutral',
                'professional_look': True
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': True,
                'caption_style': 'professional',
                'add_effects': False,  # Keep it serious
                'add_stickers': False,
                'add_music': False,  # Voice only
                'lower_thirds': True,  # News graphics
                'news_ticker': False
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
