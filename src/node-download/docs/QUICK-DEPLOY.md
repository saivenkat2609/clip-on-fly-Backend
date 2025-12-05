# Quick Deploy Guide - 5 Minutes to Working Lambda

## TL;DR

Your Lambda now uses **yt-dlp binary** instead of JavaScript libraries. This fixes all the 403 and HTML parsing errors.

## Deploy Now (3 Commands)

```bash
cd lambda-functions\opus-node-download
npm install
deploy.bat
```

Upload `lambda-deployment.zip` to your Lambda function.

## Required Setup

### 1. Lambda Layer
Make sure your Lambda has the yt-dlp layer attached:
- Lambda Console → Your function → Layers
- Verify yt-dlp layer is present

### 2. Environment Variables
Set these in Lambda Configuration:

```
BUCKET_NAME=opus-clip-videos
R2_ENDPOINT=https://your-account.r2.cloudflarestorage.com
R2_ACCESS_KEY=your-r2-access-key
R2_SECRET_KEY=your-r2-secret-key
COOKIES_S3_KEY=youtube-cookies.txt
YTDLP_PATH=/opt/bin/yt-dlp
```

### 3. Lambda Settings
```
Runtime: Node.js 20.x
Handler: index.handler
Timeout: 300 seconds
Memory: 1024 MB
```

## Test It

**Test Event:**
```json
{
  "session_id": "test123",
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

**Expected Log Output:**
```
[Download] ===== NEW INVOCATION =====
[Download] Session: test123
[Download] Loaded 20 cookies
[Download] Info fetched in 2.1s
[Download] Title: Me at the zoo
[Download] Downloaded 1.2 MB in 2.5s
[Download] Uploaded in 0.8s
[Download] Complete! Total time: 5.4s
```

**Expected Response:**
```json
{
  "statusCode": 200,
  "session_id": "test123",
  "s3_video_key": "test123/original_video.mp4",
  "video_info": {
    "title": "Me at the zoo",
    "duration": 19,
    ...
  }
}
```

## What Changed

| Before | After |
|--------|-------|
| @distube/ytdl-core library | yt-dlp binary from layer |
| HTML parsing errors | No parsing - direct binary call |
| 7 dependencies | 2 dependencies (AWS SDK only) |

## Files Changed

- ✅ **index.js** - Now uses `spawn('/opt/bin/yt-dlp', args)`
- ✅ **package.json** - Removed @distube/ytdl-core and tough-cookie

## Troubleshooting

### "Failed to spawn yt-dlp"
```bash
# Check YTDLP_PATH environment variable
YTDLP_PATH=/opt/bin/yt-dlp
```

### "yt-dlp exited with code 1"
- Check cookies are valid and uploaded to R2
- Try a public video first (use test URL above)
- Check CloudWatch logs for yt-dlp error message

### "Task timed out"
- Increase Lambda timeout to 5 minutes (300 seconds)
- Or use `QUALITY_MODE=fast` for smaller files

## Why This Works

**Before:** JavaScript library tried to parse YouTube HTML → Failed

**Now:** Calls yt-dlp binary directly → Works perfectly

The yt-dlp binary you already have as a Lambda layer is:
- Updated frequently for YouTube changes
- Battle-tested and reliable
- Same tool as your Python version

## Need More Details?

- **DEPLOY-YTDLP.md** - Complete deployment guide
- **SOLUTION-SUMMARY.md** - Full explanation of changes
- **test.js** - Local testing script

## Deploy Command

```bash
cd lambda-functions\opus-node-download
deploy.bat
```

Then upload `lambda-deployment.zip` to Lambda.

Done! 🎉
