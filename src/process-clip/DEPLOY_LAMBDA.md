# Deploy Smart Framing to AWS Lambda

This guide explains how to deploy the smart framing module to your existing Lambda function.

## 🎯 What's New

- **Face Detection**: MediaPipe-based face detection for speaker tracking
- **Smart Cropping**: Intelligent crop positioning that follows active speakers
- **Sticky Crop**: Stable framing with dead zone (no jittery movements)
- **Subtitle Sync Fix**: Fixed subtitle synchronization issues with improved FFmpeg commands
- **Backward Compatible**: Falls back to center crop if smart framing is disabled or fails

## 📦 Deployment Steps

### Step 1: Create Lambda Layer with Dependencies

```bash
cd opus-clip/src/process-clip

# Create directory for Lambda layer
mkdir -p lambda-layer/python

# Install dependencies
pip install -r requirements_lambda.txt -t lambda-layer/python/

# Create layer zip
cd lambda-layer
zip -r smart-framing-layer.zip python/

# Check size (must be < 250MB unzipped, < 50MB zipped)
du -sh python/
ls -lh smart-framing-layer.zip
```

**Expected layer size**: ~35-40MB zipped, ~120-150MB unzipped

### Step 2: Upload Lambda Layer

#### Option A: AWS Console
1. Go to AWS Lambda Console → Layers
2. Click "Create layer"
3. Name: `smart-framing-dependencies`
4. Upload `smart-framing-layer.zip`
5. Compatible runtimes: Python 3.9, 3.10, 3.11
6. Click "Create"
7. Copy the Layer ARN

#### Option B: AWS CLI
```bash
aws lambda publish-layer-version \
  --layer-name smart-framing-dependencies \
  --description "Smart framing dependencies: opencv, mediapipe, numpy, scipy" \
  --zip-file fileb://smart-framing-layer.zip \
  --compatible-runtimes python3.9 python3.10 python3.11
```

### Step 3: Update Lambda Function Code

```bash
# Create deployment package
cd opus-clip/src/process-clip

# Zip your code (lambda_function.py + smart_framing module)
zip -r lambda-deployment.zip lambda_function.py smart_framing/

# Verify contents
unzip -l lambda-deployment.zip
```

Expected structure:
```
lambda-deployment.zip
├── lambda_function.py
└── smart_framing/
    ├── __init__.py
    ├── face_detection.py
    ├── face_detection_improved.py
    ├── face_detector_factory.py
    ├── speaker_tracking.py
    ├── smart_crop.py
    ├── ffmpeg_smart_crop.py
    ├── ffmpeg_smart_crop_optimized.py
    └── subtitles.py
```

### Step 4: Deploy to Lambda

#### Option A: AWS Console
1. Go to your Lambda function in AWS Console
2. Go to "Code" tab
3. Click "Upload from" → ".zip file"
4. Select `lambda-deployment.zip`
5. Click "Save"

#### Option B: AWS CLI
```bash
aws lambda update-function-code \
  --function-name your-process-clip-function-name \
  --zip-file fileb://lambda-deployment.zip
```

### Step 5: Attach Lambda Layer

#### AWS Console:
1. Go to your Lambda function
2. Scroll to "Layers" section
3. Click "Add a layer"
4. Select "Custom layers"
5. Choose `smart-framing-dependencies`
6. Select the latest version
7. Click "Add"

#### AWS CLI:
```bash
aws lambda update-function-configuration \
  --function-name your-process-clip-function-name \
  --layers arn:aws:lambda:REGION:ACCOUNT:layer:smart-framing-dependencies:VERSION \
           arn:aws:lambda:REGION:ACCOUNT:layer:ffmpeg:VERSION
```

### Step 6: Configure Lambda Settings

#### Update Environment Variables:
```bash
# Enable smart framing
ENABLE_SMART_FRAMING=true

# Existing variables (keep these)
BUCKET_NAME=opus-clip-videos
ASPECT_RATIO=9:16
FFMPEG_PATH=/opt/bin/ffmpeg
FFPROBE_PATH=/opt/bin/ffprobe
```

#### Update Lambda Configuration:
```bash
# Memory (face detection needs more RAM)
aws lambda update-function-configuration \
  --function-name your-process-clip-function-name \
  --memory-size 2048

# Timeout (smart framing takes longer)
aws lambda update-function-configuration \
  --function-name your-process-clip-function-name \
  --timeout 900

# Ephemeral storage (for temp files)
aws lambda update-function-configuration \
  --function-name your-process-clip-function-name \
  --ephemeral-storage '{"Size": 2048}'
```

**Recommended Lambda configuration**:
- **Memory**: 2048-3008 MB
- **Timeout**: 900 seconds (15 minutes)
- **Ephemeral Storage**: 2048 MB
- **Architecture**: x86_64 (required for MediaPipe)

### Step 7: Test the Deployment

Test with a sample clip:

```python
import boto3
import json

lambda_client = boto3.client('lambda')

test_event = {
    "session_id": "test-session-123",
    "s3_video_key": "videos/test-video.mp4",
    "clip": {
        "clip_index": 0,
        "start": 5.0,
        "end": 35.0,
        "segments": [
            {
                "start": 5.0,
                "end": 8.0,
                "text": "This is a test",
                "words": [
                    {"word": "This", "start": 5.0, "end": 5.5},
                    {"word": "is", "start": 5.6, "end": 6.0},
                    {"word": "a", "start": 6.1, "end": 6.3},
                    {"word": "test", "start": 6.4, "end": 8.0}
                ]
            }
        ]
    }
}

response = lambda_client.invoke(
    FunctionName='your-process-clip-function-name',
    InvocationType='RequestResponse',
    Payload=json.dumps(test_event)
)

result = json.loads(response['Payload'].read())
print(json.dumps(result, indent=2))
```

Check CloudWatch Logs for:
- `[SmartFraming] Smart framing module loaded successfully` ✅
- `[SmartFraming] Processing with face detection and speaker tracking...` ✅
- `[SmartFraming] Detected faces in X frames` ✅
- `[SmartFraming] ✓ Smart framing complete!` ✅

## 🔄 Disable Smart Framing (Rollback)

If you need to disable smart framing without redeploying:

```bash
# Set environment variable to false
aws lambda update-function-configuration \
  --function-name your-process-clip-function-name \
  --environment "Variables={ENABLE_SMART_FRAMING=false,...}"
```

The function will automatically fall back to center-crop mode.

## 📊 Performance Expectations

### With Smart Framing (ENABLE_SMART_FRAMING=true):
- **Processing Time**: ~30-60 seconds for 30s clip
- **Memory Usage**: 1500-2500 MB
- **Cost**: ~$0.03-0.05 per clip (at 2048MB)

### Without Smart Framing (ENABLE_SMART_FRAMING=false):
- **Processing Time**: ~10-15 seconds for 30s clip
- **Memory Usage**: 512-1024 MB
- **Cost**: ~$0.01-0.02 per clip (at 1024MB)

## 🐛 Troubleshooting

### Issue: "Smart framing module not available"
**Solution**: Check that `smart_framing/` folder is included in deployment zip

### Issue: "No module named 'cv2'"
**Solution**: Verify lambda layer is attached and contains opencv-python-headless

### Issue: "MediaPipe model files not found"
**Solution**: MediaPipe downloads models to `/tmp/mediapipe_models` on first run

### Issue: Lambda timeout
**Solution**: Increase timeout to 900s and memory to 2048MB

### Issue: Out of memory
**Solution**:
- Increase Lambda memory to 3008 MB
- Reduce `sample_rate` parameter (line 538: change from 5 to 10)

### Issue: Subtitles still out of sync
**Solution**: Check CloudWatch logs - subtitle sync fix is automatically applied

## 📝 What Was Fixed

### Subtitle Synchronization
The FFmpeg commands now use:
- **Hybrid seeking**: Fast + accurate for frame-perfect positioning
- **VFR mode** (`-vsync 2`): Prevents frame dropping that causes drift
- **Timestamp preservation** (`-copyts`, `-start_at_zero`): Maintains subtitle timing

This fix is applied to:
- ✅ `process_clip_with_karaoke_subtitles()`
- ✅ `process_clip_with_simple_subtitles()`
- ✅ `extract_clip_no_subs()`
- ✅ `process_clip_with_smart_framing_lambda()` (uses `ffmpeg_smart_crop.py`)

### Smart Framing Features
- ✅ Face detection with MediaPipe Improved
- ✅ Speaker tracking correlated with transcript
- ✅ Sticky crop with dead zone (150px radius)
- ✅ Motion keyframe optimization (max 50 keyframes)
- ✅ Graceful fallback to center crop on errors

## 🎬 Next Steps

1. **Test locally first**: Run `test_complete_pipeline_improved.py` before deploying
2. **Monitor CloudWatch**: Watch for errors during first few Lambda invocations
3. **Adjust parameters**: Tune `dead_zone_radius`, `sample_rate` based on results
4. **Cost optimization**: Use center-crop for simple videos, smart framing for complex ones

## 📞 Support

If you encounter issues:
1. Check CloudWatch Logs for detailed error messages
2. Verify all environment variables are set correctly
3. Ensure FFmpeg layer is still attached
4. Test with a short clip (10-15s) first
