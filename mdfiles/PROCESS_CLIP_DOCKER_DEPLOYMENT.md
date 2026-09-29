# Process-Clip Docker Container Deployment

## ⚠️ Important Difference

**process-clip** Lambda is deployed as a **Docker container** (via ECR), not a zip file.

**Key differences:**
- ✅ **Zip-based Lambdas:** Use Lambda Layer for shared utilities
- ✅ **Container-based Lambdas:** Shared utilities baked into Docker image

**Lambda Layers don't work with container-based deployments!**

---

## ✅ Dockerfile Updated

The Dockerfile has been updated to include shared utilities:

**File:** `opus-clip-cloud/deployment/dockerfiles/Dockerfile.process-clip`

**What was added:**
```dockerfile
# Copy shared utilities (scalability features)
RUN mkdir -p /opt/python
COPY src/shared/ /opt/python/shared/

# Install dependencies
RUN pip install redis requests

# Add to Python path
ENV PYTHONPATH="${PYTHONPATH}:/opt/python"
```

This makes the shared utilities available at the same path (`/opt/python`) as Lambda Layers.

---

## 🚀 How to Deploy

### Step 1: Rebuild the Docker Image

```batch
cd C:\Projects\reframeAI\opus-clip-cloud\deployment
build-and-push-container.bat
```

**This will:**
1. Build Docker image with shared utilities
2. Authenticate to AWS ECR
3. Push image to ECR
4. Take 5-10 minutes on first build

**Output:**
```
Image URI: 930115312558.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip:latest
```

### Step 2: Update Lambda Function

After build-and-push completes, run:

```batch
cd C:\Projects\reframeAI\opus-clip-cloud\deployment
deploy-container-lambda.bat
```

**This updates the Lambda function to use the new container image.**

---

## 🔍 Verify It Works

After deployment:

1. **Go to Lambda Console** → `opus-process-clip`
2. **Test** tab → Create test event:
   ```json
   {
     "session_id": "test-123",
     "user_id": "test-user",
     "s3_video_key": "test.mp4",
     "clip_index": 0,
     "start": 0,
     "end": 10
   }
   ```
3. **Click Test**
4. **Check logs** for:
   ```
   [ProcessClip] Scalability utilities loaded successfully
   ```

---

## 📋 Environment Variables

Make sure these are set in the Lambda function:

```bash
# Cloudflare R2
BUCKET_NAME=opus-clip-videos
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY=<your-r2-access-key>
R2_SECRET_KEY=<your-r2-secret-key>

# DynamoDB
DYNAMODB_TABLE_SESSIONS=prod-video-sessions
DYNAMODB_TABLE_CONNECTIONS=prod-websocket-connections

# WebSocket
WEBSOCKET_API_ENDPOINT=https://xxxxx.execute-api.us-east-1.amazonaws.com/prod

# SQS
SQS_VIDEO_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/xxxxx/prod-video-processing-queue
SQS_UPLOAD_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/xxxxx/prod-upload-processing-queue

# Feature Flags
ENABLE_S3_SHARDING=true
ENVIRONMENT=prod

# FFmpeg paths (already in container)
FFMPEG_PATH=/usr/local/bin/ffmpeg
FFPROBE_PATH=/usr/local/bin/ffprobe
```

---

## 🎯 Summary

### For process-clip (Docker-based):
1. ✅ Shared utilities are in the Docker image (not Layer)
2. ✅ Run `build-and-push-container.bat` to rebuild
3. ✅ Run `deploy-container-lambda.bat` to update Lambda
4. ✅ No Lambda Layer needed!

### For other Lambdas (zip-based):
1. ✅ Attach Lambda Layer `shared-utilities`
2. ✅ Zip and upload via Console
3. ✅ Much faster to update

---

## ⏱️ Build Time

**First build:** 5-10 minutes (downloading base images, installing packages)
**Subsequent builds:** 2-3 minutes (using cache)

**The build script automatically:**
- ✅ Uses Docker layer caching
- ✅ Pulls latest image from ECR for cache
- ✅ Only rebuilds changed layers

---

## 🔧 Troubleshooting

### "Utilities not available"
**Cause:** Docker image wasn't rebuilt after Dockerfile update
**Fix:** Run `build-and-push-container.bat` again

### "Cannot find shared module"
**Cause:** PYTHONPATH not set correctly
**Fix:** Already fixed in updated Dockerfile. Rebuild.

### "Docker build failed"
**Cause:** Docker not running
**Fix:** Start Docker Desktop and try again

### "ECR authentication failed"
**Cause:** AWS CLI not configured
**Fix:** Run `aws configure` with your credentials

---

## 💡 Why Container for process-clip?

**process-clip uses Docker because:**
- ✅ Needs FFmpeg static binaries (400MB+)
- ✅ Needs OpenCV with system libraries
- ✅ Needs MediaPipe for face detection
- ✅ Total dependencies > 250MB (exceeds Lambda zip limit)

**Other Lambdas use zip because:**
- ✅ Small dependencies (<50MB each)
- ✅ Faster to update (no Docker build)
- ✅ Simpler deployment

---

## ✅ Next Steps

1. **Run:** `cd C:\Projects\reframeAI\opus-clip-cloud\deployment`
2. **Run:** `build-and-push-container.bat`
3. **Wait:** 5-10 minutes for build
4. **Run:** `deploy-container-lambda.bat`
5. **Test:** Upload a video and check it processes correctly

**Done!** Your process-clip Lambda now has all scalability features built-in! 🚀
