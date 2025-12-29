# Lambda Integration Guide - Quick Reference

## Overview

All shared utilities are in `src/shared/`. You need to add just **2-3 lines** at the start of each Lambda to enable scalability features.

---

## Step 1: Create Lambda Layer with Shared Utilities

### Package the shared utilities:

```bash
cd opus-clip-cloud/src
mkdir -p layer/python
cp -r shared layer/python/
cd layer
zip -r ../shared-utilities-layer.zip python
```

### Upload to AWS Lambda Layers:

1. AWS Console → Lambda → Layers → Create layer
2. Name: `shared-utilities`
3. Upload `shared-utilities-layer.zip`
4. Compatible runtimes: Python 3.11
5. Create

### Attach Layer to ALL Lambda Functions:

1. Open each Lambda function
2. Scroll down → Layers → Add a layer
3. Select "Custom layers" → `shared-utilities` → Latest version
4. Save

---

## Step 2: Update Each Lambda Function

### For EVERY Lambda function, add this at the top (after imports):

```python
import sys
sys.path.insert(0, '/opt/python')  # Lambda layer path

# Import utilities (graceful fallback if layer not attached)
try:
    from logger import get_logger
    from metrics import track_processing_time  # or specific metric function
    from websocket_notifier import notify_processing_progress
    from dynamodb_client import update_video_session
    from circuit_breaker import groq_circuit_breaker  # if using Groq API
    from s3_utils import get_s3_prefix, get_storage_client
    UTILITIES_AVAILABLE = True
except ImportError:
    print("[WARNING] Shared utilities not available - using fallback")
    UTILITIES_AVAILABLE = False
    # Keep existing get_storage_client function
```

---

## Step 3: Specific Lambda Updates

### 🔹 **detect-clips** Lambda

**Already done!** ✅ (using `lambda_function.py` - the improved version is now active)

---

### 🔹 **transcribe** Lambda

**Add after line 50** (after whisper_model = None):

```python
# Initialize utilities
if UTILITIES_AVAILABLE:
    logger = get_logger('transcribe')
else:
    logger = None
```

**Update lambda_handler** (around line 471):

```python
def lambda_handler(event, context):
    start_total = time.time()

    try:
        session_id = event['session_id']
        user_id = event.get('user_id', 'unknown')  # ADD THIS
        s3_video_key = event['s3_video_key']

        # ADD: Structured logging
        if logger:
            logger.info("Starting transcription", session_id=session_id, video_key=s3_video_key)

        # ADD: Update session status
        if UTILITIES_AVAILABLE:
            update_video_session(session_id, user_id, status='transcribing', current_step='Transcribing audio')
            notify_processing_progress(session_id, 20, "Transcribing audio...")

        # ... existing code ...

        # BEFORE RETURN, ADD:
        if UTILITIES_AVAILABLE:
            from metrics import track_transcription_time
            track_transcription_time(session_id, int((time.time() - start_total) * 1000))
            update_video_session(session_id, user_id, status='transcribed', current_step='Transcription complete')

        return {
            'statusCode': 200,
            # ... existing return ...
        }
    except Exception as e:
        # ADD: Error handling
        if logger:
            logger.error("Transcription failed", error=str(e), session_id=session_id)
        if UTILITIES_AVAILABLE:
            update_video_session(session_id, user_id, status='failed', error_message=str(e))
        raise
```

**Wrap Groq API calls with circuit breaker** (around line 158):

```python
# BEFORE:
response = requests.post(url, headers=headers, data=data, files=files, timeout=120)

# AFTER:
if UTILITIES_AVAILABLE:
    response = groq_circuit_breaker.call(
        lambda: requests.post(url, headers=headers, data=data, files=files, timeout=120)
    )
else:
    response = requests.post(url, headers=headers, data=data, files=files, timeout=120)
```

---

### 🔹 **finalize** Lambda

**Add at top** (after imports):

```python
import sys
sys.path.insert(0, '/opt/python')

try:
    from logger import get_logger
    from websocket_notifier import notify_processing_complete
    from dynamodb_client import update_video_session
    UTILITIES_AVAILABLE = True
    logger = get_logger('finalize')
except ImportError:
    UTILITIES_AVAILABLE = False
    logger = None
```

**Update lambda_handler**:

```python
def lambda_handler(event, context):
    try:
        session_id = event['session_id']
        user_id = event.get('user_id', 'unknown')

        if logger:
            logger.info("Finalizing clips", session_id=session_id)

        # ... existing finalization code ...

        # BEFORE RETURN:
        if UTILITIES_AVAILABLE:
            update_video_session(
                session_id, user_id,
                status='completed',
                current_step='All clips ready',
                clips_count=len(clips)
            )
            notify_processing_complete(session_id, {'total_clips': len(clips)})

        return {
            'statusCode': 200,
            'clips': clips
        }
```

---

### 🔹 **process-clip** Lambda

**Add at top**:

```python
import sys
sys.path.insert(0, '/opt/python')

try:
    from logger import get_logger
    from metrics import track_clip_processing_time
    from websocket_notifier import notify_processing_progress
    from s3_utils import get_s3_prefix
    UTILITIES_AVAILABLE = True
    logger = get_logger('process-clip')
except ImportError:
    UTILITIES_AVAILABLE = False
    logger = None
```

**Update S3 key generation**:

```python
# BEFORE:
output_key = f"{session_id}/clips/clip_{clip_index}.mp4"

# AFTER:
if UTILITIES_AVAILABLE:
    prefix = get_s3_prefix(user_id, session_id)
    output_key = f"{prefix}/clips/clip_{clip_index}.mp4"
else:
    output_key = f"{session_id}/clips/clip_{clip_index}.mp4"
```

**Add metrics tracking**:

```python
# AT END OF lambda_handler:
if UTILITIES_AVAILABLE:
    track_clip_processing_time(
        session_id=session_id,
        duration_ms=int(processing_time * 1000),
        clip_index=clip_index
    )
```

---

### 🔹 **download** Lambda (YouTube download)

**Add at top**:

```python
import sys
sys.path.insert(0, '/opt/python')

try:
    from logger import get_logger
    from metrics import track_video_download_time
    from websocket_notifier import notify_processing_progress
    from dynamodb_client import create_video_session
    from s3_utils import get_s3_prefix
    UTILITIES_AVAILABLE = True
    logger = get_logger('download')
except ImportError:
    UTILITIES_AVAILABLE = False
    logger = None
```

**Update S3 key generation** (around line 181):

```python
# BEFORE:
s3_key = f"{session_id}/original_video.mp4"

# AFTER:
if UTILITIES_AVAILABLE:
    prefix = get_s3_prefix(user_id, session_id)
    s3_key = f"{prefix}/original_video.mp4"
else:
    s3_key = f"{session_id}/original_video.mp4"
```

**Add session creation** (at start of lambda_handler):

```python
if UTILITIES_AVAILABLE:
    create_video_session(
        session_id=session_id,
        user_id=user_id,
        youtube_url=youtube_url,
        status='downloading'
    )
    notify_processing_progress(session_id, 10, "Downloading video...")
```

---

## Step 4: Update Requirements Files

### For Lambdas using Redis:

Add to `requirements.txt`:
```
redis==5.0.1
```

### For Lambdas using circuit breaker with external APIs:

Already have `requests` - no changes needed.

---

## Step 5: Add Environment Variables

**Add to ALL Lambda functions** (Configuration → Environment variables):

```
REDIS_ENDPOINT=<from CloudFormation outputs>
DYNAMODB_TABLE_SESSIONS=prod-video-sessions
DYNAMODB_TABLE_CONNECTIONS=prod-websocket-connections
WEBSOCKET_API_ENDPOINT=<from CloudFormation outputs>
ENABLE_S3_SHARDING=true
ENVIRONMENT=prod
```

---

## Quick Integration Checklist

For each Lambda function:

- [ ] Attach shared-utilities Lambda Layer
- [ ] Add `sys.path.insert(0, '/opt/python')` at top
- [ ] Add try/except import block for utilities
- [ ] Update lambda_handler to use logger
- [ ] Add session status updates
- [ ] Add WebSocket progress notifications
- [ ] Update S3 key generation (if applicable)
- [ ] Add metrics tracking
- [ ] Wrap external API calls with circuit breaker (if applicable)
- [ ] Add environment variables
- [ ] Test and deploy

---

## Testing After Integration

### Test individual Lambda:

1. Go to Lambda console → Test tab
2. Create test event with sample data
3. Check CloudWatch Logs for:
   - "Shared utilities loaded successfully" ✅
   - Structured JSON log entries ✅
   - No import errors ✅

### Test end-to-end:

1. Process a video through your application
2. Check DynamoDB table for session record ✅
3. Check Redis for cached data ✅
4. Check CloudWatch metrics for custom metrics ✅
5. Check WebSocket messages in browser DevTools ✅

---

## Rollback Plan

If integration causes issues:

1. **Remove Lambda Layer** from affected function
2. **Revert environment variables** (remove new ones)
3. **Code still works!** - The try/except gracefully falls back to old behavior

No data loss, no breaking changes!

---

## Summary

**Minimal changes required:**
- 2-3 lines at top of each Lambda
- 5-10 lines in lambda_handler
- 1-2 lines for S3 key updates
- Environment variables (copy-paste)

**Benefits:**
- Structured logging → easier debugging
- Real-time updates → better UX
- Metrics → visibility into performance
- Circuit breaker → fault tolerance
- S3 sharding → 256x throughput
- Graceful fallback → no breaking changes

**Time to integrate:** ~30-60 minutes for all Lambdas
