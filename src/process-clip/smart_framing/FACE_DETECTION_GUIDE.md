# Face Detection Guide

## Overview

This module provides **3 face detection implementations** with different accuracy/speed trade-offs:

1. **MediaPipe Original** - Fast but may have false positives
2. **MediaPipe Improved** - Enhanced with validation layer (RECOMMENDED for most cases)
3. **RetinaFace** - Maximum accuracy, fewer false positives (RECOMMENDED for quality)

## Quick Start

### Installation

```bash
# Install dependencies
pip install opencv-python mediapipe numpy scipy

# For RetinaFace support
pip install retina-face
```

### Basic Usage

```python
from face_detector_factory import create_detector

# Create detector (choose one):
detector = create_detector('mediapipe_improved')  # Balanced (recommended)
# detector = create_detector('retinaface')        # Best accuracy
# detector = create_detector('mediapipe')         # Original (not recommended)

# Detect faces
detections = detector.detect_faces_in_video(
    'video.mp4',
    start_sec=0,
    end_sec=30,
    sample_rate=2  # Process every 2nd frame
)

# Get statistics
stats = detector.get_face_statistics(detections)
print(f"Detected {stats['total_faces']} faces in {stats['total_frames']} frames")
print(f"Coverage: {stats['coverage_percent']:.1f}%")
```

## Choosing the Right Detector

### Your Problem: Small faces missed + False positives

**Recommended Solution: RetinaFace**

```python
detector = create_detector(
    backend='retinaface',
    confidence_threshold=0.75,  # Higher = fewer false positives
    min_face_size=25,           # Lower = detect smaller faces
)
```

**Alternative: MediaPipe Improved**

```python
detector = create_detector(
    backend='mediapipe_improved',
    confidence_threshold=0.7,
    min_face_size=30,
    use_full_range_model=True  # Better for distant faces
)
```

## Configuration Parameters

### `confidence_threshold` (float: 0.0-1.0)
- **Higher (0.7-0.9)**: Fewer false positives, may miss some faces
- **Lower (0.5-0.7)**: Detects more faces, more false positives
- **Recommended**:
  - MediaPipe: 0.6-0.7
  - RetinaFace: 0.75-0.85

### `min_face_size` (int: pixels)
- Minimum face width/height to accept
- **Lower (20-30)**: Detect smaller/distant faces
- **Higher (40-60)**: Filter out noise, only detect clear faces
- **Recommended**: 25-35 for most videos

### `max_face_size` (int: pixels or None)
- Maximum face size (auto-set if None)
- Helps filter false positives (very large detections)
- **Recommended**: None (auto) or 80% of frame size

### `sample_rate` (int: frames)
- Process every Nth frame
- **Lower (1-2)**: More accurate tracking, slower
- **Higher (3-5)**: Faster processing, may miss quick movements
- **Recommended**: 2 for most videos, 1 for fast-moving subjects

## Comparing Detectors

Use the comparison script to test different models on your video:

```bash
python compare_detectors.py \
    --video path/to/video.mp4 \
    --output comparison_results/ \
    --start 0 \
    --duration 10 \
    --sample-rate 2
```

This generates:
- Annotated videos for each detector
- Performance statistics
- Side-by-side comparison
- Recommendations

## Integration with Smart Framing

### Update your existing code:

**Old way (face_detection.py):**
```python
from smart_framing import FaceDetector

detector = FaceDetector(confidence_threshold=0.6)
```

**New way (recommended):**
```python
from smart_framing.face_detector_factory import create_detector

# Option 1: Use recommended config
detector = create_detector('retinaface', confidence_threshold=0.75)

# Option 2: Use preset configurations
from smart_framing.face_detector_factory import FaceDetectorFactory
config = FaceDetectorFactory.get_recommended_config('accuracy')
detector = create_detector(**config)
```

### Update `__init__.py`:

```python
# Add to exports
from .face_detector_factory import create_detector, FaceDetectorFactory

__all__ = [
    'FaceDetector',  # Original
    'create_detector',  # New unified interface
    'FaceDetectorFactory',
    # ... other exports
]
```

## Performance Comparison

Based on testing with typical videos:

| Detector | Speed | Accuracy | False Positives | Small Faces |
|----------|-------|----------|-----------------|-------------|
| MediaPipe Original | ⚡⚡⚡ | ⭐⭐ | ❌ High | ❌ Misses |
| MediaPipe Improved | ⚡⚡ | ⭐⭐⭐ | ✓ Low | ✓ Better |
| RetinaFace | ⚡ | ⭐⭐⭐⭐ | ✓✓ Very Low | ✓✓ Best |

## Troubleshooting

### Still getting false positives?

1. **Increase confidence threshold**:
   ```python
   detector = create_detector('retinaface', confidence_threshold=0.85)
   ```

2. **Increase min face size**:
   ```python
   detector = create_detector('retinaface', min_face_size=40)
   ```

3. **Enable temporal filtering** (MediaPipe Improved only):
   ```python
   detections = detector.detect_faces_in_video(
       video_path,
       enable_temporal_filtering=True  # Filters inconsistent detections
   )
   ```

### Missing small/distant faces?

1. **Lower min face size**:
   ```python
   detector = create_detector('retinaface', min_face_size=20)
   ```

2. **Use full-range model** (MediaPipe only):
   ```python
   detector = create_detector('mediapipe_improved', use_full_range_model=True)
   ```

3. **Lower confidence threshold**:
   ```python
   detector = create_detector('retinaface', confidence_threshold=0.65)
   ```

4. **Reduce sample rate**:
   ```python
   detections = detector.detect_faces_in_video(video_path, sample_rate=1)
   ```

### Faces detected in wrong locations?

This indicates **false positives**. Solutions:

1. **Switch to RetinaFace** (best solution):
   ```python
   detector = create_detector('retinaface', confidence_threshold=0.75)
   ```

2. **Add validation** (already included in improved versions):
   - Size validation (min/max)
   - Aspect ratio validation
   - Position validation
   - Temporal consistency (MediaPipe Improved)

3. **Check your video quality**:
   - Low resolution may cause false detections
   - Motion blur affects detection
   - Poor lighting conditions

## Advanced Usage

### Custom Validation Rules

```python
from face_detection_retinaface import RetinaFaceDetector

detector = RetinaFaceDetector(
    confidence_threshold=0.75,
    min_face_size=30,
    max_face_size=800,  # Custom max size
    nms_threshold=0.3   # Non-maximum suppression (lower = fewer overlaps)
)
```

### Batch Processing Multiple Videos

```python
from face_detector_factory import create_detector

detector = create_detector('retinaface')

videos = ['video1.mp4', 'video2.mp4', 'video3.mp4']

for video in videos:
    print(f"Processing {video}...")
    detections = detector.detect_faces_in_video(video)
    stats = detector.get_face_statistics(detections)
    print(f"  Faces: {stats['total_faces']}, Coverage: {stats['coverage_percent']:.1f}%")
```

### Visualization for Debugging

```python
detector = create_detector('retinaface')

detections = detector.detect_faces_in_video('video.mp4', end_sec=10)

# Create annotated video
detector.visualize_detections(
    'video.mp4',
    detections,
    'annotated_output.mp4',
    start_sec=0,
    end_sec=10
)
```

## API Reference

### `create_detector(backend, **kwargs)`

Creates a face detector with unified API.

**Parameters:**
- `backend` (str): 'mediapipe', 'mediapipe_improved', or 'retinaface'
- `confidence_threshold` (float): Minimum detection confidence (0.0-1.0)
- `min_face_size` (int): Minimum face size in pixels
- `max_face_size` (int, optional): Maximum face size in pixels
- `**kwargs`: Backend-specific parameters

**Returns:** Face detector instance

### `detector.detect_faces_in_video(video_path, start_sec, end_sec, sample_rate)`

Detect faces in video.

**Parameters:**
- `video_path` (str): Path to video file
- `start_sec` (float): Start time in seconds
- `end_sec` (float, optional): End time in seconds
- `sample_rate` (int): Process every Nth frame

**Returns:** List of detections

### `detector.get_face_statistics(detections)`

Calculate detection statistics.

**Returns:** Dict with:
- `total_frames`: Number of processed frames
- `frames_with_faces`: Frames containing faces
- `total_faces`: Total face detections
- `avg_confidence`: Average confidence score
- `coverage_percent`: Percentage of frames with faces

## Best Practices

1. **Start with comparison script** - Test all models on your videos
2. **Use RetinaFace for production** - Best accuracy/quality trade-off
3. **Tune confidence threshold** - Higher = fewer false positives
4. **Adjust min_face_size** - Based on your video resolution
5. **Use sample_rate=2** - Good balance for most videos
6. **Monitor statistics** - Check coverage and confidence scores
7. **Visualize when debugging** - See what the detector actually sees

## Migration from Original FaceDetector

Replace this:
```python
from smart_framing import FaceDetector
detector = FaceDetector(confidence_threshold=0.6)
```

With this:
```python
from smart_framing import create_detector
detector = create_detector('retinaface', confidence_threshold=0.75)
```

The API is fully compatible - no other changes needed!

## Support

If you encounter issues:
1. Run the comparison script on your video
2. Check the annotated output videos
3. Review the statistics (coverage, confidence)
4. Adjust parameters based on results
5. Try different backends if one doesn't work well

## Next Steps

- Test detectors on your videos using `compare_detectors.py`
- Choose the best detector for your use case
- Integrate into your smart framing pipeline
- Monitor performance and adjust parameters
