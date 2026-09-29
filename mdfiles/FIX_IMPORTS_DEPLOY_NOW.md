# 🚨 URGENT FIX - Import Errors Causing Missing Metrics

## The Problem
All Lambdas had **wrong import paths**. They were importing `from logger import...` instead of `from shared.logger import...`

This caused:
```
[Transcribe] Warning: Shared utilities not available: No module named 'logger'
```

**Result**: No metrics were published because utilities failed to load.

---

## ✅ FIXED - Ready to Deploy

All 3 Lambda functions have been fixed:
- ✅ **transcribe-apis** → Fixed imports, added missing `session_id` parameter
- ✅ **finalize** → Fixed imports
- ✅ **process-clip** → Fixed imports, added metrics tracking

---

## 🚀 DEPLOY NOW (3 Steps - 10 minutes)

### **STEP 1: Deploy transcribe-apis Lambda**

**File ready**: `C:\Projects\reframeAI\opus-clip-cloud\src\transcribe-apis\transcribe-apis.zip`

1. **AWS Console** → **Lambda** → **opus-transcribe**
2. **Code** tab → **Upload from** → **.zip file**
3. Select `transcribe-apis.zip`
4. Click **Save**
5. ✅ Wait for green banner: "Successfully updated function..."

**Verify Layer**:
- Scroll to **Layers** section
- Should show: `shared-utilities` (latest version)
- If missing: **Add a layer** → **Custom layers** → `shared-utilities` → Latest → **Add**

---

### **STEP 2: Deploy finalize Lambda**

**File ready**: `C:\Projects\reframeAI\opus-clip-cloud\src\finalize\finalize.zip`

1. **AWS Console** → **Lambda** → **opus-finalize**
2. **Code** tab → **Upload from** → **.zip file**
3. Select `finalize.zip`
4. Click **Save**
5. ✅ Wait for green banner

**Verify Layer**:
- Scroll to **Layers** section
- Should show: `shared-utilities` (latest version)
- If missing, add it

---

### **STEP 3: Deploy process-clip Lambda**

**This Lambda uses Docker (ECR deployment)**, so we have 2 options:

#### **Option A: Quick Fix (Direct Edit - 2 minutes)**

1. **AWS Console** → **Lambda** → **opus-process-clip**
2. **Code** tab → Find `lambda_function.py` in file tree (left side)
3. Click on `lambda_function.py` to open it
4. **Find line 21** (should say `from logger import get_logger`)
5. **Replace lines 21-23** with:

```python
    from shared.logger import get_logger
    from shared.metrics import track_clip_processing_time
    from shared.s3_utils import get_s3_prefix
```

6. **Find line 475** (should say `print(f"[ProcessClip] Preserved metadata...")`)
7. **Add AFTER line 475** (before `return result`):

```python

        # Track metrics
        if UTILITIES_AVAILABLE:
            try:
                track_clip_processing_time(session_id, clip_index, int(total_time * 1000))
                if logger:
                    logger.info("Clip processing complete", session_id=session_id, clip_index=clip_index, duration=total_time)
            except Exception as e:
                print(f"[ProcessClip] Warning: Metrics tracking failed: {e}")
```

8. Click **Deploy** (orange button at top right)
9. ✅ Wait for "Deployed successfully"

#### **Option B: Full Docker Rebuild (Production - 15 minutes)**

If you prefer proper ECR deployment:

```batch
cd C:\Projects\reframeAI\opus-clip-cloud\src\process-clip

REM Build image
docker build -t opus-process-clip .

REM Tag for ECR (replace YOUR_AWS_ACCOUNT_ID)
docker tag opus-process-clip:latest YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip:latest

REM Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

REM Push to ECR
docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip:latest

REM Update Lambda
aws lambda update-function-code --function-name opus-process-clip --image-uri YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/opus-process-clip:latest
```

**Find ECR URI**: AWS Console → ECR → Repositories → `opus-process-clip` → Copy URI

---

## 🧪 TEST IMMEDIATELY AFTER DEPLOYMENT

### 1. Upload a new test video
- Go to your dashboard
- Upload a **SHORT** YouTube video (1-2 minutes)
- **DO NOT use an old video** - must be new upload after deployment

### 2. Check Lambda logs for success

**transcribe-apis**:
1. AWS Console → Lambda → opus-transcribe → Monitor → View CloudWatch logs
2. Click **top log stream** (most recent)
3. **Look for**:
   ```
   [Transcribe] Scalability utilities loaded successfully
   Published metric: TranscriptionTime=...
   Published metric: AIAPICall=...
   Published metric: AIAPILatency=...
   ```
4. ✅ **Should NOT see**: `Warning: Shared utilities not available`

**finalize**:
1. AWS Console → Lambda → opus-finalize → Monitor → View CloudWatch logs
2. Click **top log stream**
3. **Look for**:
   ```
   [Finalize] Scalability utilities loaded successfully
   Published metric: ClipsGenerated=3 Count
   Published metric: VideoProcessingComplete=1 Count
   ```

**process-clip**:
1. AWS Console → Lambda → opus-process-clip → Monitor → View CloudWatch logs
2. Click **top log stream**
3. **Look for**:
   ```
   [ProcessClip] Scalability utilities loaded successfully
   Published metric: ClipProcessingTime=45320 Milliseconds
   ```

### 3. Check CloudWatch Metrics (after 2-3 min)

**CloudWatch Console** → **Metrics** → **Custom Namespaces** → **VideoProcessing** → **All metrics**

**Should now see ALL 7 metrics**:
- ✅ AIAPICall
- ✅ AIAPILatency
- ✅ **TranscriptionTime** ← NEW
- ✅ ClipDetectionTime
- ✅ **ClipsGenerated** ← NEW
- ✅ **VideoProcessingComplete** ← NEW
- ✅ **ClipProcessingTime** ← NEW

---

## 🐛 BONUS FIX: Groq API Error

Your logs also showed:
```
[Groq] ✗ Failed: Groq API error (400): {"error":{"message":"unknown param `timestamp_granularities`"}}
```

This is a **Groq API compatibility issue**. The Lambda is using AssemblyAI as fallback (which worked), but to fix Groq:

### Option 1: Use AssemblyAI (current fallback - works fine)
- Keep it as is, AssemblyAI worked perfectly
- Groq will auto-skip and fallback to AssemblyAI

### Option 2: Fix Groq API call (if you want Groq)

The Groq API doesn't support `timestamp_granularities` parameter. Need to update the API call format.

**I can fix this if you want**, but since AssemblyAI is working, it's not urgent.

---

## ✅ DEPLOYMENT CHECKLIST

- [ ] **STEP 1**: Upload `transcribe-apis.zip` to opus-transcribe Lambda
- [ ] **STEP 1b**: Verify Layer attached
- [ ] **STEP 2**: Upload `finalize.zip` to opus-finalize Lambda
- [ ] **STEP 2b**: Verify Layer attached
- [ ] **STEP 3**: Update opus-process-clip Lambda (Option A or B)
- [ ] **TEST**: Upload NEW test video (1-2 min)
- [ ] **VERIFY**: Check logs show "Scalability utilities loaded successfully"
- [ ] **VERIFY**: Check logs show "Published metric:" messages
- [ ] **VERIFY**: Check CloudWatch shows all 7 metrics

---

## 🎯 Expected Result

After deployment and test video processing, you'll see:

**Lambda Logs**:
```
[Transcribe] Scalability utilities loaded successfully ✅
[Finalize] Scalability utilities loaded successfully ✅
[ProcessClip] Scalability utilities loaded successfully ✅

Published metric: TranscriptionTime=12500 Milliseconds
Published metric: ClipsGenerated=3 Count
Published metric: VideoProcessingComplete=1 Count
Published metric: ClipProcessingTime=45320 Milliseconds
```

**CloudWatch Metrics**: 7 metrics total (up from 2)

---

## 🚨 If Still Not Working

1. **Check Lambda Layer version**:
   - Each Lambda → Layers section
   - Must be version 6 or 7 (latest)

2. **Check IAM permissions**:
   - Lambda → Configuration → Permissions
   - Execution role must have: `cloudwatch:PutMetricData`

3. **Send me the NEW logs** from all 3 Lambdas after deploying

---

**Start with STEP 1 now!** Upload `transcribe-apis.zip` first. 🚀
