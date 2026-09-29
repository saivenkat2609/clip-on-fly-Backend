# WebSocket Real-Time Updates - Fix Deployment Guide

## What Was Fixed

### Root Cause
The backend Lambda functions were sending WebSocket notifications with the **wrong data structure**. The frontend expected a `status` field (e.g., 'downloading', 'transcribing', 'detecting', 'processing_clips'), but the backend was only sending a `message` field.

### Files Modified

#### 1. **`opus-clip-cloud/src/shared/websocket_notifier.py`**
- **Line 176-209**: Updated `notify_processing_progress()` function signature
- **Changed from**:
  ```python
  def notify_processing_progress(
      session_id: str,
      progress: int,
      message: str,  # ❌ Wrong order, missing status
      endpoint_url: str = None
  )
  ```
- **Changed to**:
  ```python
  def notify_processing_progress(
      session_id: str,
      status: str,  # ✅ Status first (downloading, transcribing, detecting, processing_clips)
      progress: int = 0,
      message: str = None,
      endpoint_url: str = None
  ) -> int
  ```
- **Line 196-198**: Added status field to data object:
  ```python
  data = {
      'status': status,  # ✅ Send status field for frontend
      'progress': progress
  }
  ```
- **Line 119-121**: Extract status to root message level for frontend compatibility

#### 2. **`opus-clip-cloud/src/transcribe-apis/lambda_function.py`**
- **Line 487**: Updated call to include status:
  ```python
  notify_processing_progress(session_id, 'transcribing', 20, "Transcribing audio...")
  ```
- **Line 531**: Updated call to include status:
  ```python
  notify_processing_progress(session_id, 'transcribing', 100, "Transcription complete")
  ```

#### 3. **`opus-clip-cloud/src/detect-clips/lambda_function.py`**
- **Line 139-145**: Updated call to include status:
  ```python
  notify_processing_progress(
      session_id=session_id,
      status='detecting',  # ✅ Added
      progress=40,
      message="Analyzing transcript with AI...",
      endpoint_url=WEBSOCKET_API_ENDPOINT
  )
  ```
- **Line 266-272**: Updated call to include status:
  ```python
  notify_processing_progress(
      session_id=session_id,
      status='detecting',  # ✅ Added
      progress=60,
      message=f"Found {len(final_clips)} clips",
      endpoint_url=WEBSOCKET_API_ENDPOINT
  )
  ```

#### 4. **`opus-clip-cloud/src/detect-clips/lambda_function_improved.py`**
- **Line 127-133**: Updated call (same as above)
- **Line 254-260**: Updated call (same as above)

---

## Deployment Steps

### Step 1: Upload New Lambda Layer
1. **Navigate to AWS Console** → **Lambda** → **Layers**
2. **Click "Create layer"**:
   - Name: `shared-utilities-layer-websocket-fix`
   - Description: `Fixed WebSocket notification format for real-time status updates`
   - Upload the file: `C:\Projects\reframeAI\opus-clip-cloud\src\shared-utilities-layer-websocket-fix.zip` (25KB)
   - Compatible runtimes: `Python 3.11`, `Python 3.12`
3. **Click "Create"**
4. **Note the Layer ARN** (e.g., `arn:aws:lambda:us-east-1:123456789:layer:shared-utilities-layer-websocket-fix:1`)

### Step 2: Update Lambda Functions

Update the following Lambda functions to use the new layer:

#### A. **transcribe-apis Lambda**
1. Go to **Lambda** → **Functions** → **`transcribe-apis`**
2. Scroll to **Layers** section
3. **Remove old layer** (if exists): `shared-utilities-layer`
4. **Click "Add a layer"**:
   - Layer source: `Custom layers`
   - Custom layer: `shared-utilities-layer-websocket-fix`
   - Version: `1`
5. **Click "Add"**
6. **Verify environment variable**: `WEBSOCKET_API_ENDPOINT` is set to your WebSocket API URL

#### B. **detect-clips Lambda**
- Repeat the same steps as above
- Remove old layer, add new layer
- Verify `WEBSOCKET_API_ENDPOINT` environment variable

#### C. **node-download Lambda** (if exists)
- Repeat the same steps
- Verify `WEBSOCKET_API_ENDPOINT` environment variable

#### D. **Any other Lambda functions** that use the shared utilities layer
- Repeat the same process

### Step 3: Verify Environment Variables

For **EACH Lambda function**, verify the following environment variables are set:

```bash
WEBSOCKET_API_ENDPOINT=wss://your-websocket-id.execute-api.us-east-1.amazonaws.com/prod
```

To find your WebSocket API URL:
1. **AWS Console** → **API Gateway**
2. Find your WebSocket API (e.g., `VideoProcessingWebSocketAPI`)
3. Copy the **WebSocket URL** from the **Stages** section
4. Should look like: `wss://xxxxx.execute-api.us-east-1.amazonaws.com/prod`

### Step 4: Test the Fix

1. **Open your frontend application** with **DevTools Console** (F12)
2. **Upload a new video** and click **"Generate Clips"**
3. **Monitor console logs**:

   **Expected logs (SUCCESS)**:
   ```
   [createVideoWebSocket] Initializing WebSocket: {url: "wss://...", envVarSet: true}
   [WebSocket] Connecting to wss://...
   [WebSocket] ✅ Connected successfully!
   [WebSocket] 📤 Sending subscribe message for session: abc123

   [WebSocket] 📥 Raw message received: {"event":"processing_progress","status":"transcribing"}
   [WebSocket] 📦 Parsed message: {event: "processing_progress", status: "transcribing"}
   [useVideoStatus] 📥 Message received: {...}
   [useVideoStatus] ✏️ Updating status: transcribing
   [ProjectDetails] 🔄 WebSocket State Changed: {wsStatus: "transcribing", stage: 1}
   ```

4. **Check the visual debug panel** at the bottom of the processing card:
   - **WS Status** should update: `downloading` → `transcribing` → `detecting` → `processing_clips`
   - **Stage** should show current stage name
   - **Progress** should update in real-time

5. **Verify stage animations**:
   - Active stage should "pop forward" with scale transformation
   - Completed stages should fade back
   - Stage transitions should be smooth (700ms duration)

---

## Status Field Values

The backend must send one of these exact status values:

| Status Value | Frontend Stage | Description |
|--------------|----------------|-------------|
| `downloading` | Downloading | Video download in progress |
| `transcribing` | Transcribing | Audio transcription in progress |
| `detecting` | Detecting Clips | AI clip detection in progress |
| `processing_clips` | Processing Clips | Clip generation in progress |
| `completed` | (no stage) | Processing complete |
| `failed` | (no stage) | Processing failed |

---

## Troubleshooting

### Issue: Still No Messages After Deployment

**Check CloudWatch Logs** for the Lambda function:
1. **AWS Console** → **CloudWatch** → **Log groups**
2. Find log group: `/aws/lambda/transcribe-apis` (or relevant function)
3. Check for these logs:
   ```
   [WebSocket] Sending progress notification: transcribing 20%
   Notified X clients for session abc123
   ```

**If no WebSocket logs**:
- Verify `WEBSOCKET_API_ENDPOINT` environment variable is set
- Check that new Lambda Layer is attached
- Ensure Lambda function code includes the import: `from shared.websocket_notifier import notify_processing_progress`

### Issue: Connection Failed / GoneException

**Symptom**: Logs show `Connection {id} is gone (client disconnected)`

**Possible causes**:
1. Client disconnected before message sent (normal, will auto-reconnect)
2. WebSocket connection ID expired (normal, cleaned up automatically)

### Issue: Wrong Status Names

**Symptom**: Messages received but stage not updating

**Check**: Backend must send **exact** status names: `downloading`, `transcribing`, `detecting`, `processing_clips`
- ❌ Wrong: `download`, `transcribe`, `detect`
- ✅ Correct: `downloading`, `transcribing`, `detecting`

---

## Expected Message Format

### Backend sends:
```json
{
  "event": "processing_progress",
  "session_id": "06f0271e-3507-47f0-8785-bfb71a9a7b86",
  "timestamp": 1735318745,
  "status": "transcribing",
  "data": {
    "status": "transcribing",
    "progress": 20,
    "message": "Transcribing audio..."
  }
}
```

### Frontend expects:
- **`message.status`** OR **`message.data.status`** must be one of: `downloading`, `transcribing`, `detecting`, `processing_clips`
- **`message.data.progress`** (optional) for progress percentage (0-100)
- **`message.data.message`** (optional) for status message

---

## Summary

✅ **Fixed**: Backend `notify_processing_progress()` function signature
✅ **Fixed**: All Lambda function calls to include `status` parameter
✅ **Created**: New Lambda Layer with fixes
✅ **Ready**: Frontend already has comprehensive logging and animations

**Next**: Deploy the Lambda Layer and update Lambda functions to start receiving real-time status updates!

---

## Files Changed Summary

```
opus-clip-cloud/src/shared/websocket_notifier.py
  ├─ Line 176-209: Updated function signature
  └─ Line 196-198: Added status field to data

opus-clip-cloud/src/transcribe-apis/lambda_function.py
  ├─ Line 487: Updated call
  └─ Line 531: Updated call

opus-clip-cloud/src/detect-clips/lambda_function.py
  ├─ Line 139-145: Updated call
  └─ Line 266-272: Updated call

opus-clip-cloud/src/detect-clips/lambda_function_improved.py
  ├─ Line 127-133: Updated call
  └─ Line 254-260: Updated call
```

**Lambda Layer Package**: `shared-utilities-layer-websocket-fix.zip` (25KB)
**Location**: `C:\Projects\reframeAI\opus-clip-cloud\src\shared-utilities-layer-websocket-fix.zip`
