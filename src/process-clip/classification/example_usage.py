"""
Example Usage of Classification Service

This demonstrates how to use the video classification system.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Now import from classification package
from classification import get_classification_service


def example_basic_usage():
    """
    Basic usage example: classify a video and get processing strategy
    """
    print("=" * 60)
    print("EXAMPLE 1: Basic Classification")
    print("=" * 60)

    # Get service instance
    service = get_classification_service()

    # Initialize (discovers and loads all plugins)
    success = service.initialize()

    if not success:
        print("Failed to initialize classification service")
        return

    # Example clip info (like what comes from test-event.json)
    clip_info = {
        "clip": {
            "id": "clip_123",
            "start": 10.0,
            "end": 40.0,
            "duration": 30.0,
            "text": "Hey everyone, today I'm going to show you how to make the perfect chocolate chip cookies. First, you'll want to mix the butter and sugar together until it's nice and fluffy.",
            "segments": [
                {
                    "start": 10.0,
                    "end": 15.5,
                    "text": "Hey everyone, today I'm going to show you",
                    "words": [
                        {"start": 10.0, "end": 10.2, "word": "Hey"},
                        {"start": 10.3, "end": 10.8, "word": "everyone"},
                        # ... more words
                    ]
                },
                {
                    "start": 15.5,
                    "end": 22.0,
                    "text": "how to make the perfect chocolate chip cookies",
                    "words": []
                },
                {
                    "start": 22.5,
                    "end": 30.0,
                    "text": "First, you'll want to mix the butter and sugar together",
                    "words": []
                }
            ]
        }
    }

    # Classify the video
    classification, strategy = service.classify_video(
        video_path="/path/to/video.mp4",
        clip_info=clip_info,
        max_cost_ms=1000.0  # 1 second budget
    )

    # Print results
    if classification:
        print(f"\n✓ Classification: {classification.category}")
        print(f"  Confidence: {classification.confidence:.2f}")
        print(f"  Processing time: {classification.processing_time_ms:.1f}ms")
        print(f"  Classifier used: {classification.classifier_id}")
        print(f"  Key factors:")
        for factor in classification.reasoning.get('key_factors', []):
            print(f"    - {factor}")
    else:
        print("\n✗ No classification matched")

    print(f"\n✓ Processing Strategy:")
    print(f"  Smart framing: {strategy.get('smart_framing')}")
    print(f"  Subtitle mode: {strategy.get('subtitle_mode')}")
    print(f"  Aspect ratios: {strategy.get('aspect_ratios')}")
    print(f"  Clip length: {strategy.get('clip_length_range')}")


def example_quick_classification():
    """
    Quick classification example: use only transcript (no video processing)
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Quick Classification (Transcript Only)")
    print("=" * 60)

    service = get_classification_service()

    if not service._initialized:
        service.initialize()

    # Gaming clip example
    clip_info = {
        "clip": {
            "id": "clip_456",
            "duration": 25.0,
            "text": "oh my god no way! that was such a clutch play! gg guys, that was insane. lets go!",
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "oh my god no way!",
                    "words": []
                },
                {
                    "start": 5.2,
                    "end": 10.0,
                    "text": "that was such a clutch play!",
                    "words": []
                }
            ]
        }
    }

    # Quick classification (FREE - no video processing)
    classification, strategy = service.classify_quick(clip_info)

    if classification:
        print(f"\n✓ Quick Classification: {classification.category}")
        print(f"  Confidence: {classification.confidence:.2f}")
    else:
        print("\n✗ No classification matched")


def example_plugin_management():
    """
    Plugin management example: list, enable, disable plugins
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Plugin Management")
    print("=" * 60)

    service = get_classification_service()

    if not service._initialized:
        service.initialize()

    # List all plugins
    print("\nRegistered Plugins:")
    plugins = service.list_plugins()

    for plugin in plugins:
        print(f"  - {plugin['name']} ({plugin['plugin_id']})")
        print(f"    Type: {plugin['plugin_type']}")
        print(f"    Status: {plugin['status']}")
        print(f"    Priority: {plugin['priority']}")

    # Get statistics
    print("\nPlugin Statistics:")
    stats = service.get_plugin_stats()
    print(f"  Total plugins: {stats['total']}")
    print(f"  Active: {stats['active']}")
    print(f"  Error: {stats['error']}")
    print(f"  By type:")
    for plugin_type, count in stats['by_type'].items():
        print(f"    {plugin_type}: {count}")
    print(f"  By status:")
    for status, count in stats['by_status'].items():
        print(f"    {status}: {count}")

    # Disable a plugin
    print("\nDisabling talking_head_classifier_v1...")
    success = service.disable_plugin("talking_head_classifier_v1")
    print(f"  {'✓' if success else '✗'} Disable {'successful' if success else 'failed'}")

    # Re-enable it
    print("\nRe-enabling talking_head_classifier_v1...")
    success = service.enable_plugin("talking_head_classifier_v1")
    print(f"  {'✓' if success else '✗'} Enable {'successful' if success else 'failed'}")


def example_with_real_test_event():
    """
    Example using actual test-event.json file
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Using Real Test Event")
    print("=" * 60)

    # Load test-event.json
    test_event_path = Path(__file__).parent.parent.parent.parent / "test-event.json"

    if not test_event_path.exists():
        print(f"test-event.json not found at {test_event_path}")
        return

    with open(test_event_path, 'r') as f:
        event_data = json.load(f)

    # Get clip (singular)
    clip = event_data.get('clip')
    if not clip:
        print("No clip found in test-event.json")
        return

    clip_info = {"clip": clip}  # Wrap in expected format

    # Initialize service
    service = get_classification_service()
    if not service._initialized:
        service.initialize()

    # Classify
    clip_title = clip_info.get('clip', {}).get('title', 'unknown')
    print(f"\nClassifying clip: {clip_title}")

    classification, strategy = service.classify_quick(clip_info)

    if classification:
        print(f"\n✓ Classification: {classification.category}")
        print(f"  Confidence: {classification.confidence:.2f}")
        print(f"\n  Recommended Strategy:")
        print(f"    Smart framing: {strategy.get('smart_framing')}")
        print(f"    Subtitle mode: {strategy.get('subtitle_mode')}")
        print(f"    Primary aspect ratio: {strategy.get('primary_ratio')}")
    else:
        print("\n✗ No classification matched, using default strategy")


def main():
    """
    Run all examples
    """
    try:
        example_basic_usage()
        example_quick_classification()
        example_plugin_management()
        example_with_real_test_event()

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean shutdown
        service = get_classification_service()
        service.shutdown()
        print("\n" + "=" * 60)
        print("Examples completed")
        print("=" * 60)


if __name__ == "__main__":
    main()
