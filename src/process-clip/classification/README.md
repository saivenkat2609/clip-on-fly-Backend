# Video Classification System

A plugin-based system for automatically classifying videos and determining optimal processing strategies.

## Overview

This classification system analyzes video clips and automatically determines:
- **Category**: What type of content (talking head, cooking, gaming, tutorial, etc.)
- **Confidence**: How certain we are about the classification
- **Processing Strategy**: Optimal settings for video processing (framing, subtitles, aspect ratios, etc.)

## Architecture

The system uses a **microkernel plugin architecture** with:
- **Core system**: Minimal, stable orchestration layer
- **Plugins**: Self-contained, auto-discoverable feature extractors, classifiers, and strategies
- **Error isolation**: Plugins can fail without crashing the system
- **Cost awareness**: Tracks computational budget to avoid expensive operations

### Components

```
classification/
├── core/                      # Core plugin system
│   ├── plugin_metadata.py    # Data structures
│   ├── plugin_interface.py   # Base interfaces
│   ├── plugin_registry.py    # Plugin registration
│   ├── plugin_loader.py      # Auto-discovery
│   ├── plugin_manager.py     # Lifecycle management
│   └── orchestrator.py       # Execution orchestration
│
├── plugins/                   # Plugin implementations
│   ├── extractors/           # Feature extraction
│   │   ├── transcript_extractor.py
│   │   ├── visual_extractor.py
│   │   └── audio_extractor.py
│   ├── classifiers/          # Video classification
│   │   ├── talking_head_classifier.py
│   │   ├── cooking_classifier.py
│   │   ├── gaming_classifier.py
│   │   └── tutorial_classifier.py
│   └── strategies/           # Processing strategies
│       ├── talking_head_strategy.py
│       ├── cooking_strategy.py
│       ├── gaming_strategy.py
│       └── tutorial_strategy.py
│
├── classification_service.py  # Main service facade
├── classification_integration.py  # Lambda integration
└── example_usage.py          # Examples
```

## Quick Start

### Basic Usage

```python
from classification import get_classification_service

# Initialize service (discovers and loads all plugins)
service = get_classification_service()
service.initialize()

# Classify a video
classification, strategy = service.classify_video(
    video_path="/path/to/video.mp4",
    clip_info={
        "clip": {
            "start": 10.0,
            "end": 40.0,
            "duration": 30.0,
            "text": "Hey everyone, today I'm going to show you...",
            "segments": [...]
        }
    }
)

# Use results
if classification:
    print(f"Category: {classification.category}")
    print(f"Confidence: {classification.confidence:.2f}")
    print(f"Strategy: {strategy}")
```

### Quick Classification (Free)

For fast, cost-free classification using only transcript:

```python
# Quick classification (transcript only - NO video processing)
classification, strategy = service.classify_quick(clip_info)
```

### Lambda Integration

See `classification_integration.py` for full Lambda integration:

```python
from classification_integration import (
    initialize_classification,
    classify_and_configure_processing
)

# Initialize once at module level (warm starts)
classification_service = initialize_classification()

def lambda_handler(event, context):
    # Get processing config based on classification
    config = classify_and_configure_processing(
        service=classification_service,
        clip_info=clip,
        use_quick_mode=True  # Free transcript-only classification
    )

    # Use config to guide processing
    if config['use_smart_framing']:
        process_clip_with_smart_framing_lambda(...)
    elif config['subtitle_mode'] == 'karaoke':
        process_clip_with_karaoke_subtitles(...)
```

## Plugin System

### Plugin Types

1. **Feature Extractors**: Extract features from videos
   - `transcript` - Speech density, patterns, keywords (FREE)
   - `visual` - Motion, faces, composition ($0.50/1000 clips)
   - `audio` - Music, intensity, silence patterns ($0.40/1000 clips)

2. **Classifiers**: Classify videos into categories
   - `talking_head` - Person speaking to camera
   - `cooking` - Recipe and food preparation
   - `gaming` - Gameplay and gaming content
   - `tutorial` - Educational how-to content
   - _(more can be added as plugins)_

3. **Strategies**: Define processing configurations
   - Each category has optimized processing settings
   - Smart framing, subtitle modes, aspect ratios, etc.

### Adding New Plugins

#### 1. Feature Extractor

```python
from classification.core import IFeatureExtractorPlugin, PluginMetadata, PluginType

class MyExtractorPlugin(IFeatureExtractorPlugin):
    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="my_extractor_v1",
            plugin_type=PluginType.FEATURE_EXTRACTOR,
            name="My Feature Extractor",
            version="1.0.0",
            provides_features=["my_feature"],
            cost_estimate_ms=100.0
        )

    def extract(self, video_path: str, clip_info: Dict[str, Any]) -> Dict[str, Any]:
        # Extract and return features
        return {"my_metric": 0.8}
```

Save as `plugins/extractors/my_extractor.py` - it will be auto-discovered!

#### 2. Classifier

```python
from classification.core import IClassifierPlugin, PluginMetadata, PluginType

class MyClassifier(IClassifierPlugin):
    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="my_classifier_v1",
            plugin_type=PluginType.CLASSIFIER,
            name="My Classifier",
            requires_features=["transcript", "my_feature"],
            target_category="my_category"
        )

    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Analyze features and return classification
        confidence = 0.85
        return {
            'category': 'my_category',
            'confidence': confidence,
            'reasoning': {...}
        }
```

#### 3. Processing Strategy

```python
from classification.core import IProcessingStrategyPlugin, PluginMetadata, PluginType

class MyStrategy(IProcessingStrategyPlugin):
    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="my_strategy_v1",
            plugin_type=PluginType.PROCESSING_STRATEGY,
            target_category="my_category"
        )

    def get_processing_config(self) -> Dict[str, Any]:
        return {
            'smart_framing': True,
            'subtitle_mode': 'karaoke',
            'aspect_ratios': ['9:16', '1:1'],
            # ... more configuration
        }
```

## Video Categories

### Currently Supported

| Category | Detection Signals | Processing Strategy |
|----------|------------------|-------------------|
| **Talking Head** | Face centered, low motion, high speech density | Smart face tracking, karaoke subs, 9:16 |
| **Cooking** | Cooking keywords, moderate motion, instructional pattern | Action tracking, simple subs, longer clips |
| **Gaming** | Gaming keywords, high motion, burst speech, reactions | Preserve gameplay, karaoke subs, 60fps |
| **Tutorial** | Tutorial keywords, continuous explanation, demonstrations | Content-aware framing, simple subs, chapters |

### Easily Extensible

Add new categories by creating:
1. Classifier plugin (detection logic)
2. Strategy plugin (processing config)

No core code changes needed!

## Cost Optimization

The system tracks computational costs and optimizes for efficiency:

### Feature Extraction Costs

- **Transcript analysis**: FREE (already have data)
- **Visual analysis**: ~500ms per clip
- **Audio analysis**: ~400ms per clip

### Two-Stage Approach

1. **Quick Classification** (Free): Use transcript only
   - Fast, free, works for most categories
   - Good enough for talking head, tutorial, gaming

2. **Full Classification** (Paid): Add visual/audio
   - More accurate
   - Required for cooking, sports, dance
   - User can control budget: `max_cost_ms=1000`

### Cost Control

```python
# Limit computational budget
classification, strategy = service.classify_video(
    video_path=video_path,
    clip_info=clip_info,
    max_cost_ms=500.0  # Only 500ms of processing
)
```

## Error Handling

The system is designed for **graceful degradation**:

- If a plugin fails, others continue
- Circuit breaker stops repeatedly failing plugins
- Always returns a result (default strategy if needed)
- Detailed logging for debugging

```python
# Even if classification fails, you get a strategy
classification, strategy = service.classify_video(...)

# classification might be None, but strategy is never None
assert strategy is not None
```

## Performance

### Cold Start (First Invocation)
- Plugin discovery: ~50ms
- Plugin initialization: ~100ms
- **Total cold start**: ~150ms

### Warm Start (Lambda Reuse)
- Plugin loading: 0ms (cached)
- **Immediate classification**

### Classification Time
- Quick (transcript only): <10ms
- Full (all features): ~1000ms (configurable)

## Testing

Run examples:

```bash
cd src/process-clip/classification
python example_usage.py
```

This will:
1. Initialize the system
2. Run multiple classification examples
3. Demonstrate plugin management
4. Show usage with test-event.json

## Plugin Management

### List Plugins

```python
plugins = service.list_plugins()
for plugin in plugins:
    print(f"{plugin['name']} - {plugin['status']}")
```

### Disable/Enable Plugins

```python
# Disable a plugin
service.disable_plugin("talking_head_classifier_v1")

# Enable it back
service.enable_plugin("talking_head_classifier_v1")
```

### Get Statistics

```python
stats = service.get_plugin_stats()
print(f"Total plugins: {stats['total_plugins']}")
print(f"Active plugins: {stats['active_plugins']}")
```

## Configuration

### Plugin Configuration

Create `plugin_config.json`:

```json
{
    "transcript_extractor_v1": {
        "enabled": true
    },
    "visual_extractor_v1": {
        "enabled": true,
        "face_cascade_path": "/path/to/cascade.xml"
    },
    "talking_head_classifier_v1": {
        "enabled": true,
        "min_confidence": 0.7
    }
}
```

Load it:

```python
service = ClassificationService()
service.initialize(plugin_config=config)
```

## Extending the System

### Adding New Video Categories

1. **Define Detection Signals**
   - What makes this category unique?
   - Which features are most important?

2. **Create Classifier Plugin**
   - Implement detection logic
   - Set confidence thresholds
   - Provide reasoning

3. **Create Strategy Plugin**
   - Define optimal processing settings
   - Smart framing needs?
   - Subtitle preferences
   - Aspect ratio priorities

4. **Test and Iterate**
   - Run on sample videos
   - Adjust confidence thresholds
   - Refine strategy settings

### Example: Adding "Music Video" Category

```python
# plugins/classifiers/music_video_classifier.py
class MusicVideoClassifier(IClassifierPlugin):
    def __init__(self):
        self._metadata = PluginMetadata(
            plugin_id="music_video_classifier_v1",
            requires_features=["audio", "visual"],
            target_category="music_video"
        )

    def classify(self, features):
        audio = features.get('audio', {})
        visual = features.get('visual', {})

        # High music confidence + synchronized motion
        has_music = audio.get('has_music', False)
        motion = visual.get('motion_category', '')

        if has_music and motion in ['high', 'moderate']:
            return {
                'category': 'music_video',
                'confidence': 0.9,
                'reasoning': {'music': has_music, 'motion': motion}
            }
        return None
```

```python
# plugins/strategies/music_video_strategy.py
class MusicVideoStrategy(IProcessingStrategyPlugin):
    def get_processing_config(self):
        return {
            'smart_framing': False,  # Keep original framing
            'subtitle_mode': 'none',  # No subtitles for music
            'aspect_ratios': ['9:16', '1:1'],
            'stabilization': False,
            'add_music': False  # Already has music
        }
```

Drop these files in their respective directories - done!

## Troubleshooting

### Plugins Not Loading

```python
# Check plugin discovery
service.initialize()
plugins = service.list_plugins()
print(f"Found {len(plugins)} plugins")
```

### Classification Always Returns None

- Check confidence thresholds in classifiers
- Verify required features are available
- Enable more plugins

### Poor Classification Accuracy

1. Add more detection signals to classifier
2. Adjust confidence weights
3. Add new feature extractors
4. Test with diverse video samples

## Future Enhancements

- **ML-based classifiers**: Use trained models
- **Hybrid strategies**: Combine multiple strategies
- **A/B testing**: Test strategy effectiveness
- **Learning system**: Improve based on user feedback
- **More categories**: Sports, dance, news, vlog, etc.

## Architecture Benefits

### SOLID Principles

- ✅ **Single Responsibility**: Each plugin does one thing
- ✅ **Open/Closed**: Add plugins without modifying core
- ✅ **Liskov Substitution**: All plugins follow same interface
- ✅ **Interface Segregation**: Separate interfaces per plugin type
- ✅ **Dependency Inversion**: Core depends on interfaces, not implementations

### Production-Ready

- Error isolation (circuit breaker pattern)
- Cost tracking and budgeting
- Health checks and monitoring
- Graceful degradation
- Hot-reloadable plugins
- Thread-safe plugin registry

### Scalability

- Works at any scale (1 video or 1M videos)
- Lambda-optimized (warm start caching)
- Configurable cost budgets
- Can disable expensive plugins

## License

Part of OpusClip video processing system.
