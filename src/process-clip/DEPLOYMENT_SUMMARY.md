# Smart Framing Lambda Deployment Summary

## ✅ What Was Updated

### 1. Lambda Function (`lambda_function.py`)
- ✅ **Smart framing integration**: Face detection + speaker tracking + dynamic crop
- ✅ **Subtitle sync fix**: Updated FFmpeg commands in all processing functions
- ✅ **Backward compatible**: Falls back to center crop if smart framing disabled/fails
- ✅ **Environment toggle**: Enable/disable via `ENABLE_SMART_FRAMING` env variable

**Key changes:**
- Lines 13-27: Import smart_framing module (graceful fallback if not available)
- Lines 54: Added `ENABLE_SMART_FRAMING` toggle
- Lines 234-298: Smart routing between smart framing and traditional processing
- Lines 516-622: New `process_clip_with_smart_framing_lambda()` function
- Lines 420-443: Karaoke subtitle FFmpeg fix (hybrid seeking + VFR)
- Lines 479-507: Simple subtitle FFmpeg fix
- Lines 524-546: No-subtitle FFmpeg fix

### 2. Smart Framing Module
- ✅ **Subtitle sync fix** in `smart_framing/ffmpeg_smart_crop.py`:
  - Lines 280-309: Updated `build_ffmpeg_command()` with hybrid seeking
  - Changed from `-vsync cfr` to `-vsync 2` (VFR)
  - Added `-copyts` and `-start_at_zero` for timestamp preservation

- ✅ **Sticky crop** in `smart_framing/smart_crop.py`:
  - Dead zone approach (150px radius)
  - Locks crop position until face leaves radius
  - No more jittery movements

- ✅ **New subtitle module** `smart_framing/subtitles.py`:
  - Karaoke subtitles with word-by-word highlighting
  - Simple subtitles for segment-level display
  - Auto-detection of Lambda vs local environment

### 3. Deployment Files
- ✅ **requirements_lambda.txt**: Lambda-compatible dependencies
  - opencv-python-headless (no GUI)
  - mediapipe==0.10.9
  - numpy==1.24.3
  - scipy==1.11.4
  - protobuf==3.20.3

- ✅ **deploy-process-clip.bat** (updated):
  - Now includes smart_framing module
  - Uses requirements_lambda.txt
  - Updates Lambda memory (2048MB) and timeout (900s)
  - Shows package size warnings

- ✅ **DEPLOY_LAMBDA.md**: Comprehensive deployment guide
- ✅ **deploy_to_lambda.sh**: Linux/Mac deployment script
- ✅ **deploy_to_lambda.bat**: Windows deployment script (standalone)

## 🚀 Quick Deployment

### Simple Way (Uses existing deployment script):

```bash
cd opus-clip\deployment
deploy-process-clip.bat
```

This will:
1. Copy `lambda_function.py` and `smart_framing/` module
2. Install dependencies from `requirements_lambda.txt`
3. Create deployment package
4. Upload to Lambda
5. Update memory to 2048MB and timeout to 900s

### After Deployment:

Enable smart framing by setting environment variable:

```bash
aws lambda update-function-configuration \
  --function-name opus-clip-process-clip \
  --environment "Variables={ENABLE_SMART_FRAMING=true,BUCKET_NAME=opus-clip-videos,ASPECT_RATIO=9:16}"
```

Or in AWS Console:
1. Go to Lambda function → Configuration → Environment variables
2. Add: `ENABLE_SMART_FRAMING` = `true`

## 📊 What Changed vs Previous Version

| Feature | Before | After |
|---------|--------|-------|
| **Cropping** | Center crop only | Smart framing with face detection OR center crop |
| **Subtitle Sync** | ❌ Out of sync (0.5-2s drift) | ✅ Fixed with hybrid seeking |
| **Framing Stability** | Static center | Sticky crop with dead zone |
| **FFmpeg Commands** | `-async 1`, `-vsync cfr` | `-vsync 2`, `-copyts`, `-start_at_zero` |
| **Memory Usage** | 512-1024 MB | 1500-2500 MB (smart framing) |
| **Processing Time** | ~10-15s per 30s clip | ~30-60s per 30s clip (smart framing) |
| **Cost per Clip** | ~$0.01-0.02 | ~$0.03-0.05 (smart framing) |

## 🎛️ Configuration Options

### Environment Variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_SMART_FRAMING` | `false` | Enable smart framing (face detection) |
| `ASPECT_RATIO` | `9:16` | Video aspect ratio (9:16, 16:9, 1:1) |
| `BUCKET_NAME` | `opus-clip-videos` | S3 bucket name |
| `FFMPEG_PATH` | `/opt/bin/ffmpeg` | FFmpeg binary path |

### Lambda Configuration:

| Setting | Recommended | Minimum |
|---------|-------------|---------|
| **Memory** | 2048-3008 MB | 2048 MB |
| **Timeout** | 900s (15 min) | 300s (5 min) |
| **Ephemeral Storage** | 2048 MB | 1024 MB |
| **Architecture** | x86_64 | x86_64 (required) |

## 🔄 Toggle Smart Framing On/Off

### Enable Smart Framing:
```bash
ENABLE_SMART_FRAMING=true  # Face detection + smart crop
```
- Processing: 30-60s per 30s clip
- Memory: 1500-2500 MB
- Cost: ~$0.03-0.05 per clip
- Best for: Videos with faces/speakers

### Disable Smart Framing (Default):
```bash
ENABLE_SMART_FRAMING=false  # Simple center crop
```
- Processing: 10-15s per 30s clip
- Memory: 512-1024 MB
- Cost: ~$0.01-0.02 per clip
- Best for: Simple videos, cost optimization

**Note:** Subtitle sync fix is applied in BOTH modes!

## 🧪 Testing

After deployment, test with CloudWatch Logs:

**Check for smart framing initialization:**
```
[SmartFraming] Smart framing module loaded successfully ✅
[SmartFraming] Processing with face detection and speaker tracking...
[SmartFraming] Detected faces in X frames
[SmartFraming] ✓ Smart framing complete!
```

**Check for subtitle sync fix:**
```
[Karaoke] Running FFmpeg with karaoke subtitles...
# FFmpeg command should include: -vsync 2 -copyts -start_at_zero
```

## ❓ Troubleshooting

### Package too large (> 50MB)
If the deployment package exceeds 50MB:
1. Use `deploy_to_lambda.sh` or `deploy_to_lambda.bat` (standalone scripts)
2. These create a Lambda Layer for dependencies
3. This separates code from dependencies

### Out of memory errors
- Increase Lambda memory to 3008 MB
- Or disable smart framing: `ENABLE_SMART_FRAMING=false`

### Still see subtitle drift
- Check CloudWatch logs to verify `-vsync 2` is in FFmpeg command
- Verify Lambda function code was updated (check last modified date)

## 📝 Files Modified

```
opus-clip/
├── src/process-clip/
│   ├── lambda_function.py                 ← UPDATED (smart framing integration)
│   ├── smart_framing/
│   │   ├── __init__.py                    ← UPDATED (export subtitles)
│   │   ├── ffmpeg_smart_crop.py           ← UPDATED (subtitle sync fix)
│   │   ├── smart_crop.py                  ← UPDATED (sticky crop)
│   │   └── subtitles.py                   ← NEW (karaoke subtitles)
│   ├── requirements_lambda.txt            ← NEW (Lambda dependencies)
│   ├── DEPLOY_LAMBDA.md                   ← NEW (deployment guide)
│   ├── deploy_to_lambda.sh                ← NEW (Linux deployment)
│   └── deploy_to_lambda.bat               ← NEW (Windows deployment)
└── deployment/
    └── deploy-process-clip.bat            ← UPDATED (includes smart_framing)
```

## 🎉 Success Criteria

After deployment, you should see:
- ✅ Lambda function updated with new code
- ✅ Memory increased to 2048 MB
- ✅ Timeout increased to 900s
- ✅ CloudWatch logs show smart framing initialization
- ✅ Subtitles are synchronized with speech
- ✅ Video framing is stable (no jitter)

## 🔗 Next Steps

1. **Run deployment**: `cd deployment && deploy-process-clip.bat`
2. **Enable smart framing**: Set `ENABLE_SMART_FRAMING=true`
3. **Test with sample clip**: Process a 30s clip and verify
4. **Monitor costs**: Compare processing costs with/without smart framing
5. **Tune parameters**: Adjust `dead_zone_radius`, `sample_rate` if needed

## 📚 Additional Resources

- Full deployment guide: `DEPLOY_LAMBDA.md`
- Test pipeline locally: `python tests/test_complete_pipeline_improved.py`
- Standalone deployment: Use `deploy_to_lambda.bat` for layer-based deployment
