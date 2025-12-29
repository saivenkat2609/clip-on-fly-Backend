"""
Talking Head Processing Strategy Plugin

Defines optimal processing for talking head videos
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class TalkingHeadStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for talking head videos

    Optimizations:
    - Smart framing to keep face centered (CRITICAL)
    - Karaoke subtitles for engagement
    - Primarily 9:16 (vertical) format
    - Minimal cropping needed (already centered)
    - No stabilization needed (static)

    This is the most optimized category - simple and effective processing.
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="talking_head_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="Talking Head Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for talking head videos",
            priority=1,
            target_category="talking_head",
            tags=["face", "vertical", "karaoke"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for talking head videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing to track and center face
            'smart_framing': True,
            'framing_config': {
                'mode': 'face_tracking',
                'priority': 'face',  # Keep face in frame
                'padding': 0.2,  # 20% padding around face
                'smooth_transitions': True,
                'max_pan_speed': 0.3  # Slow, smooth panning
            },

            # Subtitle configuration
            'subtitle_mode': 'karaoke',  # Word-by-word highlighting
            'subtitle_config': {
                'style': 'modern',
                'position': 'bottom_third',
                'size': 'large',
                'color': 'white',
                'outline': True,
                'animation': 'scale'  # Slight scale on active word
            },

            # Aspect ratios (vertical primary)
            'aspect_ratios': ['9:16', '1:1'],  # Vertical first, then square
            'primary_ratio': '9:16',

            # Cropping strategy
            'crop_strategy': 'face_centered',  # Center on face
            'auto_crop': True,

            # Stabilization
            'stabilization': False,  # Not needed for static shots

            # Clip length
            'clip_length_range': (15.0, 45.0),  # 15-45 seconds
            'ideal_clip_length': 30.0,

            # Quality settings
            'quality': {
                'resolution': '1080p',
                'bitrate': 'high',
                'fps': 30
            },

            # Additional optimizations
            'additional_config': {
                'enhance_audio': True,  # Boost voice clarity
                'remove_silence': True,  # Cut long pauses
                'fade_transitions': False,  # Not needed
                'add_intro_outro': False,  # Keep it raw
                'face_enhancement': True,  # Subtle beauty filter
                'background_blur': False  # Not needed (usually clean background)
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': True,
                'caption_style': 'dynamic',
                'add_effects': False,  # Keep it natural
                'add_stickers': False,
                'add_music': False  # Voice is primary
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
