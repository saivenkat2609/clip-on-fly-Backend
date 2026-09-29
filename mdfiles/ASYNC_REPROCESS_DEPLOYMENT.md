# Async Template Reprocessing - Deployment Guide

## Problem Solved
The reprocess-clip API was timing out with 503 errors because it waited for the entire reprocessing (which takes 1-2 minutes) to complete before returning.

## Solution
Made the reprocessing **asynchronous**:
1. API returns immediately with 202 Accepted
2. Processing happens in the background
3. UI polls result.json every 2 seconds to detect completion
4. User sees "Processing..." toast and updates automatically when done

---

## Files Changed

### 1. Backend: API Gateway Lambda
**File:** `opus-clip-cloud/src/api-gateway/lambda_function.py`

**Change:** Line 309 - Changed from synchronous to asynchronous invocation
```python
# OLD (waits for response):
InvocationType='RequestResponse'

# NEW (returns immediately):
InvocationType='Event'
```

**Deployment Package:** `api-gateway-async.zip`

### 2. Frontend: Reprocess Hook
**File:** `reframe-ai/src/hooks/useTemplateReprocess.ts`

**Changes:**
- Added `pollForResult()` function that polls `/result/{session_id}` every 2 seconds
- Updated `reprocessClip()` to:
  1. Call API (gets 202 response immediately)
  2. Show "Processing..." toast
  3. Poll until clip is updated with new template
  4. Show "Success!" toast when complete
  5. Return updated clip data to UI

**Max polling time:** 2 minutes (60 attempts × 2 seconds)

---

## Deployment Steps

### Step 1: Deploy Backend (AWS Lambda)

1. **Update opus-api-gateway Lambda:**
   ```
   AWS Lambda Console → opus-api-gateway → Upload from → .zip file
   File: C:\Projects\reframeAI\opus-clip-cloud\src\api-gateway\api-gateway-async.zip
   ```

2. **Verify environment variables on opus-reprocess-clip Lambda:**
   - Go to Configuration → Environment variables
   - Ensure these are set:
     - `R2_ENDPOINT`: Your Cloudflare R2 endpoint
     - `R2_ACCESS_KEY`: Your R2 access key
     - `R2_SECRET_KEY`: Your R2 secret key
     - `BUCKET_NAME`: `opus-clip-videos`

3. **Deploy opus-reprocess-clip Lambda (if not done yet):**
   ```
   AWS Lambda Console → opus-reprocess-clip → Upload from → .zip file
   File: C:\Projects\reframeAI\opus-clip-cloud\src\reprocess-clip\reprocess-clip-fixed-v2.zip
   ```

### Step 2: Deploy Frontend

The UI changes are already in your local code. Just deploy normally:

```bash
cd C:\Projects\reframeAI\reframe-ai
npm run build
# Deploy to your hosting (Vercel/Netlify/etc)
```

---

## How It Works

### User Flow:
1. User selects a new template for a clip
2. UI immediately shows: **"Processing Template... This may take 1-2 minutes"**
3. Loading spinner shows on the clip
4. Every 2 seconds, UI checks if reprocessing is done
5. When complete, shows: **"Template Changed!"**
6. Clip automatically updates with new download URL

### Technical Flow:
```
UI: POST /reprocess-clip
    ↓
API Gateway: Invoke opus-reprocess-clip async (202 response)
    ↓
UI: Poll GET /result/{session_id} every 2 seconds
    ↓
opus-reprocess-clip Lambda (background):
  - Load result.json
  - Load transcript.json
  - Reconstruct clip data
  - Invoke opus-process-clip (1-2 min)
  - Update result.json with new template
    ↓
UI: Detects template_id changed → Success!
```

---

## Testing

1. Deploy both backend and frontend
2. Go to a project with existing clips
3. Click the template icon on any clip
4. Select a different template
5. You should see:
   - ✅ "Processing Template..." toast immediately
   - ✅ Loading spinner on clip
   - ✅ After 1-2 minutes: "Template Changed!" toast
   - ✅ Clip updates with new video URL

---

## Troubleshooting

### Issue: Still getting 503 errors
**Solution:** Make sure you deployed the updated `api-gateway-async.zip` to the `opus-api-gateway` Lambda function

### Issue: Polling times out after 2 minutes
**Solution:** Check CloudWatch logs for `opus-reprocess-clip` to see if there are errors:
- Missing environment variables (R2 credentials)
- Transcript.json not found
- opus-process-clip Lambda errors

### Issue: Clip doesn't update in UI
**Solution:** Check browser console logs:
- Look for polling attempts
- Verify `/result/{session_id}` returns updated clip with new `template_id`
- Check if template modal closes properly

---

## Benefits

✅ **No more timeouts** - API returns immediately
✅ **Better UX** - Users see progress feedback
✅ **Resilient** - Continues working even if browser loses connection briefly
✅ **Scalable** - Can reprocess multiple clips simultaneously
✅ **Fast UI** - No blocking operations

---

## Future Enhancements

1. **WebSocket notifications** - Push updates instead of polling
2. **Progress percentage** - Show actual FFmpeg progress
3. **Batch reprocessing** - Apply template to all clips at once
4. **Template preview** - Show before/after comparison
