# 🔧 FIX MISSING CLOUDWATCH METRICS

## Problem
Only **AIAPICall** and **AIAPILatency** metrics showing in CloudWatch.
Missing: **TranscriptionTime**, **ClipDetectionTime**, **ClipsGenerated**, **VideoProcessingComplete**, **ClipProcessingTime**

## Root Cause
1. **transcribe-apis Lambda**: `track_ai_api_call()` missing `session_id` parameter (line 525)
2. **process-clip Lambda**: Imports `track_clip_processing_time` but never calls it

## ✅ Fixed Files
- `C:\Projects\reframeAI\opus-clip-cloud\src\transcribe-apis\lambda_function.py` ✅
- `C:\Projects\reframeAI\opus-clip-cloud\src\process-clip\lambda_function.py` ✅

---

## 📦 STEP 1: Re-deploy transcribe-apis Lambda

### 1.1 Create ZIP file

```batch
cd C:\Projects\reframeAI\opus-clip-cloud\src\transcribe-apis
powershell Compress-Archive -Path * -DestinationPath transcribe-apis.zip -Force
```

### 1.2 Upload to Lambda

1. **AWS Console** → **Lambda** → **opus-transcribe**
2. **Code** tab → **Upload from** → **.zip file**
3. Click **Upload**, select `transcribe-apis.zip`
4. Click **Save**
5. Wait for upload to complete (green banner: "Successfully updated function...")

### 1.3 Verify Layer is attached

1. Scroll to **Layers** section (below Code source)
2. Should show: `shared-utilities:X` (latest version)
3. If missing, click **Add a layer** → **Custom layers** → `shared-utilities` → **Latest version** → **Add**

---

## 🐳 STEP 2: Re-deploy process-clip Lambda (Docker)

**NOTE**: This Lambda uses Docker image deployed via ECR, not a simple .zip file.

### 2.1 Check your deployment method

You have 2 options:

#### **Option A: ECR Deployment (Recommended - Production)**

If you're using ECR (Amazon Elastic Container Registry), you need to rebuild and push the Docker image.

**Required**:
- Docker Desktop installed and running
- AWS CLI configured with ECR access

**Steps**:

```batch
cd C:\Projects\reframeAI\opus-clip-cloud\src\process-clip

REM Build Docker image
docker build -t opus-process-clip .

REM Tag for ECR (replace with your ECR URI)
docker tag opus-process-clip:latest YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip:latest

REM Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

REM Push to ECR
docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip:latest

REM Update Lambda to use new image
aws lambda update-function-code --function-name opus-process-clip --image-uri YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip:latest
```

**Find your ECR URI**:
1. AWS Console → **ECR** (Elastic Container Registry)
2. Find repository: **opus-process-clip**
3. Copy the **URI** (e.g., `123456789012.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip`)

#### **Option B: Direct Code Update (Quick Fix - Testing)**

If you don't have Docker/ECR setup, you can update just the `lambda_function.py` file:

1. **AWS Console** → **Lambda** → **opus-process-clip**
2. **Code** tab → Find `lambda_function.py` in the file tree
3. Click on `lambda_function.py` to open it
4. Replace lines 475-486 with:

```python
        print(f"[ProcessClip] Preserved metadata - Title: {result.get('title', 'None')}, Virality: {result.get('virality_score', 'None')}")

        # Track metrics
        if UTILITIES_AVAILABLE:
            try:
                track_clip_processing_time(session_id, clip_index, int(total_time * 1000))
                if logger:
                    logger.info("Clip processing complete", session_id=session_id, clip_index=clip_index, duration=total_time)
            except Exception as e:
                print(f"[ProcessClip] Warning: Metrics tracking failed: {e}")

        return result
```

5. Click **Deploy** button (orange button at top right)

**⚠️ WARNING**: This only updates the Python code, not dependencies. For production, use Option A (ECR).

---

## 🧪 STEP 3: Test End-to-End

### 3.1 Upload a test video

1. Go to your dashboard
2. Upload a short YouTube video (1-3 minutes)
3. Wait for processing to complete

### 3.2 Check CloudWatch Metrics

Wait 2-3 minutes, then:

1. **AWS Console** → **CloudWatch** → **Metrics** → **All metrics**
2. **Custom namespaces** → **VideoProcessing**
3. Click **All metrics**

**Expected Metrics (Should see ALL of these)**:
- ✅ **AIAPICall** - AI API usage count
- ✅ **AIAPILatency** - AI API response times
- ✅ **TranscriptionTime** - Transcription duration ← **NEW**
- ✅ **ClipDetectionTime** - Clip detection duration
- ✅ **ClipsGenerated** - Number of clips created ← **NEW**
- ✅ **VideoProcessingComplete** - Completion count ← **NEW**
- ✅ **ClipProcessingTime** - Individual clip processing duration ← **NEW**

### 3.3 Check Lambda Logs

For each Lambda, check CloudWatch Logs for metrics being published:

**transcribe-apis Lambda**:
```
[Transcribe] Complete in 12.5s
Published metric: TranscriptionTime=12500 Milliseconds
Published metric: AIAPICall=1 Count
Published metric: AIAPILatency=497 Milliseconds
```

**detect-clips Lambda**:
```
[Detect] Clip detection complete
Published metric: ClipDetectionTime=2253 Milliseconds
```

**finalize Lambda**:
```
[Finalize] Complete! Generated 3 download URLs
Published metric: VideoProcessingComplete=1 Count
Published metric: ClipsGenerated=3 Count
```

**process-clip Lambda**:
```
[TIMING] TOTAL: 45.32s
Published metric: ClipProcessingTime=45320 Milliseconds
```

---

## ✅ Success Criteria

After deployment, you should see:

1. ✅ All 7 metrics in CloudWatch → VideoProcessing namespace
2. ✅ "Published metric" logs in all Lambda CloudWatch Logs
3. ✅ No errors in Lambda execution
4. ✅ Video processing completes successfully with clips

---

## 🐛 Troubleshooting

### Issue: Still only seeing AIAPICall and AIAPILatency

**Fix 1**: Check IAM permissions
- **Lambda Console** → Function → **Configuration** → **Permissions**
- Click on **Execution role** name
- Verify policy has: `cloudwatch:PutMetricData`

**Fix 2**: Check Lambda Layer version
- **Lambda Console** → Function → **Layers**
- Should show latest version (probably v6 or v7)
- If old version, click **Edit** → Change to latest → **Save**

**Fix 3**: Check for errors in metrics.py
- **Lambda Console** → Function → **Monitor** → **View CloudWatch logs**
- Search for "Metrics tracking failed" or "put_metric error"

### Issue: process-clip metrics still missing after Option B update

**Solution**: You must use **Option A (ECR deployment)** for process-clip Lambda.
The inline editor only updates Python code, but the Lambda Layer with `track_clip_processing_time` needs to be in the Docker image.

---

## 📊 Verification Dashboard

Create a CloudWatch Dashboard to monitor all metrics:

**CloudWatch Console** → **Dashboards** → **Create dashboard** → **Add widget**

**Metrics to add**:
1. VideoProcessing > AIAPICall (Sum, 5 min)
2. VideoProcessing > AIAPILatency (Average, 5 min)
3. VideoProcessing > TranscriptionTime (Average, 5 min)
4. VideoProcessing > ClipDetectionTime (Average, 5 min)
5. VideoProcessing > ClipProcessingTime (Average, 5 min)
6. VideoProcessing > ClipsGenerated (Sum, 1 hour)
7. VideoProcessing > VideoProcessingComplete (Sum, 1 hour)

---

## 🎉 Done!

All CloudWatch metrics should now be working. You can track:
- API usage and latency
- Transcription performance
- Clip detection speed
- Clip processing time
- Total clips generated
- Completion rate

**Next**: Monitor metrics for 24 hours to ensure stability.
