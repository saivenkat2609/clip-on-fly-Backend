"""
Classification Integration for Lambda Function

This module provides integration between the classification service
and the existing process-clip Lambda function.

Usage:
    In lambda_function.py, add:

    from classification_integration import (
        initialize_classification,
        classify_and_configure_processing
    )

    # At module level (outside handler for warm starts):
    classification_service = initialize_classification()

    # In lambda_handler, before processing:
    processing_config = classify_and_configure_processing(
        service=classification_service,
        clip_info=clip,
        video_path=local_video_path
    )

    # Use processing_config to guide processing decisions
"""

from typing import Dict, Any, Optional
from classification import get_classification_service, ClassificationService


# Global service instance (persists across warm starts)
_classification_service: Optional[ClassificationService] = None


def initialize_classification(force_reinit: bool = False) -> ClassificationService:
    """
    Initialize classification service

    This should be called once at module level (outside handler)
    to benefit from Lambda warm starts.

    Args:
        force_reinit: Force reinitialization

    Returns:
        ClassificationService instance
    """
    global _classification_service

    if _classification_service is not None and not force_reinit:
        print("[Classification] Using cached service instance (warm start)")
        return _classification_service

    print("[Classification] Initializing classification service...")

    try:
        # Get service instance
        service = get_classification_service()

        # Initialize (load plugins)
        success = service.initialize()

        if success:
            print("[Classification] ✓ Service initialized successfully")
            _classification_service = service
            return service
        else:
            print("[Classification] ✗ Service initialization failed")
            return None

    except Exception as e:
        print(f"[Classification] Error initializing: {e}")
        import traceback
        traceback.print_exc()
        return None


def classify_and_configure_processing(
    service: Optional[ClassificationService],
    clip_info: Dict[str, Any],
    video_path: Optional[str] = None,
    use_quick_mode: bool = True
) -> Dict[str, Any]:
    """
    Classify video and get processing configuration

    Args:
        service: ClassificationService instance (or None to skip)
        clip_info: Clip metadata including transcript
        video_path: Path to video (optional, only for full classification)
        use_quick_mode: Use quick classification (transcript only)

    Returns:
        Processing configuration dictionary
    """
    if service is None:
        print("[Classification] Service not available, using default config")
        return get_default_processing_config()

    try:
        # Classify the video
        if use_quick_mode or video_path is None:
            # Quick classification (transcript only - FREE)
            print("[Classification] Using quick classification (transcript only)...")
            classification, strategy = service.classify_quick({"clip": clip_info})
        else:
            # Full classification (includes visual/audio - EXPENSIVE)
            print("[Classification] Using full classification...")
            classification, strategy = service.classify_video(
                video_path=video_path,
                clip_info={"clip": clip_info},
                max_cost_ms=15000.0  # 15 second budget (NLP ~800ms + Visual ~11-12s)
            )

        # Log results
        if classification:
            print(f"[Classification] Category: {classification.category}")
            print(f"[Classification] Confidence: {classification.confidence:.2f}")
            print(f"[Classification] Classifier: {classification.classifier_id}")
        else:
            print("[Classification] No classification matched, using default")

        # Convert strategy to Lambda processing config
        return convert_strategy_to_lambda_config(strategy, classification)

    except Exception as e:
        print(f"[Classification] Error during classification: {e}")
        import traceback
        traceback.print_exc()
        return get_default_processing_config()


def convert_strategy_to_lambda_config(
    strategy: Dict[str, Any],
    classification: Optional[Any]
) -> Dict[str, Any]:
    """
    Convert classification strategy to Lambda processing config

    Args:
        strategy: Processing strategy from classification
        classification: Classification result (or None)

    Returns:
        Lambda-compatible processing configuration
    """
    config = {
        # Classification metadata
        'classified': classification is not None,
        'category': classification.category if classification else 'unknown',
        'confidence': classification.confidence if classification else 0.0,

        # Processing flags
        'use_smart_framing': strategy.get('smart_framing', False),
        'add_subtitles': strategy.get('subtitle_mode') != 'none',
        'subtitle_mode': strategy.get('subtitle_mode', 'karaoke'),

        # Aspect ratios
        'aspect_ratios': strategy.get('aspect_ratios', ['9:16']),
        'primary_ratio': strategy.get('primary_ratio', '9:16'),

        # Crop strategy
        'crop_strategy': strategy.get('crop_strategy', 'center'),

        # Quality settings
        'stabilization': strategy.get('stabilization', False),
        'clip_length_range': strategy.get('clip_length_range', (20.0, 45.0)),

        # Full strategy for reference
        'full_strategy': strategy
    }

    print(f"[Classification] Processing config:")
    print(f"  Smart framing: {config['use_smart_framing']}")
    print(f"  Subtitle mode: {config['subtitle_mode']}")
    print(f"  Primary ratio: {config['primary_ratio']}")
    print(f"  Stabilization: {config['stabilization']}")

    return config


def get_default_processing_config() -> Dict[str, Any]:
    """
    Get default processing configuration (fallback)

    Returns:
        Default processing configuration
    """
    return {
        'classified': False,
        'category': 'unknown',
        'confidence': 0.0,
        'use_smart_framing': False,
        'add_subtitles': True,
        'subtitle_mode': 'karaoke',
        'aspect_ratios': ['9:16'],
        'primary_ratio': '9:16',
        'crop_strategy': 'center',
        'stabilization': False,
        'clip_length_range': (20.0, 45.0),
        'full_strategy': {}
    }


def apply_processing_config_to_lambda(
    config: Dict[str, Any],
    current_settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply classification config to override Lambda settings

    Args:
        config: Classification-based processing config
        current_settings: Current Lambda settings (from env vars, etc.)

    Returns:
        Updated settings dictionary
    """
    # Override settings based on classification
    updated = current_settings.copy()

    # Smart framing override
    if config['classified']:
        # Only override if we have a classification
        updated['ENABLE_SMART_FRAMING'] = config['use_smart_framing']
        updated['ADD_SUBTITLES'] = config['add_subtitles']
        updated['SUBTITLE_MODE'] = config['subtitle_mode']
        updated['DEFAULT_ASPECT_RATIO'] = config['primary_ratio']

    return updated


# Example integration for lambda_function.py
def get_example_integration_code():
    """
    Returns example code showing how to integrate with lambda_function.py
    """
    return """
# Add to lambda_function.py:

from classification_integration import (
    initialize_classification,
    classify_and_configure_processing
)

# Initialize at module level (outside handler - persists across warm starts)
classification_service = initialize_classification()

def lambda_handler(event, context):
    # ... existing code ...

    # After downloading video and before processing (around line 300):

    # Get classification-based processing config
    processing_config = classify_and_configure_processing(
        service=classification_service,
        clip_info=clip,
        video_path=local_video_path,  # Optional for full classification
        use_quick_mode=True  # True = free transcript-only, False = full analysis
    )

    # Override settings based on classification
    use_smart_framing = processing_config['use_smart_framing']
    subtitle_mode = processing_config['subtitle_mode']
    aspect_ratio = processing_config['primary_ratio']

    print(f"[ProcessClip] Classification: {processing_config['category']} "
          f"(confidence: {processing_config['confidence']:.2f})")

    # Decide processing path based on classification
    if use_smart_framing and SMART_FRAMING_AVAILABLE:
        print(f"[ProcessClip] Using smart framing (recommended by classifier)")
        process_clip_with_smart_framing_lambda(...)
    elif subtitle_mode == 'karaoke' and has_word_timestamps:
        print(f"[ProcessClip] Using karaoke subtitles (recommended by classifier)")
        process_clip_with_karaoke_subtitles(...)
    elif subtitle_mode == 'simple':
        print(f"[ProcessClip] Using simple subtitles (recommended by classifier)")
        process_clip_with_simple_subtitles(...)
    else:
        print(f"[ProcessClip] No subtitles (recommended by classifier)")
        extract_clip_no_subs(...)

    # ... rest of handler ...
"""
