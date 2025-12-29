"""
Gaming Processing Strategy Plugin

Defines optimal processing for gaming videos
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class GamingStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for gaming videos

    Optimizations:
    - Minimal framing (preserve full screen gameplay)
    - Karaoke subtitles for reactions
    - Multiple aspect ratios (9:16, 16:9)
    - Center crop for vertical (focus on action)
    - No stabilization (gameplay is stable)
    - Medium length clips (capture full moments)
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="gaming_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="Gaming Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for gaming content",
            priority=2,
            target_category="gaming",
            tags=["gaming", "esports", "gameplay"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for gaming videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing (minimal - preserve gameplay)
            'smart_framing': False,  # Usually don't want to pan gaming footage
            'framing_config': {
                'mode': 'static',
                'priority': 'center',
                'padding': 0.0,
                'smooth_transitions': False,
                'max_pan_speed': 0.0
            },

            # Subtitle configuration
            'subtitle_mode': 'karaoke',  # Highlight reactions
            'subtitle_config': {
                'style': 'bold',
                'position': 'bottom_third',
                'size': 'large',
                'color': 'white',
                'outline': True,
                'background': 'semi_transparent',
                'animation': 'pop'  # Emphasize reactions
            },

            # Aspect ratios
            'aspect_ratios': ['9:16', '16:9', '1:1'],  # All formats work
            'primary_ratio': '9:16',

            # Cropping strategy
            'crop_strategy': 'center',  # Center the action
            'auto_crop': True,
            'preserve_hud': True,  # Try to keep game UI visible

            # Stabilization
            'stabilization': False,  # Gameplay is already stable

            # Clip length (capture complete moments)
            'clip_length_range': (20.0, 50.0),  # 20-50 seconds
            'ideal_clip_length': 35.0,

            # Quality settings (high for gaming)
            'quality': {
                'resolution': '1080p',
                'bitrate': 'very_high',  # Fast motion needs high bitrate
                'fps': 60  # Smooth gameplay
            },

            # Additional optimizations
            'additional_config': {
                'enhance_audio': True,  # Boost reactions
                'remove_silence': True,  # Cut dead air
                'fade_transitions': False,  # Keep it raw
                'add_intro_outro': False,
                'sharpness_boost': 1.1,  # Enhance clarity
                'contrast_boost': 1.05
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': True,
                'caption_style': 'dynamic',
                'add_effects': True,  # Gaming benefits from effects
                'effect_types': ['hit_markers', 'screen_shake'],
                'add_stickers': True,  # Reaction stickers
                'add_music': False,  # Game audio is primary
                'preserve_game_audio': True
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
