"""
Product Review Processing Strategy Plugin

Defines optimal processing for product review content
"""

from typing import Dict, Any
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType


class ProductReviewStrategy(IProcessingStrategyPlugin):
    """
    Processing strategy for product review videos

    Optimizations:
    - Smart framing (face + product shots)
    - Simple subtitles (clear explanations)
    - Multiple aspect ratios
    - Longer clips (complete reviews)
    - Clear, professional presentation
    """

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="product_review_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            name="Product Review Strategy",
            version="1.0.0",
            author="OpusClip Team",
            description="Optimal processing for product review content",
            priority=4,
            target_category="product_review",
            tags=["product", "review", "unboxing"]
        )

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration for product review videos

        Returns:
            Processing configuration dictionary
        """
        return {
            # Smart framing (adaptive for face and product)
            'smart_framing': True,
            'framing_config': {
                'mode': 'adaptive',
                'priority': 'content_aware',
                'padding': 0.15,
                'smooth_transitions': True,
                'max_pan_speed': 0.4
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
                'animation': None
            },

            # Aspect ratios
            'aspect_ratios': ['9:16', '1:1', '16:9'],
            'primary_ratio': '9:16',

            # Cropping strategy
            'crop_strategy': 'adaptive',
            'auto_crop': True,

            # Stabilization
            'stabilization': True,
            'stabilization_strength': 'low',

            # Clip length (longer for complete reviews)
            'clip_length_range': (30.0, 60.0),
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
                'fade_transitions': True,
                'add_intro_outro': True,
                'intro_duration': 2.0,
                'outro_duration': 2.0,
                'color_enhancement': True,
                'clarity_boost': 1.1
            },

            # Engagement optimizations
            'engagement': {
                'add_captions': True,
                'caption_style': 'professional',
                'add_effects': False,
                'add_stickers': False,
                'add_music': True,
                'music_style': 'soft_background',
                'music_volume': 0.10,  # Very low
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
