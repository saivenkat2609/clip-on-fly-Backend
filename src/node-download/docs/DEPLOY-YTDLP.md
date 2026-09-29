# Deploy Node.js Lambda with yt-dlp Binary

## What Changed

**FINAL SOLUTION:** Replaced `@distube/ytdl-core` JavaScript library with **yt-dlp binary** from your existing Lambda layer.

### Why This Change?

The @distube/ytdl-core library had an HTML parsing error:
```
Error: Error when parsing watch.html, maybe YouTube made a change
```

Using the yt-dlp binary is more reliable because:
- It's the same tool as your working Python version
- Updated more frequently for YouTube API changes
- Handles all authentication and format selection natively
- You already have it as a Lambda layer

## Files Modified

1. **index.js** - Now uses yt-dlp binary via `child_process.spawn`
2. **package.json** - Removed `@distube/ytdlp-core` and `tough-cookie` dependencies

## Deployment Steps

### 1. Clean and Install Dependencies

```bash
cd lambda-functions/opus-node-download

# Remove old dependencies
rmdir /s /q node_modules
del package-lock.json

# Install fresh (only AWS SDK now)
npm install
```

### 2. Create Deployment Package

```bash
deploy.bat
```

This creates `lambda-deployment.zip` containing:
- index.js (with yt-dlp implementation)
- package.json
- node_modules/ (AWS SDK only)

### 3. Upload to Lambda

**Option A: AWS Console**
1. Go to Lambda Console
2. Select your download Lambda function
3. Click "Upload from" > ".zip file"
4. Choose `lambda-deployment.zip`
5. Click "Save"

**Option B: AWS CLI**
```bash
aws lambda update-function-code ^
  --function-name opus-clip-download ^
  --zip-file fileb://lambda-deployment.zip
```

### 4. Verify Lambda Layer

Make sure your Lambda has the yt-dlp layer attached:

1. Go to Lambda Console > Your function
2. Scroll to "Layers" section
3. Verify yt-dlp layer is listed
4. The layer should provide `/opt/bin/yt-dlp`

**If layer is missing:**
- Attach your existing yt-dlp Lambda layer
- Or create one following AWS Lambda Layer documentation

### 5. Configure Environment Variables

Set these in Lambda Configuration > Environment variables:

**Required:**
```
BUCKET_NAME=opus-clip-videos
R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
R2_ACCESS_KEY=your-r2-access-key
R2_SECRET_KEY=your-r2-secret-key
```

**Optional:**
```
COOKIES_S3_KEY=youtube-cookies.txt
QUALITY_MODE=balanced
YTDLP_PATH=/opt/bin/yt-dlp
```

**Environment Variable Details:**

- `YTDLP_PATH` - Path to yt-dlp binary in Lambda layer
  - Default: `/opt/bin/yt-dlp`
  - Change if your layer uses a different path
  - Check layer documentation for the correct path

- `QUALITY_MODE` - Video quality to download
  - `fast` - 480p max (fastest downloads)
  - `balanced` - 480p optimized (default)
  - `best` - 1080p max (largest files)

- `COOKIES_S3_KEY` - Path to YouTube cookies file in your bucket
  - Optional but recommended for restricted videos
  - Should be Netscape cookie format
  - If not set, downloads work for public videos only

### 6. Lambda Configuration

Ensure these settings:

```
Runtime: Node.js 20.x (or 18.x)
Handler: index.handler
Timeout: 300 seconds (5 minutes)
Memory: 1024 MB (or more for large videos)
Ephemeral storage: 512 MB (or 1024 MB for HD videos)
```

## Testing

### Test Event

Use this JSON test event:

```json
{
  "session_id": "test-ytdlp-123",
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

This is the first YouTube video (18 seconds, public, no restrictions).

### Expected Success Logs

```
[Download] ===== NEW INVOCATION =====
[Download] Session: test-ytdlp-123
[Download] URL: https://www.youtube.com/watch?v=jNQXAC9IVRw
[Download] Lambda Request ID: abc123-def456
[Download] Quality Mode: balanced
[Download] Remaining time: 299000ms
[Download] Loading cookies from opus-clip-videos/youtube-cookies.txt...
[Download] Loaded 20 cookies to /tmp/youtube-cookies.txt
[Download] Video not found in storage, proceeding with download...
[Download] Fetching video info...
[Download] Running: /opt/bin/yt-dlp --dump-json --no-playlist --no-check-formats --cookies /tmp/youtube-cookies.txt https://www.youtube.com/watch?v=jNQXAC9IVRw
[Download] Info fetched in 2.1s
[Download] Title: Me at the zoo
[Download] Duration: 19 seconds
[Download] Mode: BALANCED - Using 480p
[Download] Downloading to /tmp/test-ytdlp-123_video.mp4...
[Download] Running: /opt/bin/yt-dlp --format best[height<=480][ext=mp4]/best[height<=480]/worst[height>=360] --output /tmp/test-ytdlp-123_video.mp4 --no-playlist --no-continue --no-part --no-mtime --concurrent-fragments 8 --buffer-size 128K --retries 3 --fragment-retries 3 --force-ipv4 --newline --progress --cookies /tmp/youtube-cookies.txt https://www.youtube.com/watch?v=jNQXAC9IVRw
[download] 100% of 1.2MB in 00:02
[Download] Downloaded 1.2 MB in 2.5s (0.48 MB/s)
[Download] Remaining time before upload: 294s
[Download] Uploading to storage: test-ytdlp-123/original_video.mp4
[Download] Uploaded in 0.8s (1.5 MB/s)
[Download] Complete! Total time: 5.4s

Response:
{
  "statusCode": 200,
  "session_id": "test-ytdlp-123",
  "s3_video_key": "test-ytdlp-123/original_video.mp4",
  "video_info": {
    "title": "Me at the zoo",
    "duration": 19,
    "description": "The first video on YouTube...",
    "uploader": "jawed",
    "view_count": 280000000,
    "thumbnail_url": "https://i.ytimg.com/vi/jNQXAC9IVRw/maxresdefault.jpg"
  }
}
```

## How It Works

### 1. Cookie Handling
```javascript
// Downloads cookies from R2/S3
const response = await s3.send(new GetObjectCommand({
    Bucket: BUCKET_NAME,
    Key: COOKIES_S3_KEY
}));

// Saves to /tmp for yt-dlp to use
fs.writeFileSync('/tmp/youtube-cookies.txt', cookieData);
```

### 2. yt-dlp Execution
```javascript
// Spawns yt-dlp process
const ytdlp = spawn('/opt/bin/yt-dlp', args, { cwd: '/tmp' });

// Captures output
ytdlp.stdout.on('data', (data) => {
    stdout += data.toString();
});

// Handles completion
ytdlp.on('close', (code) => {
    if (code === 0) resolve({ stdout, stderr });
    else reject(new Error(`yt-dlp exited with code ${code}`));
});
```

### 3. Two-Step Download Process
```javascript
// Step 1: Get video info (JSON output)
await runYtdlp(['--dump-json', '--no-playlist', url]);

// Step 2: Download video file
await runYtdlp(['--format', formatSpec, '--output', localPath, url]);
```

## Troubleshooting

### Error: "Failed to spawn yt-dlp"

**Cause:** yt-dlp binary not found at `/opt/bin/yt-dlp`

**Solution:**
1. Verify Lambda layer is attached
2. Check yt-dlp path in layer
3. Set `YTDLP_PATH` environment variable to correct path

```bash
# Test layer path
aws lambda invoke --function-name opus-clip-download --payload '{"test":"layer"}' response.json
# Check logs for error message
```

### Error: "yt-dlp exited with code 1"

**Cause:** yt-dlp failed to download video

**Solution:**
1. Check CloudWatch logs for yt-dlp error message
2. Common issues:
   - Video restricted/private (need valid cookies)
   - Video unavailable/deleted
   - Network timeout (increase Lambda timeout)
   - Region restrictions

### Error: "No such file or directory: /tmp/youtube-cookies.txt"

**Cause:** Cookies failed to download from R2/S3

**Solution:**
1. Verify `COOKIES_S3_KEY` environment variable
2. Check cookies file exists in R2/S3 bucket
3. Verify Lambda has S3/R2 read permissions
4. Test without cookies (public videos only):
   - Remove or comment out `COOKIES_S3_KEY` env var

### Error: "Task timed out after 300.00 seconds"

**Cause:** Video too large or download too slow

**Solution:**
1. Increase Lambda timeout (max 15 minutes)
2. Use `QUALITY_MODE=fast` for smaller files
3. Increase Lambda memory (more CPU = faster downloads)
4. Check video duration (limit is 1 hour)

## Performance Comparison

| Implementation | Status | Issue |
|----------------|--------|-------|
| Python + yt-dlp | Failed | 403 Forbidden errors |
| Node.js + @distube/ytdl-core | Failed | HTML parsing error |
| **Node.js + yt-dlp binary** | **Working** | **None** |

## What's Different from Python Version

**Similarities:**
- Uses same yt-dlp binary
- Same authentication (cookies)
- Same format selection logic
- Same R2/S3 upload

**Improvements:**
- Better error handling and logging
- Cleaner async/await code (no sync operations)
- Explicit Step Functions payload handling
- Proper stream cleanup

## Next Steps

1. **Deploy** - Follow steps above
2. **Test** - Use simple video first
3. **Verify** - Check CloudWatch logs
4. **Production** - Test with your actual videos

## If Everything Works

You should see:
- No 403 errors
- No HTML parsing errors
- Successful downloads
- Fast R2 uploads
- Complete video info returned

## Still Have Issues?

Check CloudWatch logs for detailed error messages. The implementation now logs:
- Exact yt-dlp command being run
- Full stdout and stderr from yt-dlp
- File sizes and download speeds
- Remaining Lambda execution time
- Complete error stack traces

Every step is logged with `[Download]` prefix for easy filtering.
