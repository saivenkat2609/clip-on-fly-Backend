# 🔍 WebSocket Real-Time Updates - Debug Guide

## ✅ What I Added

I've added **comprehensive debugging** throughout the entire WebSocket chain to help identify why real-time updates aren't working.

---

## 📊 Visual Debug Panel

At the bottom of the processing card, you'll now see:

```
Connected • Live updates
─────────────────────────────────────
WS Status: downloading
Progress: 23%
Stage: Downloading
SessionID: 8cd95b72...
```

This shows **live** values from the WebSocket connection.

---

## 🔍 Console Logs to Check

Open **Browser DevTools** (F12) → **Console** tab and look for these logs:

### 1. **WebSocket URL Configuration**
```
[createVideoWebSocket] Initializing WebSocket: {
  url: "wss://xxxxx.execute-api.us-east-1.amazonaws.com/prod",
  isDefault: false,
  envVarSet: true
}
```

**✅ If `envVarSet: true`**: WebSocket URL is configured
**❌ If `envVarSet: false`**: **PROBLEM! VITE_WEBSOCKET_URL not set**

---

### 2. **WebSocket Connection**
```
[WebSocket] Connecting to wss://xxxxx...
[WebSocket] ✅ Connected successfully!
[WebSocket] Session ID: 8cd95b72-15c3-49fc-8ecc-8f26ec935fbc
[WebSocket] 📤 Sending subscribe message for session: 8cd95b72...
```

**✅ If you see "Connected successfully"**: Connection established
**❌ If you see errors or no connection**: WebSocket URL is wrong or backend not running

---

### 3. **Incoming Messages**
```
[WebSocket] 📥 Raw message received: {"event":"processing_progress","session_id":"abc123","status":"downloading","data":{"progress":23}}
[WebSocket] 📦 Parsed message: {
  event: "processing_progress",
  session_id: "abc123",
  status: "downloading",
  data: {progress: 23}
}
[useVideoStatus] 📥 Message received: {...}
[useVideoStatus] ✏️ Updating status: downloading
[ProjectDetails] 🔄 WebSocket State Changed: {
  wsStatus: "downloading",
  wsProgress: 23,
  isConnected: true
}
```

**✅ If you see messages**: Backend IS sending updates!
**❌ If no messages**: Backend not sending or wrong session ID

---

### 4. **Stage Updates**
```
[ProjectDetails] WebSocket status: downloading → Stage index: 0
[ProjectDetails] WebSocket status: transcribing → Stage index: 1
```

**✅ If you see stage changes**: UI should animate!
**❌ If stuck on stage 0**: Backend not progressing or status names don't match

---

## 🚨 Common Issues & Fixes

### **Issue 1: `envVarSet: false`**

**Problem**: `VITE_WEBSOCKET_URL` environment variable not set

**Fix**: Check `.env` file in `reframe-ai/` folder:
```bash
# reframe-ai/.env
VITE_WEBSOCKET_URL=wss://your-websocket-id.execute-api.us-east-1.amazonaws.com/prod
```

**Important**:
- Must start with `VITE_` prefix
- Restart dev server after changing `.env`
- For production, set in deployment environment

---

### **Issue 2: No Connection / Error Connecting**

**Problem**: WebSocket URL is wrong or API Gateway not deployed

**Logs**:
```
[WebSocket] Error: ...
[WebSocket] Reconnecting in 1000ms...
```

**Fix**: Verify WebSocket API Gateway exists:
1. **AWS Console** → **API Gateway** → Find WebSocket API
2. Copy the **WebSocket URL** (should look like `wss://xxxxx.execute-api.region.amazonaws.com/prod`)
3. Update `.env` file with correct URL

---

### **Issue 3: Connected But No Messages**

**Problem**: Backend Lambda not sending WebSocket notifications

**Logs**:
```
[WebSocket] ✅ Connected successfully!
[WebSocket] 📤 Sending subscribe message for session: abc123
... (no more messages)
```

**Fix**: Check if backend Lambdas are calling `notify_processing_progress()`:

```python
# In download/transcribe/detect Lambdas
from shared.websocket_notifier import notify_processing_progress

# Send progress update
notify_processing_progress(connection_id, session_id, "downloading", 25)
```

**Verify in CloudWatch Logs**:
```
[WebSocket] Sending progress notification: downloading 25%
```

---

### **Issue 4: Wrong Status Names**

**Problem**: Backend sends different status names than frontend expects

**Frontend expects**:
- `downloading`
- `transcribing`
- `detecting`
- `processing_clips`

**If backend sends** `download` instead of `downloading`, it won't match!

**Fix**: Update backend to use correct status names OR update frontend stages:

```typescript
// In ProjectDetails.tsx
const processingStages = [
  { id: 'download', label: 'Downloading', ... },  // Match backend
  { id: 'transcribe', label: 'Transcribing', ... },
  ...
];
```

---

### **Issue 5: WebSocket Not Enabled**

**Problem**: WebSocket hook disabled due to video status

**Logs**:
```
[ProjectDetails] WebSocket Config: {
  wsEnabled: false,  // ❌ PROBLEM!
  videoStatus: "completed"
}
```

**This is normal for completed videos!** WebSocket only enables when:
- `videoStatus === 'processing'`
- OR video data hasn't loaded yet

---

## 🧪 Step-by-Step Debug Process

1. **Open DevTools Console** (F12)

2. **Upload a new video** and click "Generate Clips"

3. **Check logs in this order**:

   **a) Configuration:**
   ```
   [createVideoWebSocket] Initializing WebSocket
   → Is envVarSet: true? ✅
   ```

   **b) Connection:**
   ```
   [WebSocket] Connecting to wss://...
   [WebSocket] ✅ Connected successfully!
   → Did it connect? ✅
   ```

   **c) Subscription:**
   ```
   [WebSocket] 📤 Sending subscribe message for session: abc123
   → Was session ID sent? ✅
   ```

   **d) Messages:**
   ```
   [WebSocket] 📥 Raw message received: ...
   → Are messages coming in? ✅
   ```

   **e) Status Updates:**
   ```
   [useVideoStatus] ✏️ Updating status: downloading
   → Is status being updated? ✅
   ```

   **f) UI Updates:**
   ```
   [ProjectDetails] 🔄 WebSocket State Changed
   → Is UI state changing? ✅
   ```

4. **Check Visual Debug Panel** at bottom of processing card:
   - Does "WS Status" show current status?
   - Does "Stage" show current stage name?
   - Is it updating in real-time?

---

## 📋 Quick Checklist

- [ ] `.env` file has `VITE_WEBSOCKET_URL` set
- [ ] WebSocket URL starts with `wss://`
- [ ] Dev server restarted after `.env` change
- [ ] Console shows "✅ Connected successfully!"
- [ ] Console shows "📤 Sending subscribe message"
- [ ] Console shows "📥 Raw message received"
- [ ] Console shows status updates (downloading → transcribing)
- [ ] Visual debug panel updates in real-time
- [ ] Stage animations work (active stage pops forward)

---

## 🎯 Expected Console Output (Success)

```
[createVideoWebSocket] Initializing WebSocket: {url: "wss://...", envVarSet: true}
[useVideoStatus] Initialized: {sessionId: "abc123", enabled: true}
[WebSocket] Connecting to wss://...
[WebSocket] ✅ Connected successfully!
[WebSocket] Session ID: abc123
[WebSocket] 📤 Sending subscribe message for session: abc123
[WebSocket] 📥 Raw message received: {"event":"processing_progress","status":"downloading"}
[WebSocket] 📦 Parsed message: {event: "processing_progress", status: "downloading"}
[useVideoStatus] 📥 Message received: {...}
[useVideoStatus] ✏️ Updating status: downloading
[ProjectDetails] 🔄 WebSocket State Changed: {wsStatus: "downloading", stage: 0}
[WebSocket] 📥 Raw message received: {"event":"processing_progress","status":"transcribing"}
[useVideoStatus] ✏️ Updating status: transcribing
[ProjectDetails] 🔄 WebSocket State Changed: {wsStatus: "transcribing", stage: 1}
```

---

## 🚀 Next Steps

1. **Upload a new video** with DevTools console open
2. **Copy all console logs** and share them
3. **Take screenshot** of visual debug panel
4. This will tell us exactly where the issue is!

The extensive logging will pinpoint the exact problem! 🎯
