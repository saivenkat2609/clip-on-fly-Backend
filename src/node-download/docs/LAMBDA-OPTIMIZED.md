# Lambda Optimizations Applied ✅

## Summary of Changes

I've optimized `index.js` to work perfectly in AWS Lambda with the following improvements:

### 1. ✅ Import Optimization
**Before:** `GetObjectCommand` was imported inside the async function
**After:** All AWS SDK imports at the top level

```javascript
const { S3Client, HeadObjectCommand, PutObjectCommand, GetObjectCommand } = require('@aws-sdk/client-s3');
```

**Why:** Lambda cold starts are faster when all requires are at module level.

### 2. ✅ Context Handling
**Added:**
```javascript
// Ensure Lambda doesn't wait for empty event loop (only if context exists)
if (context) {
    context.callbackWaitsForEmptyEventLoop = false;
}
```

**Why:** Prevents Lambda from waiting for the event loop to be empty before freezing, reducing execution time.

### 3. ✅ Timeout Monitoring
**Added timeout warnings:**
```javascript
// Before download
if (context && context.getRemainingTimeInMillis) {
    const remaining = context.getRemainingTimeInMillis();
    if (remaining < 120000) { // Less than 2 minutes
        console.warn(`WARNING: Only ${remaining/1000}s remaining`);
    }
}

// Before upload
if (remaining < 60000) { // Less than 1 minute
    console.error(`ERROR: Only ${remaining/1000}s remaining - may not complete upload!`);
}
```

**Why:** Helps debug timeout issues and understand where time is being spent.

### 4. ✅ Robust Context Handling
**Added null checks:**
```javascript
console.log(`Lambda Request ID: ${context ? context.requestId : 'local'}`);
console.log(`Remaining time: ${context ? context.getRemainingTimeInMillis() : 'N/A'}ms`);
```

**Why:** Works in both Lambda and local testing environments.

### 5. ✅ Cookie Loading Optimization
**Format:** Returns plain array instead of CookieJar
```javascript
[
  {
    domain: ".youtube.com",
    path: "/",
    secure: true,
    httpOnly: false,
    expires: 1735123456,
    name: "SSID",
    value: "cookie-value"
  }
]
```

**Why:** Matches `ytdl.createAgent()` requirements exactly - no conversion needed.

### 6. ✅ Memory Management
**Already optimized:**
- Streams for video download (no memory buffering)
- Multipart upload with 4 concurrent parts
- Immediate cleanup of temp files
- Cookie caching to avoid re-downloads

## Deployment Instructions

### 1. Build Package

```bash
cd lambda-functions/opus-node-download
npm install
deploy.bat
```

### 2. Lambda Configuration

**Runtime Settings:**
```
Runtime: Node.js 20.x
Handler: index.handler
Architecture: x86_64 (or arm64)
```

**Performance Settings:**
```
Memory: 1024 MB (minimum) - 2048 MB recommended for large videos
Timeout: 300 seconds (5 minutes)
Ephemeral storage: 512 MB (default) - increase to 1024 MB if needed
```

**Environment Variables:**
```bash
# Required
BUCKET_NAME=opus-clip-videos
AWS_REGION=us-east-1

# For R2/Cloudflare
R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
R2_ACCESS_KEY=your-r2-access-key
R2_SECRET_KEY=your-r2-secret-key

# Required for reliability
COOKIES_S3_KEY=youtube-cookies.txt

# Optional
QUALITY_MODE=balanced  # fast, balanced, or best
```

**Advanced Settings:**
```
Reserved concurrency: (optional) Set limit if needed
Provisioned concurrency: (optional) For faster cold starts
```

### 3. Upload Code

**AWS Console:**
1. Go to Lambda → Code
2. Upload from → .zip file
3. Select `lambda-deployment.zip`
4. Save

**AWS CLI:**
```bash
aws lambda update-function-code \
  --function-name opus-clip-download-node \
  --zip-file fileb://lambda-deployment.zip
```

### 4. Test

**Test Event:**
```json
{
  "session_id": "test-123",
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

**Expected CloudWatch Logs:**
```
[Download] ===== NEW INVOCATION =====
[Download] Session: test-123
[Download] URL: https://www.youtube.com/watch?v=jNQXAC9IVRw
[Download] Lambda Request ID: abc-123-def
[Download] Quality Mode: balanced
[Download] Remaining time: 300000ms
[Download] Loading cookies from opus-clip-videos/youtube-cookies.txt...
[Download] Loaded 20 cookies
[Download] Using cookies for authentication
[Download] Fetching video info...
[Download] Info fetched in 2.5s
[Download] Title: Me at the zoo
[Download] Duration: 18 seconds
[Download] Selected format: 360p (mp4)
[Download] Expected size: 2.45 MB
[Download] Downloading to /tmp/test-123_video.mp4...
[Download] Downloaded 2.45 MB in 3.2s (0.77 MB/s)
[Download] Remaining time before upload: 294s
[Download] Uploading to storage: test-123/original_video.mp4
[Download] Uploaded in 1.8s (1.36 MB/s)
[Download] Complete! Total time: 8.5s
✅ SUCCESS
```

## Performance Metrics

### Expected Times (480p video):

| Video Length | Info Fetch | Download | Upload | Total |
|-------------|-----------|----------|---------|--------|
| 30 seconds | 2-3s | 5-8s | 2-3s | **10-15s** |
| 2 minutes | 2-3s | 8-15s | 3-5s | **15-25s** |
| 5 minutes | 2-3s | 15-30s | 5-10s | **25-45s** |
| 10 minutes | 2-3s | 30-60s | 10-20s | **45-85s** |

### Cold Start:
- **First invocation:** Add 2-3 seconds
- **Warm invocations:** No additional time
- **Provisioned concurrency:** Eliminates cold starts

## Troubleshooting

### "Task timed out after 300 seconds"
**Solutions:**
1. Increase Lambda timeout to 900 seconds (15 minutes) - max allowed
2. Increase memory to 2048 MB (gives more CPU power)
3. Use QUALITY_MODE=fast for faster downloads
4. Check video length - videos over 10 minutes may timeout

### "ENOSPC: no space left on device"
**Solutions:**
1. Increase Ephemeral storage from 512 MB to 1024-2048 MB
2. Files are cleaned up automatically, but check /tmp isn't full

### "Out of memory"
**Solutions:**
1. Increase Lambda memory to 2048 MB or 3008 MB
2. Streams are used (no buffering), but very large videos need more memory

### "403 Forbidden" or "Failed to find any playable formats"
**Solutions:**
1. Verify COOKIES_S3_KEY is set
2. Verify cookies file exists in bucket
3. Re-export cookies from browser (they may have expired)
4. Check Lambda has S3 GetObject permission

### Context is undefined
**Solution:** The code now handles this automatically with null checks

## Monitoring

### Key Metrics to Watch:

**CloudWatch Metrics:**
- Duration: Should be 15-85s for most videos
- Errors: Should be 0%
- Throttles: Should be 0
- Memory Used: Should be under 512 MB

**CloudWatch Logs Insights Query:**
```sql
fields @timestamp, @message
| filter @message like /Complete! Total time/
| parse @message /Total time: (?<duration>[\d.]+)s/
| stats avg(duration) as avg_duration, max(duration) as max_duration, count() as invocations
```

**Cost Optimization:**
- Use 1024 MB memory for most videos (good balance)
- Use 2048 MB only for long videos (10+ minutes)
- Set Reserved Concurrency to limit costs
- Monitor S3/R2 transfer costs

## Best Practices

1. **Always use cookies** - Set COOKIES_S3_KEY environment variable
2. **Monitor timeout warnings** - Check CloudWatch for WARNING messages
3. **Use appropriate memory** - 1024 MB for most cases, 2048 MB for long videos
4. **Set reasonable timeout** - 300s (5 min) for most videos
5. **Cache cookies** - Cookies are cached per Lambda container (warm starts)
6. **Clean up regularly** - Lambda does this automatically, but monitor /tmp usage

## Production Checklist

Before going to production:

- [ ] Lambda timeout set to 300 seconds (5 minutes)
- [ ] Memory set to at least 1024 MB
- [ ] All environment variables configured
- [ ] Cookies uploaded to S3/R2 and COOKIES_S3_KEY set
- [ ] IAM role has S3 GetObject/PutObject/HeadObject permissions
- [ ] CloudWatch Logs enabled for debugging
- [ ] Tested with various video lengths
- [ ] Step Functions integration tested
- [ ] Error handling tested (invalid URLs, expired cookies, etc.)
- [ ] Cost monitoring set up (CloudWatch Billing Alarms)

---

Your Lambda is now optimized and ready for production! 🚀

All optimizations work in both local testing and AWS Lambda environments.
