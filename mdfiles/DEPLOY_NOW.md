# 🚀 Deploy WebSocket Fix - Do This NOW

## The Problem
Your WebSocket connects but backend isn't sending messages because:
1. ❌ WebSocket handler requires `user_id` (now fixed)
2. ❌ Lambda functions don't have the WebSocket notification fix
3. ❌ Lambda Layer not updated

## Quick Fix - 3 Steps

### Step 1: Deploy WebSocket Handler (2 minutes)

**File**: `C:\Projects\reframeAI\opus-clip-cloud\src\websocket-handler\websocket-handler-fixed.zip`

1. **AWS Console** → **Lambda** → **Functions** → Find `websocket-handler` (or similar name like `VideoProcessingWebSocketHandler`)
2. **Click "Upload from"** → **".zip file"**
3. Select: `websocket-handler-fixed.zip`
4. **Click "Save"**

**What I fixed**: Made `user_id` optional - now accepts subscribe with just `session_id`

---

### Step 2: Create Lambda Layer (3 minutes)

**File**: `C:\Projects\reframeAI\opus-clip-cloud\src\shared-utilities-layer-websocket-fix.zip` (25KB)

1. **AWS Console** → **Lambda** → **Layers** → **"Create layer"**
2. **Fill in**:
   - Name: `shared-utilities-websocket-fix`
   - Description: `Fixed WebSocket notification format`
   - Upload: `shared-utilities-layer-websocket-fix.zip`
   - Compatible runtimes: Check `Python 3.11` and `Python 3.12`
3. **Click "Create"**
4. **Copy the Layer ARN** (you'll need it next)

---

### Step 3: Update Lambda Functions (5 minutes)

#### A. transcribe-apis Lambda

1. **Go to**: Lambda → Functions → `transcribe-apis`

2. **Update code**:
   - Click **"Upload from"** → **".zip file"**
   - Select: `C:\Projects\reframeAI\opus-clip-cloud\src\transcribe-apis\transcribe-apis-with-requests.zip` (1.07MB)
   - Click **"Save"**

3. **Update layer**:
   - Scroll to **Layers** section
   - Click **"Edit"** (or remove old layer if exists)
   - Click **"Add a layer"**
   - Select **"Custom layers"**
   - Choose: `shared-utilities-websocket-fix`
   - Version: `1`
   - Click **"Add"**

4. **Add environment variable**:
   - Go to **Configuration** → **Environment variables**
   - Click **"Edit"**
   - Add new variable:
     ```
     Key: WEBSOCKET_API_ENDPOINT
     Value: wss://dye394x0nd.execute-api.us-east-1.amazonaws.com/prod
     ```
   - Click **"Save"**

#### B. detect-clips Lambda

Repeat the same steps as above:
1. Don't need to upload code (unless you have a new version)
2. **Add the layer**: `shared-utilities-websocket-fix`
3. **Add environment variable**: `WEBSOCKET_API_ENDPOINT` = `wss://dye394x0nd.execute-api.us-east-1.amazonaws.com/prod`

---

## Test It!

1. **Open your app** with DevTools Console (F12)
2. **Upload a new video** and click "Generate Clips"
3. **Watch the console**:

**Expected logs (SUCCESS)**:
```
[WebSocket] Connecting to wss://dye394x0nd...
[WebSocket] ✅ Connected successfully!
[WebSocket] 📤 Sending subscribe message for session: abc123

// ⭐ YOU SHOULD NOW SEE THESE:
[WebSocket] 📥 Raw message received: {"event":"processing_progress","status":"transcribing","data":{...}}
[WebSocket] 📦 Parsed message: {event: "processing_progress", status: "transcribing"}
[useVideoStatus] 📥 Message received: {...}
[useVideoStatus] ✏️ Updating status: transcribing
[ProjectDetails] 🔄 WebSocket State Changed: {wsStatus: "transcribing", wsProgress: 20, isConnected: true}
```

4. **Watch the UI** - stages should animate in real-time!

---

## Quick Reference

### Files to Deploy:

| File | Size | Deploy To | Priority |
|------|------|-----------|----------|
| `websocket-handler-fixed.zip` | 1.4KB | websocket-handler Lambda | ⭐ HIGH |
| `shared-utilities-layer-websocket-fix.zip` | 25KB | Create new Layer | ⭐ HIGH |
| `transcribe-apis-with-requests.zip` | 1.07MB | transcribe-apis Lambda | ⭐ HIGH |

### Environment Variable (Add to ALL Lambda functions):
```bash
WEBSOCKET_API_ENDPOINT=wss://dye394x0nd.execute-api.us-east-1.amazonaws.com/prod
```

---

## Troubleshooting

### Still no messages after deployment?

**Check CloudWatch Logs**:

1. **WebSocket Handler Logs**:
   - Look for: `Subscribed connection {id} to session {session_id}`
   - If missing: WebSocket handler not deployed

2. **transcribe-apis Logs**:
   - Look for: `Sending progress notification: transcribing 20%`
   - Look for: `Notified X clients for session {session_id}`
   - If missing: Layer not attached or env var not set

### "No module named requests" error?
→ Lambda code not updated with `transcribe-apis-with-requests.zip`

### Subscribe action returning 400 error?
→ WebSocket handler not updated with the fix

---

## What Each Fix Does

1. **WebSocket Handler**: Now accepts subscribe with just `session_id` (user_id optional)
2. **Lambda Layer**: Includes fixed `websocket_notifier.py` that sends `status` field
3. **transcribe-apis code**: Updated to call notification function with correct parameters
4. **Environment variable**: Tells Lambda where to send WebSocket messages

---

## Expected Flow After Deployment

```
User uploads video
  ↓
Frontend WebSocket connects
  ↓
Frontend sends subscribe message
  ↓
WebSocket handler saves connection to DynamoDB ✅
  ↓
Lambda functions process video
  ↓
Lambda calls notify_processing_progress(session_id, 'transcribing', 20)
  ↓
websocket_notifier looks up connections in DynamoDB
  ↓
Sends message to API Gateway Management API
  ↓
Frontend receives message: {"status": "transcribing", "progress": 20}
  ↓
UI updates stage animation 🎉
```

---

## Deploy in This Order

1. ✅ **WebSocket Handler** (fixes subscribe action)
2. ✅ **Lambda Layer** (fixes notification format)
3. ✅ **Lambda Functions** (use fixed layer + env var)

**Total time**: ~10 minutes

After deployment, **test immediately** and you should see real-time updates! 🚀
