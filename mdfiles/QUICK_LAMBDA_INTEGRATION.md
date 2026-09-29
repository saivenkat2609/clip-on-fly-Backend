# Quick Lambda Integration - Copy-Paste Ready Code

## ✅ detect-clips Lambda - ALREADY INTEGRATED!

The `detect-clips/lambda_function.py` is already fully integrated. No action needed!

---

## 📝 transcribe Lambda - Add These Sections

### 1. At Top (After line 11 - after `import warnings`):

```python
import sys

# Add Lambda Layer path
sys.path.insert(0, '/opt/python')

# Import scalability utilities (graceful fallback)
try:
    from logger import get_logger
    from metrics import track_transcription_time
    from websocket_notifier import notify_processing_progress
    from dynamodb_client import update_video_session
    from circuit_breaker import groq_circuit_breaker
    UTILITIES_AVAILABLE = True
    print("[Transcribe] Scalability utilities loaded successfully")
except ImportError as e:
    print(f"[Transcribe] Warning: Shared utilities not available: {str(e)}")
    UTILITIES_AVAILABLE = False
```

### 2. After `whisper_model = None` (around line 50):

```python
# Initialize logger if available
if UTILITIES_AVAILABLE:
    logger = get_logger('transcribe')
else:
    logger = None
```

### 3. In `lambda_handler` - Add at START (after getting session_id):

```python
user_id = event.get('user_id', 'unknown')

# Log start
if logger:
    logger.info("Starting transcription", session_id=session_id, user_id=user_id)

# Update status
if UTILITIES_AVAILABLE:
    try:
        update_video_session(session_id, user_id, status='transcribing', current_step='Transcribing audio')
        notify_processing_progress(session_id, 20, "Transcribing audio...")
    except:
        pass
```

### 4. In `lambda_handler` - Add BEFORE RETURN:

```python
# Track metrics
if UTILITIES_AVAILABLE:
    try:
        track_transcription_time(session_id, int((time.time() - start_total) * 1000))
        update_video_session(session_id, user_id, status='transcribed', current_step='Transcription complete')
    except:
        pass
```

### 5. In `transcribe_groq` function - Wrap API call (around line 159):

**REPLACE:**
```python
response = requests.post(url, headers=headers, data=data, files=files, timeout=120)
```

**WITH:**
```python
if UTILITIES_AVAILABLE:
    response = groq_circuit_breaker.call(
        lambda: requests.post(url, headers=headers, data=data, files=files, timeout=120)
    )
else:
    response = requests.post(url, headers=headers, data=data, files=files, timeout=120)
```

---

## 📝 finalize Lambda - Complete Integration Code

### Add at Top:

```python
import sys
sys.path.insert(0, '/opt/python')

try:
    from logger import get_logger
    from websocket_notifier import notify_processing_complete
    from dynamodb_client import update_video_session
    from metrics import track_video_processing_complete
    UTILITIES_AVAILABLE = True
    logger = get_logger('finalize')
    print("[Finalize] Scalability utilities loaded successfully")
except ImportError:
    UTILITIES_AVAILABLE = False
    logger = None
```

### In `lambda_handler` - Add at START:

```python
user_id = event.get('user_id', 'unknown')

if logger:
    logger.info("Finalizing clips", session_id=session_id)
```

### In `lambda_handler` - Add BEFORE RETURN:

```python
# Update session and notify
if UTILITIES_AVAILABLE:
    try:
        update_video_session(
            session_id, user_id,
            status='completed',
            current_step='All clips ready',
            clips_count=len(clips)
        )
        notify_processing_complete(session_id, {'total_clips': len(clips)})
        track_video_processing_complete(session_id, len(clips))
    except Exception as e:
        if logger:
            logger.warning("Failed to update session", error=str(e))

if logger:
    logger.info("Finalization complete", clip_count=len(clips))
```

---

## 📝 process-clip Lambda - Complete Integration Code

### Add at Top:

```python
import sys
sys.path.insert(0, '/opt/python')

try:
    from logger import get_logger
    from metrics import track_clip_processing_time
    from s3_utils import get_s3_prefix
    UTILITIES_AVAILABLE = True
    logger = get_logger('process-clip')
    print("[ProcessClip] Scalability utilities loaded successfully")
except ImportError:
    UTILITIES_AVAILABLE = False
    logger = None
```

### In `lambda_handler` - Update S3 Key Generation:

**REPLACE:**
```python
output_key = f"{session_id}/clips/clip_{clip_index}.mp4"
```

**WITH:**
```python
user_id = event.get('user_id', 'unknown')

if UTILITIES_AVAILABLE:
    prefix = get_s3_prefix(user_id, session_id)
    output_key = f"{prefix}/clips/clip_{clip_index}.mp4"
else:
    output_key = f"{session_id}/clips/clip_{clip_index}.mp4"
```

### In `lambda_handler` - Add at END:

```python
# Track metrics
if UTILITIES_AVAILABLE:
    try:
        track_clip_processing_time(
            session_id=session_id,
            duration_ms=int(processing_time * 1000),
            clip_index=clip_index
        )
    except:
        pass

if logger:
    logger.info("Clip processing complete", clip_index=clip_index)
```

---

## 📝 download Lambda - Complete Integration Code

### NOTE: Your download Lambda appears to be in Python (backup file). If it's Node.js, skip this.

### Add at Top:

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
    print("[Download] Scalability utilities loaded successfully")
except ImportError:
    UTILITIES_AVAILABLE = False
    logger = None
```

### In `lambda_handler` - Add at START:

```python
user_id = event.get('user_id', 'unknown')

if logger:
    logger.info("Starting download", session_id=session_id, url=youtube_url)

# Create session
if UTILITIES_AVAILABLE:
    try:
        create_video_session(
            session_id=session_id,
            user_id=user_id,
            youtube_url=youtube_url,
            status='downloading'
        )
        notify_processing_progress(session_id, 10, "Downloading video...")
    except:
        pass
```

### Update S3 Key Generation (around line 181):

**REPLACE:**
```python
s3_key = f"{session_id}/original_video.mp4"
```

**WITH:**
```python
if UTILITIES_AVAILABLE:
    prefix = get_s3_prefix(user_id, session_id)
    s3_key = f"{prefix}/original_video.mp4"
else:
    s3_key = f"{session_id}/original_video.mp4"
```

### Add BEFORE RETURN:

```python
# Track metrics
if UTILITIES_AVAILABLE:
    try:
        track_video_download_time(session_id, int((time.time() - start_time) * 1000))
    except:
        pass

if logger:
    logger.info("Download complete", session_id=session_id, size_mb=file_size_mb)
```

---

## ⚡ Super Quick Integration (5 minutes per Lambda)

For each Lambda function:

1. **Open the Lambda file**
2. **Copy-paste the "At Top" section** after imports
3. **Find the `lambda_handler` function**
4. **Add the "at START" code** right after getting session_id
5. **Add the "BEFORE RETURN" code** before the return statement
6. **Apply any specific changes** (like S3 key or API call wrapping)
7. **Save**

That's it! Deploy and you're done!

---

## ✅ Integration Checklist

- [x] detect-clips - Already done!
- [ ] transcribe - 5 sections to add
- [ ] finalize - 3 sections to add
- [ ] process-clip - 3 sections to add
- [ ] download - 4 sections to add (if Python)

**Total time:** ~20-30 minutes for all Lambdas

---

## 🧪 Test After Integration

For each Lambda, create a test event:

```json
{
  "session_id": "test-123",
  "user_id": "test-user",
  "s3_video_key": "test/video.mp4"
}
```

Run test and check CloudWatch Logs for:
- ✅ "Scalability utilities loaded successfully"
- ✅ Structured JSON log entries
- ✅ No import errors

---

## 🔄 If You Get Errors

**"Module not found"** → Make sure Lambda Layer is attached

**"UTILITIES_AVAILABLE is False"** → Check Layer has correct Python version (3.11)

**"Permission denied"** → Check IAM role has DynamoDB, Redis permissions

**Everything else works but no utilities** → That's fine! The code has graceful fallback.

---

## 💡 Pro Tip

You don't have to integrate all Lambdas at once! Start with one (like transcribe), test it, then do the others. Each Lambda is independent.
