"""
Tutorial Processing Strategy Plugin

Defines optimal processing for tutorial/educational videos
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class TutorialStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for tutorial videos

    Optimizations:
    - Smart framing to track demonstrations
    - Simple subtitles (clear and readable)
    - Multiple aspect ratios
    - Crop to focus on important areas
    - Minimal stabilization
    - Longer clips (complete explanations)
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="tutorial_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="Tutorial Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for tutorial and educational content",
            priority=2,
            target_category="tutorial",
            tags=["tutorial", "education", "howto"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for tutorial videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing to track demonstrations
            'smart_framing': True,
            'framing_config': {
                'mode': 'content_aware',
                'priority': 'important_areas',  # Focus on what's being shown
                'padding': 0.15,
                'smooth_transitions': True,
                'max_pan_speed': 0.4
            },

            # Subtitle configuration
            'subtitle_mode': 'simple',  # Clear and readable
            'subtitle_config': {
                'style': 'clean',
                'position': 'bottom_third',
                'size': 'large',
                'color': 'white',
                'outline': True,
                'background': 'subtle',
                'animation': None  # No distractions
            },

            # Aspect ratios
            'aspect_ratios': ['9:16', '1:1', '16:9'],
            'primary_ratio': '9:16',

            # Cropping strategy
            'crop_strategy': 'content_aware',  # Focus on important areas
            'auto_crop': True,

            # Stabilization
            'stabilization': True,
            'stabilization_strength': 'low',  # Gentle stabilization

            # Clip length (longer for complete explanations)
            'clip_length_range': (30.0, 60.0),  # 30-60 seconds
            'ideal_clip_length': 45.0,

            # Quality settings
            'quality': {
                'resolution': '1080p',
                'bitrate': 'high',
                'fps': 30
            },

            # Additional optimizations
            'additional_config': {
                'enhance_audio': True,  # Clear voice
                'remove_silence': False,  # Keep natural pacing
                'fade_transitions': True,
                'add_intro_outro': True,  # Can add context
                'intro_duration': 2.0,
                'outro_duration': 2.0,
                'clarity_enhancement': True
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': True,
                'caption_style': 'educational',
                'add_effects': False,  # Keep it professional
                'add_stickers': False,
                'add_music': True,  # Light background music
                'music_style': 'calm_background',
                'music_volume': 0.15,  # Low volume
                'chapter_markers': True  # Show steps
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
