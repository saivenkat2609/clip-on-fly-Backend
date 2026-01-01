# Local Testing Guide for Lambda Container

This guide explains how to build and test the Lambda container locally before deploying to AWS.

## Overview

We provide three scripts for local development and testing:

1. **`build-local.bat`** - Build Docker image locally (no AWS push)
2. **`smoke-test-local.bat`** - Quick test that container starts properly
3. **`test-local-container.bat`** - Full integration test with Lambda Runtime Interface Emulator

## Prerequisites

- Docker Desktop installed and running
- AWS CLI configured (for full integration tests)
- Test video uploaded to S3 (for full integration tests)

## Workflow

### Step 1: Build Locally

Build the Docker image on your local machine without pushing to AWS:

```batch
cd C:\Vijay\Work\Clipforge\opus-clip\deployment
build-local.bat
```

**What it does:**
- Builds Docker image with tag `opus-process-clip:local-test`
- Removes old local test image (forces fresh build)
- Shows image size and build information
- Does NOT push to ECR or deploy to Lambda

**Output:**
```
========================================
SUCCESS: Local Image Built!
========================================

Image Name: opus-process-clip:local-test
Image Size: 1024 MB
```

**Time:** 5-10 minutes first build, 2-3 minutes subsequent builds

---

### Step 2: Smoke Test (Quick)

Verify the container starts and modules load correctly:

```batch
smoke-test-local.bat
```

**What it does:**
- Tests if Python runs
- Tests if Lambda handler imports
- Tests if classification system loads
- Shows plugin statistics
- **No AWS credentials needed**
- **No video processing**

**Output:**
```
✓ Lambda handler loaded
✓ Classification service loaded
✓ Classification system initialized
  Total plugins: 25
  Active plugins: 7
  Error plugins: 0
```

**Time:** ~30 seconds

---

### Step 3: Full Integration Test (Optional)

Run the container locally with Lambda Runtime Interface Emulator:

```batch
test-local-container.bat
```

**What it does:**
- Starts container with Lambda RIE on port 9000
- Mounts local `/tmp` directory
- Passes AWS credentials from your environment
- Waits for Lambda invocations

**Requirements:**
- AWS credentials configured
- Test video in S3
- `test-event.json` file present

**How to invoke:**

Open a NEW terminal while container is running:

**Using curl:**
```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d @../test-event.json
```

**Using PowerShell:**
```powershell
$event = Get-Content ..\test-event.json -Raw
Invoke-RestMethod -Uri "http://localhost:9000/2015-03-31/functions/function/invocations" -Method Post -Body $event
```

**Time:** Depends on video length (usually 30-120 seconds per clip)

---

## Test Event Format

Create `test-event.json` in the root directory:

```json
{
  "session_id": "test-local-123",
  "s3_video_key": "videos/test-video.mp4",
  "template_id": "prof-modern-minimal",
  "clip": {
    "clip_index": 0,
    "start": 10.0,
    "end": 40.0,
    "duration": 30.0,
    "text": "Today I'm going to show you how to make chocolate chip cookies",
    "segments": [
      {
        "start": 10.0,
        "end": 15.0,
        "text": "Today I'm going to show you",
        "words": [
          {"start": 10.0, "end": 10.5, "word": "Today"},
          {"start": 10.6, "end": 11.0, "word": "I'm"}
        ]
      }
    ]
  }
}
```

---

## Debugging Container Issues

### Inspect the Container

Open a shell inside the container:

```batch
docker run -it --rm opus-process-clip:local-test /bin/bash
```

Inside the container:
```bash
# Check Python version
python --version

# Test imports
python -c "from lambda_function import lambda_handler; print('OK')"

# Check file structure
ls -la /var/task/
ls -la /var/task/classification/

# Test classification manually
python -c "
from classification import get_classification_service
service = get_classification_service()
service.initialize()
print(service.get_plugin_stats())
"
```

### Check Container Logs

Run container with verbose logging:

```batch
docker run --rm -e LOG_LEVEL=DEBUG opus-process-clip:local-test
```

### Verify Container Contents

List files in the image:

```batch
docker run --rm opus-process-clip:local-test ls -la /var/task/
```

Check Python packages:

```batch
docker run --rm opus-process-clip:local-test pip list
```

---

## Comparison: Local vs AWS Deployment

| Feature | Local Testing | AWS Deployment |
|---------|--------------|----------------|
| **Build Time** | 5-10 min | 5-10 min + 2-3 min push |
| **Testing** | Immediate | Requires deployment |
| **Debugging** | Easy (shell access) | CloudWatch logs only |
| **Cost** | Free | Lambda + S3 costs |
| **Iteration** | Fast | Slower |
| **AWS Resources** | None needed | S3, ECR, Lambda |
| **Network** | Local only | AWS network |

---

## Development Workflow

### Recommended: Test Locally First

```batch
# 1. Make code changes
# 2. Build locally
build-local.bat

# 3. Quick smoke test
smoke-test-local.bat

# 4. If smoke test passes, full integration test (optional)
test-local-container.bat

# 5. If all tests pass, deploy to AWS
build-and-push-container.bat
```

### Quick Iteration (No AWS Deploy)

For rapid development without AWS deployment:

```batch
# 1. Make code changes
# 2. Build locally
build-local.bat

# 3. Test immediately
smoke-test-local.bat
```

This cycle takes ~3-5 minutes total.

---

## Common Issues

### Issue: "Docker is not running"

**Solution:**
- Start Docker Desktop
- Wait for it to fully initialize
- Try again

### Issue: "Local test image not found"

**Solution:**
- Run `build-local.bat` first
- Image must be built before testing

### Issue: "Classification system import failed"

**Possible causes:**
- Classification directory not included in Docker image
- Check `Dockerfile.process-clip` copies classification folder
- Rebuild image: `build-local.bat`

**Verify:**
```batch
docker run --rm opus-process-clip:local-test ls -la /var/task/classification/
```

### Issue: "AWS credentials not found" (full integration test)

**Solution:**

Set AWS credentials in environment:

```batch
set AWS_ACCESS_KEY_ID=your_key
set AWS_SECRET_ACCESS_KEY=your_secret
set AWS_REGION=us-east-1
```

Or configure AWS CLI:
```batch
aws configure
```

### Issue: Container runs but Lambda doesn't respond

**Check:**
1. Container is running on port 9000
2. No firewall blocking localhost:9000
3. Test with simple curl: `curl http://localhost:9000`

---

## Performance Testing

### Measure Classification Performance

Test classification speed locally:

```batch
docker run --rm opus-process-clip:local-test python -c "
import time
from classification import get_classification_service

service = get_classification_service()
service.initialize()

# Test clip
clip_info = {
    'clip': {
        'text': 'oh my god that was such a clutch play! gg guys!',
        'duration': 20.0,
        'segments': []
    }
}

start = time.time()
classification, strategy = service.classify_quick(clip_info)
elapsed = (time.time() - start) * 1000

print(f'Classification: {classification.category}')
print(f'Confidence: {classification.confidence:.2f}')
print(f'Time: {elapsed:.1f}ms')
"
```

Expected output:
```
Classification: gaming
Confidence: 0.77
Time: 5.2ms
```

---

## Clean Up

### Remove Local Test Images

```batch
docker rmi opus-process-clip:local-test
```

### Remove All Unused Images

```batch
docker image prune -a
```

### Clear Docker Build Cache

```batch
docker builder prune -a
```

---

## Summary

✅ **Use `build-local.bat`** to build without AWS
✅ **Use `smoke-test-local.bat`** for quick validation (30 seconds)
✅ **Use `test-local-container.bat`** for full integration test (with AWS)
✅ **Use `build-and-push-container.bat`** when ready to deploy

Local testing saves time and AWS costs during development! 🚀
