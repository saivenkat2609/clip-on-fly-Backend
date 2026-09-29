# 🚀 Enable Real-Time Clips in UI

## What This Does

**Currently**: All clips appear at once after processing completes (few minutes delay)

**After this fix**: Clips appear **one-by-one** in real-time as they're generated! 🎉

---

## How It Works

### Before:
```
process-clip Lambda → Uploads clip to S3 → Returns
process-clip Lambda → Uploads clip to S3 → Returns
process-clip Lambda → Uploads clip to S3 → Returns
(All 5 clips finish)
finalize Lambda → Updates Firestore with ALL clips at once
Frontend → Sees all 5 clips appear together
```

### After:
```
process-clip Lambda → Uploads clip to S3 → Updates Firestore immediately ✅
Frontend → Clip 1 appears! (real-time)

process-clip Lambda → Uploads clip to S3 → Updates Firestore immediately ✅
Frontend → Clip 2 appears! (real-time)

process-clip Lambda → Uploads clip to S3 → Updates Firestore immediately ✅
Frontend → Clip 3 appears! (real-time)
```

---

## 📦 STEP 1: Update Lambda Layer (3 minutes)

**New file created**: `C:\Projects\reframeAI\opus-clip-cloud\src\shared-utilities-layer-with-firestore.zip`

This includes:
- ✅ All previous utilities (logging, metrics, sharding, etc.)
- ✅ **NEW**: `firestore_client.py` for incremental clip updates

**Deploy it**:

1. **AWS Console** → **Lambda** → **Layers** → `shared-utilities`
2. Click **"Create version"**
3. **Upload** → Select `shared-utilities-layer-with-firestore.zip`
4. **Compatible runtimes**: Python 3.11
5. **Description**: "Real-time clips - incremental Firestore updates"
6. Click **"Create"**
7. ✅ **Note the version number** (e.g., v9)

---

## 🔧 STEP 2: Update process-clip Lambda (2 options)

### **Option A: Quick Code Edit** (Recommended - 5 minutes)

The process-clip Lambda code has already been updated in your local files. You just need to update the code in AWS:

1. **AWS Console** → **Lambda** → **opus-process-clip**
2. **Code** tab → Find `lambda_function.py`
3. **Update the import section** (around line 19-34):

Find:
```python
# Import scalability utilities (graceful fallback)
try:
    from shared.logger import get_logger
    from shared.metrics import track_clip_processing_time
    from shared.s3_utils import get_s3_prefix, get_clip_key
    UTILITIES_AVAILABLE = True
    print("[ProcessClip] Scalability utilities loaded successfully")
except ImportError as e:
    print(f"[ProcessClip] Warning: Shared utilities not available: {str(e)}")
    UTILITIES_AVAILABLE = False
    # Fallback for sharding function
    get_clip_key = lambda user_id, session_id, clip_index, aspect_ratio: f"{session_id}/clips/clip_{clip_index}_{aspect_ratio.replace(':', 'x')}.mp4"
```

Replace with:
```python
# Import scalability utilities (graceful fallback)
try:
    from shared.logger import get_logger
    from shared.metrics import track_clip_processing_time
    from shared.s3_utils import get_s3_prefix, get_clip_key
    from shared.firestore_client import add_clip_to_firestore
    UTILITIES_AVAILABLE = True
    FIRESTORE_AVAILABLE = True
    print("[ProcessClip] Scalability utilities loaded successfully")
except ImportError as e:
    print(f"[ProcessClip] Warning: Shared utilities not available: {str(e)}")
    UTILITIES_AVAILABLE = False
    FIRESTORE_AVAILABLE = False
    # Fallback for sharding function
    get_clip_key = lambda user_id, session_id, clip_index, aspect_ratio: f"{session_id}/clips/clip_{clip_index}_{aspect_ratio.replace(':', 'x')}.mp4"
    add_clip_to_firestore = lambda *args, **kwargs: False
```

4. **Add Firestore update code** (after line ~440, after `print(f"[TIMING] Upload: {upload_time:.2f}s")`):

Find:
```python
        print(f"[TIMING] Upload: {upload_time:.2f}s")

        # Clean up temp files
```

Replace with:
```python
        print(f"[TIMING] Upload: {upload_time:.2f}s")

        # Generate presigned URL for the clip
        download_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_clip_key},
            ExpiresIn=259200  # 3 days
        )

        # Add clip to Firestore immediately (for real-time UI updates)
        if FIRESTORE_AVAILABLE and user_id:
            print(f"[ProcessClip] Adding clip {clip_index} to Firestore for real-time updates...")
            clip_data = {
                'clip_index': clip_index,
                'download_url': download_url,
                's3_key': s3_clip_key,
                'title': clip.get('title'),
                'duration': clip.get('duration'),
                'startTime': clip.get('start'),
                'endTime': clip.get('end'),
                'virality_score': clip.get('virality_score'),
                'score_breakdown': clip.get('score_breakdown'),
                'template_id': template_id,
                'template_name': template.get('name', template_id)
            }

            firestore_success = add_clip_to_firestore(user_id, session_id, clip_data)
            if firestore_success:
                print(f"[ProcessClip] ✓ Clip {clip_index} added to Firestore successfully")
            else:
                print(f"[ProcessClip] ✗ Failed to add clip {clip_index} to Firestore (will be added by finalize)")
        else:
            print(f"[ProcessClip] Skipping Firestore update (not available or no user_id)")

        # Clean up temp files
```

5. Click **"Deploy"**
6. **Update Layer Version**:
   - Scroll to **Layers** section
   - Click layer name → **"Edit"**
   - **Version** → Select latest (from Step 1)
   - Click **"Save"**

### **Option B: Full Docker Rebuild** (15 minutes)

Only if you want proper production deployment with Docker:

```bash
cd C:\Projects\reframeAI\opus-clip-cloud\src\process-clip

docker build -t opus-process-clip .
docker tag opus-process-clip:latest YOUR_ECR_URI/opus-process-clip:latest
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_URI
docker push YOUR_ECR_URI/opus-process-clip:latest
aws lambda update-function-code --function-name opus-process-clip --image-uri YOUR_ECR_URI/opus-process-clip:latest
```

---

## ✅ STEP 3: Verify Environment Variables

Make sure **opus-process-clip** Lambda has:

1. **Lambda Console** → **opus-process-clip** → **Configuration** → **Environment variables**
2. Check these exist:
   - `FIREBASE_PROJECT_ID` = `reframeai-87b24` (or your project ID)
   - `FIREBASE_WEB_API_KEY` = `your_firebase_web_api_key`
   - `ENABLE_S3_SHARDING` = `true`
3. If missing, click **"Edit"** → **Add** → **Save**

---

## 🧪 TEST REAL-TIME CLIPS (5 minutes)

### Test 1: Upload a NEW video

1. Go to your dashboard
2. Upload a **new** YouTube video
3. Watch the project page
4. **Expected behavior**: Clips appear **one by one** as they're generated! 🎉

**Example timeline**:
```
0:30 - First clip appears
0:45 - Second clip appears
1:00 - Third clip appears
1:15 - Fourth clip appears
1:30 - Fifth clip appears
1:45 - Toast: "Processing complete! 5 clips generated"
```

### Test 2: Check CloudWatch Logs

**opus-process-clip logs** should show:
```
[ProcessClip] Uploading to S3 (with sharding): users/7a/user123/abc123/clips/clip_0_9x16.mp4
[TIMING] Upload: 2.34s
[ProcessClip] Adding clip 0 to Firestore for real-time updates...
[Firestore] Fetching current clips for session abc123
[Firestore] Adding new clip 0
[Firestore] ✓ Clip 0 added to Firestore successfully
```

**Frontend console** (browser DevTools) should show:
```
[ProjectDetails] Video data updated: { status: 'processing', clipsCount: 1 }
[ProjectDetails] Video data updated: { status: 'processing', clipsCount: 2 }
[ProjectDetails] Video data updated: { status: 'processing', clipsCount: 3 }
[ProjectDetails] Video data updated: { status: 'processing', clipsCount: 4 }
[ProjectDetails] Video data updated: { status: 'processing', clipsCount: 5 }
[ProjectDetails] ✓ Clips loaded! Showing 5 clips
```

---

## 🎯 Success Criteria

After deployment and testing:

1. ✅ **Clips appear one-by-one** in real-time (not all at once)
2. ✅ **No page refresh needed** - Firestore listener updates automatically
3. ✅ **Toast notification** appears when all clips are ready
4. ✅ **CloudWatch logs** show "✓ Clip X added to Firestore successfully"
5. ✅ **Browser console** shows incremental clip count updates

---

## 🎉 What You Get

**User Experience:**
- User uploads video
- Navigates to project page
- Sees "Downloading 23%", "Transcribing 67%", etc.
- **Clip 1 appears** - User can watch immediately!
- **Clip 2 appears** - Downloads while watching Clip 1
- **Clip 3 appears** - Can start sharing Clip 1 before all clips are ready
- Much better perceived performance!

**Technical Benefits:**
- ✅ Real-time updates (no polling needed)
- ✅ Incremental Firestore updates (clips added one-by-one)
- ✅ Fallback to finalize Lambda (if Firestore update fails)
- ✅ No breaking changes (finalize still works as backup)
- ✅ Better user engagement (can interact with clips immediately)

---

## 🐛 Troubleshooting

### Issue: Clips still appear all at once

**Fix 1**: Check Lambda Layer attached
```
Lambda → opus-process-clip → Layers section
Should show: shared-utilities:X (latest version with firestore_client)
```

**Fix 2**: Check environment variables
```
FIREBASE_PROJECT_ID and FIREBASE_WEB_API_KEY must be set
```

**Fix 3**: Check CloudWatch logs
```
Should see: "[ProcessClip] Adding clip X to Firestore for real-time updates..."
Should NOT see: "[ProcessClip] Skipping Firestore update (not available or no user_id)"
```

### Issue: Some clips appear in real-time, but finalize takes long

This is **NORMAL**! The finalize Lambda:
- Generates ALL presigned URLs (can take time with many clips)
- Updates final status
- Sends completion notifications
- Acts as backup in case individual updates failed

Clips appearing one-by-one is the **main benefit** - finalize can take its time!

---

## 📊 Performance Improvement

**Before (current)**:
```
User waits 2-3 minutes → All 5 clips appear → Can start watching
Time to first clip: 2-3 minutes ❌
```

**After (with real-time updates)**:
```
User waits 30 seconds → Clip 1 appears → Can start watching immediately!
Time to first clip: 30 seconds ✅ (4-6x faster!)
```

---

## 🚀 Deploy Now!

**Total time**: 10 minutes

1. Upload new Lambda Layer (3 min)
2. Update process-clip code (5 min)
3. Test with new video (2 min)

**Clips will appear in real-time!** 🎉
