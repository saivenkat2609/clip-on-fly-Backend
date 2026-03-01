# Smart Framing Local Testing

This directory contains test scripts for locally testing the smart framing face detection before deploying to AWS Lambda.

## 📁 Directory Structure

```
tests/
├── README.md              # This file
├── test_local.py          # Main test script for face detection
├── sample_clips/          # Place test videos here
└── output/                # Test results will be saved here
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd opus-clip/src/process-clip
pip install -r requirements.txt
```

**Required packages:**
- `mediapipe==0.10.9` - Face detection
- `opencv-python==4.8.1.78` - Video processing
- `numpy==1.24.3` - Numerical operations
- `scipy==1.11.4` - Signal processing

### 2. Add a Test Video

Place a sample video file in `tests/sample_clips/`:
- **Format:** MP4 (recommended)
- **Duration:** 30-60 seconds
- **Content:** Video with visible speaker(s)
- **Quality:** Good lighting for best face detection

**Example:**
```
tests/sample_clips/test_video.mp4
```

### 3. Run the Test

```bash
python tests/test_local.py tests/sample_clips/test_video.mp4
```

**Optional: Limit processing duration (in seconds):**
```bash
python tests/test_local.py tests/sample_clips/test_video.mp4 30
```

## 📊 Expected Output

The test script will:

1. **Console Output:**
   - Video properties (FPS, resolution, duration)
   - Detection progress
   - Statistics (frames processed, faces detected, confidence)
   - Sample detections with bounding boxes

2. **Annotated Video:**
   - Location: `tests/output/annotated_video.mp4`
   - Shows green bounding boxes around detected faces
   - Displays confidence scores
   - Frame counter overlay

**Example output:**
```
======================================================================
SMART FRAMING - LOCAL FACE DETECTION TEST
======================================================================

📹 Video file: tests/sample_clips/test_video.mp4

🔧 Initializing face detector...
[FaceDetector] Initialized with confidence threshold: 0.6

🔍 Running face detection...
   Processing first 60.0 seconds of video
   Sampling rate: every 2nd frame

[FaceDetector] Video: tests/sample_clips/test_video.mp4
[FaceDetector] FPS: 30.00, Total frames: 900, Duration: 30.00s
[FaceDetector] Processing from 0.00s to 30.00s
[FaceDetector] Sample rate: every 2 frame(s)
[FaceDetector] Processed 450 frames
[FaceDetector] Detected 445 faces total

======================================================================
DETECTION RESULTS
======================================================================

✅ Total frames processed: 450
✅ Frames with faces: 442
✅ Total faces detected: 445
✅ Average faces per frame: 1.01
✅ Average confidence: 0.89
✅ Face coverage: 98.2%

📋 Sample detections (first 10 frames with faces):
   ...

======================================================================
TEST COMPLETE!
======================================================================

✅ Face detection is working!
🎉 Detection quality looks good!
```

## 🔍 Interpreting Results

### Good Detection
- ✅ **Face coverage:** >80% of frames have detected faces
- ✅ **Average confidence:** >0.70
- ✅ **Bounding boxes:** Correctly positioned around faces in annotated video
- ✅ **Stability:** Faces detected consistently across frames

### Poor Detection
- ❌ **Face coverage:** <50% of frames
- ❌ **Average confidence:** <0.60
- ❌ **Bounding boxes:** Missing or incorrectly positioned
- ❌ **False positives:** Boxes around non-face objects

### Optimization Tips

**If detection is too slow:**
- Increase `sample_rate` parameter (process fewer frames)
- Use shorter test video
- Example: `sample_rate=4` processes every 4th frame

**If too many false positives:**
- Increase `confidence_threshold` (default: 0.6)
- Try values: 0.7, 0.75, 0.8
- Edit in `test_local.py`: `FaceDetector(confidence_threshold=0.7)`

**If missing faces:**
- Decrease `confidence_threshold` (try 0.5)
- Ensure good lighting in video
- Check that faces are visible (not occluded)

## 🐛 Troubleshooting

### Error: "No module named 'mediapipe'"
```bash
pip install mediapipe==0.10.9
```

### Error: "No module named 'cv2'"
```bash
pip install opencv-python==4.8.1.78
```

### Error: "Cannot open video file"
- Check file exists: `ls tests/sample_clips/`
- Verify file format: use MP4
- Try different video file

### Error: "No faces detected"
1. Check video has visible faces (not voiceover only)
2. Lower confidence threshold: `FaceDetector(confidence_threshold=0.5)`
3. Verify lighting quality in video
4. Check video resolution (not too low)

### ImportError: "cannot import name 'FaceDetector'"
- Ensure you're running from correct directory: `opus-clip/src/process-clip/`
- Check `smart_framing/__init__.py` exists
- Try: `python -c "from smart_framing import FaceDetector; print('OK')"`

## 📝 Test Video Recommendations

### Good Test Videos
- **Talking head:** Single person speaking to camera
- **Interview:** Two people in conversation
- **Presentation:** Speaker with slides
- **Podcast:** Multiple speakers visible

### Avoid for Initial Testing
- Low resolution (<480p)
- Poor lighting (very dark/backlit)
- Rapid movement (too much motion blur)
- Profile shots only (prefer frontal faces)
- Occluded faces (wearing masks, hands covering face)

## 🎯 Success Criteria

Before proceeding to Phase 2, verify:

- [ ] Test script runs without errors
- [ ] Face detection achieves >80% coverage
- [ ] Average confidence >0.70
- [ ] Annotated video shows accurate bounding boxes
- [ ] Processing time is reasonable (~3-5s per minute of video)
- [ ] No dependency on Lambda/AWS for local testing

## 🚀 Next Steps

Once face detection works locally:

1. ✅ **Verify Results:** Review annotated video carefully
2. ✅ **Test Multiple Videos:** Try different video types
3. ✅ **Phase 2:** Implement complete test suite
   - Speaker correlation
   - Smart crop calculation
   - FFmpeg integration
   - Multi-speaker handling
4. ✅ **Integration:** Connect with `lambda_function.py`
5. ✅ **Deployment:** Package and deploy to Lambda

## 📚 Additional Resources

- **Architecture Document:** `../../docs/smart-framing-architecture.md`
- **MediaPipe Documentation:** https://google.github.io/mediapipe/
- **OpenCV Documentation:** https://docs.opencv.org/

## 💡 Tips

- Start with short videos (30-60 seconds) for faster iteration
- Use videos similar to your production use case
- Test with different lighting conditions
- Verify detection on profile shots vs frontal faces
- Check performance with multiple faces in frame

---

**Need help?** Check the main project README or consult the architecture document for detailed design information.
