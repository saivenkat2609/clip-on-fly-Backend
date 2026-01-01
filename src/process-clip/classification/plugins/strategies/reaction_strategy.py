"""
Reaction Processing Strategy Plugin

Defines optimal processing for reaction content
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class ReactionStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for reaction videos

    Optimizations:
    - Face-focused framing
    - Karaoke subtitles for reactions
    - Vertical format (face close-ups)
    - Preserve emotional delivery
    - Fast-paced editing
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="reaction_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="Reaction Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for reaction content",
            priority=3,
            target_category="reaction",
            tags=["reaction", "commentary", "response"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for reaction videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing (face tracking)
            'smart_framing': True,
            'framing_config': {
                'mode': 'face_tracking',
                'priority': 'face',
                'padding': 0.15,
                'smooth_transitions': True,
                'max_pan_speed': 0.3
            },

            # Subtitle configuration
            'subtitle_mode': 'karaoke',  # Emphasize reactions
            'subtitle_config': {
                'style': 'bold',
                'position': 'bottom_third',
                'size': 'large',
                'color': 'white',
                'outline': True,
                'background': 'semi_transparent',
                'animation': 'pop'  # Emphasize emotional words
            },

            # Aspect ratios
            'aspect_ratios': ['9:16', '1:1'],
            'primary_ratio': '9:16',

            # Cropping strategy
            'crop_strategy': 'face_centered',
            'auto_crop': True,

            # Stabilization
            'stabilization': False,  # Keep natural energy

            # Clip length (shorter for reactions)
            'clip_length_range': (15.0, 40.0),
            'ideal_clip_length': 25.0,

            # Quality settings
            'quality': {
                'resolution': '1080p',
                'bitrate': 'high',
                'fps': 30
            },

            # Additional optimizations
            'additional_config': {
                'enhance_audio': True,  # Boost reactions
                'remove_silence': True,  # Fast paced
                'fade_transitions': False,
                'add_intro_outro': False,
                'face_enhancement': True,
                'expression_boost': True
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': True,
                'caption_style': 'dynamic',
                'add_effects': True,  # Zoom on big reactions
                'effect_types': ['zoom_in', 'freeze_frame'],
                'add_stickers': True,  # Reaction emojis
                'add_music': False,  # Voice is primary
                'preserve_energy': True
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
