"""
Sports Processing Strategy Plugin

Defines optimal processing for sports content
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class SportsStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for sports videos

    Optimizations:
    - Minimal framing (preserve action)
    - Simple subtitles (don't obscure action)
    - Multiple formats for different platforms
    - High quality/framerate
    - Fast-paced editing
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="sports_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="Sports Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for sports content",
            priority=5,
            target_category="sports",
            tags=["sports", "action", "athletics"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for sports videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing (minimal - preserve action)
            'smart_framing': False,  # Don't crop sports footage
            'framing_config': {
                'mode': 'static',
                'priority': 'preserve_frame',
                'padding': 0.0,
                'smooth_transitions': False,
                'max_pan_speed': 0.0
            },

            # Subtitle configuration
            'subtitle_mode': 'simple',  # Don't obscure action
            'subtitle_config': {
                'style': 'minimal',
                'position': 'top_third',  # Keep bottom clear
                'size': 'small',
                'color': 'white',
                'outline': True,
                'background': 'semi_transparent',
                'animation': None
            },

            # Aspect ratios
            'aspect_ratios': ['9:16', '16:9', '1:1'],
            'primary_ratio': '9:16',

            # Cropping strategy
            'crop_strategy': 'center',  # Center on action
            'auto_crop': True,
            'preserve_action': True,

            # Stabilization
            'stabilization': False,  # Preserve original camera work

            # Clip length (short for highlights)
            'clip_length_range': (10.0, 30.0),
            'ideal_clip_length': 20.0,

            # Quality settings (high for fast motion)
            'quality': {
                'resolution': '1080p',
                'bitrate': 'very_high',
                'fps': 60  # Smooth fast motion
            },

            # Additional optimizations
            'additional_config': {
                'enhance_audio': True,  # Boost crowd/impact sounds
                'remove_silence': False,  # Keep natural flow
                'fade_transitions': False,
                'add_intro_outro': False,
                'motion_blur_reduction': True,
                'sharpness_boost': 1.1
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': False,  # Action speaks for itself
                'caption_style': None,
                'add_effects': True,  # Slow-mo, replays
                'effect_types': ['slow_motion', 'zoom'],
                'add_stickers': False,
                'add_music': True,
                'music_style': 'energetic',
                'music_volume': 0.3
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
