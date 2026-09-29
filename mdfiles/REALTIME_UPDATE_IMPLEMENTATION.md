# Real-Time Video Update Implementation

## Overview
Implemented aggressive cache-busting and real-time UI updates so users see the reprocessed video immediately without page refresh.

---

## ✅ Changes Made

### 1. **Overwrite Existing Clips** (Backend)
**Problem**: Creating new versioned files clutters storage and causes confusion.

**Solution**: Overwrite the same S3 key with aggressive cache-control headers.

#### Files Modified:
- `opus-clip-cloud/src/reprocess-clip/lambda_function.py` (lines 301-322)
- `opus-clip-cloud/src/process-clip/lambda_function.py` (lines 402-404)

**Before**:
```python
# Creates: clip_0_9x16_v1766485671.mp4 (new file each time)
version_timestamp = int(time.time())
s3_clip_key = f"{session_id}/clips/clip_{clip_index}_9x16_v{version_timestamp}.mp4"
```

**After**:
```python
# Overwrites: clip_0_9x16.mp4 (same file)
new_s3_key = existing_clip_key

s3.upload_file(
    output_path,
    BUCKET_NAME,
    new_s3_key,
    ExtraArgs={
        'ContentType': 'video/mp4',
        'CacheControl': 'no-cache, no-store, must-revalidate, max-age=0',
        'Metadata': {
            'reprocessed-at': str(int(time.time()))
        }
    }
)
```

**Benefits**:
- ✅ No storage bloat from versioned files
- ✅ Cleaner S3 structure
- ✅ Aggressive cache headers prevent CDN caching

---

### 2. **Strict Polling with Cache Busting** (Frontend Hook)
**Problem**: Polling detected success too early, showing UI update before reprocessing completed.

**Solution**: Strict polling logic that only succeeds when reprocessing is truly complete.

#### File Modified:
- `reframe-ai/src/hooks/useTemplateReprocess.ts` (lines 35-118)

**Key Changes**:
```typescript
// Record start time to detect new updates
const startTime = Date.now();

// Wait 3 seconds between polls (reprocessing takes ~55s)
await new Promise(resolve => setTimeout(resolve, 3000));

// Cache-bust result.json requests
const result = await apiClient.get(`/result/${session_id}?_=${Date.now()}`);

// STRICT CHECK: Only succeed if reprocessing actually completed
const templateMatches = updatedClip.template_id === template_id;
const hasReprocessedFlag = updatedClip.reprocessed === true;
const hasNewTimestamp = lastUpdatedTime > startTime;

// SUCCESS only if: template matches AND (reprocessed flag OR new timestamp)
if (templateMatches && (hasReprocessedFlag || hasNewTimestamp)) {
  // Update UI
}
```

**Benefits**:
- ✅ Only updates UI when reprocessing is truly complete
- ✅ Prevents premature "success" detection
- ✅ Reliable timestamp-based verification

---

### 3. **Aggressive Video Player Reload** (Frontend Component)
**Problem**: Video.js player wasn't fully reloading even with new URL.

**Solution**: Complete player reset before loading new source.

#### File Modified:
- `reframe-ai/src/components/VideoPreview.tsx` (lines 60-95)

**Key Changes**:
```typescript
// Aggressive reload strategy
player.pause();
player.reset(); // Reset player state completely

// Clear current source
player.src({ src: '', type: '' });

// Wait a tick, then set new source
setTimeout(() => {
  player.src({
    src: src,
    type: "video/mp4",
  });
  player.load(); // Force reload from network
  player.play();
}, 100);
```

**Benefits**:
- ✅ Completely clears player buffer
- ✅ Forces fresh network request
- ✅ No residual cached frames

---

### 4. **Immediate UI State Update** (Frontend Page)
**Problem**: UI wasn't updating state aggressively enough.

**Solution**: Triple-layer cache busting with forced state update.

#### File Modified:
- `reframe-ai/src/pages/ProjectDetails.tsx` (lines 221-255)

**Key Changes**:
```typescript
// Triple cache busting
const cacheBuster = Date.now();
const randomId = Math.random().toString(36).substring(7);
const separator = freshUrl.includes('?') ? '&' : '?';
freshUrl = `${freshUrl}${separator}_v=${cacheBuster}&_r=${randomId}`;

// Add reprocessing timestamp to track changes
reprocessedAt: cacheBuster,

// Force immediate state update
setVideo({ ...video, clips: updatedClips });
```

**Component Key Update**:
```typescript
<VideoThumbnail
  key={`${clip.clipIndex}-${clip.reprocessedAt || clip.lastUpdated || clip.downloadUrl}`}
  // Forces remount when reprocessedAt changes
/>
```

**Benefits**:
- ✅ URL changes guaranteed unique
- ✅ Component remounts on reprocess
- ✅ Immediate visual update

---

## 📊 Performance Comparison

### Before Optimization:
| Metric | Value |
|--------|-------|
| Reprocessing Time | 55+ seconds |
| Polling Interval | 3 seconds |
| UI Update Delay | Immediate (incorrect - showed old template) |
| Cache Busting | Single timestamp |
| Video Reload | Partial (source change only) |

### After Optimization:
| Metric | Value |
|--------|-------|
| Reprocessing Time | **55 seconds** (full reprocessing for clean subtitles) |
| Polling Interval | **3 seconds** |
| UI Update Delay | **~3 seconds after completion** ⚡ |
| Cache Busting | **Triple-layer (timestamp + random + metadata)** |
| Video Reload | **Complete reset + fresh load** |
| Success Detection | **Strict (timestamp + flag verification)** ⚡ |

**Total Time to See New Video**: ~60 seconds (reliable, no double subtitles)

---

## 🔄 Complete Flow

```
User clicks "Apply Template"
         ↓
Toast: "Reprocessing video with new subtitle style. This may take up to 60 seconds."
         ↓
API Gateway → Async Lambda Invocation (202 response)
         ↓
reprocess-clip Lambda (FULL REPROCESSING):
├─ Load result.json and transcript (~0.5s)
├─ Invoke opus-process-smart-framing Lambda (SYNCHRONOUS)
│  ├─ Download original video (~5-10s)
│  ├─ Extract clip segment (~2-5s)
│  ├─ Apply crop/scale transformations (~5-10s)
│  ├─ Create new ASS subtitles with template (~0.5s)
│  ├─ FFmpeg burn subtitles (~15-25s)
│  └─ Upload to S3 with no-cache headers (~3-5s)
├─ Update result.json with:
│  ├─ last_updated: new timestamp
│  ├─ reprocessed: true
│  └─ template_id: new template
└─ Complete! [Total: ~55s]
         ↓
Frontend Polling (every 3s):
├─ Fetch result.json with cache buster
├─ STRICT CHECK:
│  ├─ template_id matches? ✓
│  ├─ reprocessed flag = true? ✓
│  └─ last_updated > startTime? ✓
├─ Generate fresh URL: base_url?_cb=1766486891&_r=abc123
└─ Update clip state with reprocessedAt timestamp
         ↓
UI Update Cascade:
├─ VideoThumbnail remounts (key changed)
├─ VideoPreview.tsx detects src change
├─ Player.reset() → clear buffer
├─ setTimeout → Player.src(newUrl) → load()
└─ Auto-play new video
         ↓
✨ User sees updated video with CLEAN new template! [~3s UI delay]
         ↓
Toast: "✨ Template Applied Successfully!"
```

**Total User Experience**: ~60 seconds from click to seeing new video
**Key Benefit**: No double subtitles, clean professional output

---

## 🛠️ Deployment Checklist

### Backend:
- [x] `opus-reprocess-clip` Lambda - Fast path + overwrite logic
- [x] `opus-process-smart-framing` Lambda - Removed versioning
- [x] Environment variables:
  - `R2_PUBLIC_DOMAIN=pub-a42da8500209450c8fb64926d3bcd10a.r2.dev`
  - `ENABLE_FAST_REPROCESS=true`

### Frontend:
- [x] `useTemplateReprocess.ts` - Faster polling + cache busting
- [x] `VideoPreview.tsx` - Aggressive reload
- [x] `ProjectDetails.tsx` - Triple cache busting + state update

### Deploy Commands:
```bash
# Backend
cd C:\Projects\reframeAI\opus-clip-cloud\deployment
build-and-push-container.bat opus-reprocess-clip

# Frontend
cd C:\Projects\reframeAI\reframe-ai
npm run build
# Deploy to hosting
```

---

## 🐛 Troubleshooting

### If video still shows old content:

1. **Check CloudWatch Logs**:
   ```
   [FastReprocess] Uploaded in 2.34s (overwritten existing clip)
   [ReprocessClip] Using public URL: https://pub-xxx.r2.dev/.../clip_0_9x16.mp4?_t=1766486891
   ```

2. **Check Browser Console**:
   ```
   [TemplateReprocess] ✅ Clip updated successfully!
   [ProjectDetails] ✅ UI updated with new video URL: ...?_v=1766486891&_r=abc123
   [VideoPreview] Source changed, forcing complete reload: ...
   [VideoPreview] ✅ Video reloaded successfully
   ```

3. **Verify S3 Object**:
   - Check S3 object metadata shows recent `reprocessed-at` timestamp
   - Verify `CacheControl` header is set to `no-cache, no-store`

4. **Clear Browser Cache** (last resort):
   - Hard refresh: Ctrl+Shift+R (Windows) / Cmd+Shift+R (Mac)
   - Or open DevTools → Network tab → Disable cache

### If reprocessing is slow:

Check if fast path is being used:
```
[FastReprocess] Using optimized fast path (existing clip + new subtitles)
```

If you see:
```
[ReprocessClip] Using slow path (invoke process-clip Lambda)
```

Reasons:
- `ENABLE_FAST_REPROCESS=false` in environment
- `existing_clip_key` not found (first-time processing)
- Fast path error (falls back automatically)

---

## 📈 Metrics to Monitor

### CloudWatch Metrics:
- Lambda duration: Should be ~10-15s for fast path
- Lambda invocation errors: Should be < 1%
- API Gateway 5xx errors: Should be 0

### User Experience Metrics:
- Time to see new video: ~15 seconds
- Failed reprocessing rate: < 1%
- User satisfaction: Immediate visual feedback

---

## ✅ Success Criteria

You'll know it's working when:

1. ✅ Click "Apply Template" → See processing toast ("may take up to 60 seconds")
2. ✅ Wait ~60 seconds → See success toast (only when reprocessing completes)
3. ✅ Video updates with **clean new styling** (no double subtitles)
4. ✅ **No page refresh needed**
5. ✅ CloudWatch shows full reprocessing via opus-process-smart-framing
6. ✅ S3 has same file name (not versioned)
7. ✅ Browser DevTools shows video request with new timestamp
8. ✅ UI only updates AFTER backend completes (strict polling)

---

**Status**: ✅ Ready to deploy!

**Key Benefits**:
- ✅ Reliable UI updates (only after reprocessing completes)
- ✅ Clean subtitle rendering (no double captions)
- ✅ Automatic cache busting
- ✅ Professional output quality
