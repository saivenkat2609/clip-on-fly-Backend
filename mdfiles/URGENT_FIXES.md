# 🚨 Urgent Fixes Required

## Issue 1: Wrong WebSocket Protocol (FIXED - Restart Required)

### Problem
Your `.env` file had `https://` instead of `wss://` for the WebSocket URL, causing connection failures.

### What I Fixed
Changed line 11 in `reframe-ai/.env`:
```bash
# OLD (WRONG):
VITE_WEBSOCKET_URL=https://dye394x0nd.execute-api.us-east-1.amazonaws.com/prod

# NEW (CORRECT):
VITE_WEBSOCKET_URL=wss://dye394x0nd.execute-api.us-east-1.amazonaws.com/prod
```

### Action Required
**RESTART YOUR DEV SERVER**:
```bash
# Stop current server (Ctrl+C)
# Then restart:
cd reframe-ai
npm run dev
```

After restart, you should see in console:
```
[createVideoWebSocket] Initializing WebSocket: {url: 'wss://dye394x0nd...', ...}
[WebSocket] Connecting to wss://dye394x0nd...
[WebSocket] ✅ Connected successfully!
```

---

## Issue 2: Lambda "No Module Named Requests"

### Problem
The `transcribe-apis` Lambda function in AWS is missing the `requests` library.

### Solution
Redeploy the Lambda function with the correct package that includes dependencies.

### Action Required

#### Option A: Deploy via AWS Console (Recommended)

1. **Go to AWS Lambda Console**:
   - Navigate to **Lambda** → **Functions** → **`transcribe-apis`**

2. **Upload the deployment package**:
   - Click **"Upload from"** → **".zip file"**
   - Select: `C:\Projects\reframeAI\opus-clip-cloud\src\transcribe-apis\transcribe-apis-with-requests.zip` (1.07MB)
   - Click **"Save"**

3. **Update the Lambda Layer** (from previous fix):
   - Scroll to **Layers** section
   - **Remove old layer** (if exists): `shared-utilities-layer`
   - **Click "Add a layer"**:
     - Layer source: `Custom layers`
     - Custom layer: `shared-utilities-layer-websocket-fix`
     - Version: `1` (or create it first if you haven't yet)
   - **Click "Add"**

4. **Verify Environment Variables**:
   - Go to **Configuration** → **Environment variables**
   - Ensure `WEBSOCKET_API_ENDPOINT` is set to:
     ```
     wss://dye394x0nd.execute-api.us-east-1.amazonaws.com/prod
     ```
   - If missing, click **"Edit"** → **"Add environment variable"**

#### Option B: Deploy via AWS CLI

```bash
cd "C:\Projects\reframeAI\opus-clip-cloud\src\transcribe-apis"

# Update Lambda function code
aws lambda update-function-code \
  --function-name transcribe-apis \
  --zip-file fileb://transcribe-apis-with-requests.zip
```

---

## Issue 3: Deploy the WebSocket Fix

You also need to deploy the WebSocket notification fix from earlier.

### Steps:

1. **Create Lambda Layer** (if not done yet):
   - Go to **AWS Console** → **Lambda** → **Layers**
   - Click **"Create layer"**:
     - Name: `shared-utilities-layer-websocket-fix`
     - Description: `Fixed WebSocket notification format`
     - Upload: `C:\Projects\reframeAI\opus-clip-cloud\src\shared-utilities-layer-websocket-fix.zip`
     - Compatible runtimes: `Python 3.11`, `Python 3.12`
   - Click **"Create"**
   - **Note the Layer ARN**

2. **Update ALL Lambda Functions** to use the new layer:
   - **`transcribe-apis`** (already covered above)
   - **`detect-clips`** (repeat steps from above)
   - Any other Lambda functions using shared utilities

3. **Verify Environment Variable** in each Lambda:
   ```
   WEBSOCKET_API_ENDPOINT=wss://dye394x0nd.execute-api.us-east-1.amazonaws.com/prod
   ```

---

## Quick Checklist

### Frontend (Your Computer)
- [ ] Stop dev server (Ctrl+C)
- [ ] Verify `.env` has `wss://` (not `https://`)
- [ ] Restart dev server: `npm run dev`
- [ ] Test WebSocket connection in console

### Backend (AWS)

#### transcribe-apis Lambda:
- [ ] Upload `transcribe-apis-with-requests.zip` (1.07MB)
- [ ] Add/update layer: `shared-utilities-layer-websocket-fix`
- [ ] Verify env var: `WEBSOCKET_API_ENDPOINT=wss://...`
- [ ] Save and test

#### detect-clips Lambda:
- [ ] Add/update layer: `shared-utilities-layer-websocket-fix`
- [ ] Verify env var: `WEBSOCKET_API_ENDPOINT=wss://...`
- [ ] Save and test

---

## After Deployment - Test Again

1. **Restart frontend dev server** (if not already)
2. **Open DevTools Console** (F12)
3. **Upload a new video** and click "Generate Clips"
4. **Check console logs**:

   **Expected (SUCCESS)**:
   ```
   [WebSocket] Connecting to wss://dye394x0nd...
   [WebSocket] ✅ Connected successfully!
   [WebSocket] 📤 Sending subscribe message for session: abc123

   [WebSocket] 📥 Raw message received: {"status":"transcribing"}
   [useVideoStatus] ✏️ Updating status: transcribing
   [ProjectDetails] 🔄 WebSocket State Changed: {wsStatus: "transcribing", stage: 1}
   ```

5. **Watch the UI** - processing stages should update in real-time!

---

## Common Errors After Fix

### Still getting "https://" in console?
→ **Dev server not restarted**. Stop and restart it.

### Still getting "no module named requests"?
→ **Lambda not redeployed**. Upload `transcribe-apis-with-requests.zip` again.

### Connected but no messages?
→ **Lambda Layer not updated**. Ensure new layer is attached with WebSocket fix.

### Wrong protocol error?
→ **Environment variable in Lambda**. Must be `wss://` not `https://`.

---

## Summary of Changes

### Files Modified:
1. ✅ `reframe-ai/.env` - Fixed WebSocket URL (`wss://` instead of `https://`)
2. ✅ `shared/websocket_notifier.py` - Fixed notification function signature
3. ✅ `transcribe-apis/lambda_function.py` - Updated notification calls
4. ✅ `detect-clips/lambda_function.py` - Updated notification calls

### Deployment Packages:
- ✅ `shared-utilities-layer-websocket-fix.zip` (25KB) - New Lambda Layer
- ✅ `transcribe-apis-with-requests.zip` (1.07MB) - Existing, needs redeployment

### Action Items:
1. **Restart dev server** (required immediately)
2. **Redeploy transcribe-apis Lambda** with correct package
3. **Create and attach Lambda Layer** with WebSocket fix
4. **Verify environment variables** in all Lambda functions

---

Do these steps in order, and your real-time updates should start working! 🚀
