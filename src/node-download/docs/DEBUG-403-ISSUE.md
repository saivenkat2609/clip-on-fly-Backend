# Debugging "Failed to find any playable formats"

## Current Status

You're getting:
- ✅ Cookies loading successfully (20 cookies)
- ✅ Using cookies for authentication
- ❌ **ERROR: Failed to find any playable formats**

This means cookies are loading but YouTube isn't accepting them or the formats aren't being retrieved properly.

## New Debugging Added

I've added comprehensive debugging to help identify the issue:

### 1. Cookie Information
```
[Download] Using 20 cookies for authentication
[Download] Cookie domains: .youtube.com, .google.com
[Download] Sample cookie: {"domain":".youtube.com","path":"/","secure":true,"httpOnly":false,"expires":1735123456,"name":"SSID","value":"AQ..."}
```

### 2. Agent Creation
```
[Download] Agent created successfully with cookies
```
Or if it fails:
```
[Download] Failed to create agent: [error message]
[Download] Falling back to default authentication
```

### 3. ytdl Options
```
[Download] ytdl options: agent=custom, headers={...}
```

### 4. Format Discovery
```
[Download] Found 42 total formats
[Download] Found 20 video formats
[Download] Found 5 combined video+audio formats
```

## Redeploy with Debug Info

```bash
cd lambda-functions/opus-node-download
npm install
deploy.bat
```

Upload the new zip and test again. The logs will show us exactly where the issue is.

## Possible Causes & Solutions

### Cause 1: Cookies Expired or Invalid

**Check:**
- Look for cookie expiry dates in the debug logs
- Cookies may need to be refreshed

**Solution:**
1. Export fresh cookies from your browser
2. Make sure you're logged into YouTube
3. Re-upload to R2/S3

**Export Fresh Cookies:**
```bash
# Use browser extension to export
# Then upload:
aws s3 cp youtube-cookies.txt s3://opus-clip-videos/youtube-cookies.txt \
  --endpoint-url=https://your-account-id.r2.cloudflarestorage.com
```

### Cause 2: Cookie Format Issue

**Check the sample cookie log:**
Should look like:
```json
{
  "domain": ".youtube.com",
  "path": "/",
  "secure": true,
  "httpOnly": false,
  "expires": 1735123456,
  "name": "SSID",
  "value": "AQ..."
}
```

**If format is wrong:**
- The Netscape parser might be failing
- Check your cookies file has tab-separated values

### Cause 3: Agent Creation Failing

**Check logs for:**
```
[Download] Failed to create agent: [error]
```

**If you see this:**
- The `ytdl.createAgent(cookies)` call is failing
- May need to install additional dependencies
- Try reinstalling node_modules:

```bash
rm -rf node_modules package-lock.json
npm install
```

### Cause 4: Video Restrictions

**This specific video might be:**
- Age-restricted
- Region-restricted
- Premium-only content
- Live stream (not supported)

**Test with a different video:**
```json
{
  "session_id": "test-simple",
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

This is the first YouTube video ever (18 seconds, public, no restrictions).

### Cause 5: YouTube API Changes

**If cookies are valid but still failing:**
YouTube may have changed their API. Check:
1. Update `@distube/ytdl-core`:
   ```bash
   npm install @distube/ytdl-core@latest
   ```

2. Check for ytdl-core issues:
   https://github.com/distubejs/ytdl-core/issues

## Expected Debug Output

After redeploying with debug info, you should see:

### ✅ Success Case:
```
[Download] Using 20 cookies for authentication
[Download] Cookie domains: .youtube.com, .google.com
[Download] Sample cookie: {"domain":".youtube.com"...}
[Download] Agent created successfully with cookies
[Download] ytdl options: agent=custom, headers={"User-Agent":"Mozilla/5.0..."}
[Download] Found 42 total formats
[Download] Found 20 video formats
[Download] Found 5 combined video+audio formats
[Download] Title: SPEED India VS Pakistan Cricket Match!
[Download] Duration: 354 seconds
✅ SUCCESS
```

### ❌ Cookie Issue:
```
[Download] Using 20 cookies for authentication
[Download] Cookie domains: .youtube.com
[Download] Sample cookie: {"domain":".youtube.com"...}
[Download] Failed to create agent: cookies must be an array
[Download] Falling back to default authentication
❌ ERROR: Failed to find any playable formats
```

### ❌ No Formats:
```
[Download] Using 20 cookies for authentication
[Download] Agent created successfully with cookies
[Download] Found 0 total formats
[Download] Found 0 video formats
[Download] Found 0 combined video+audio formats
❌ ERROR: Failed to find any playable formats
```

## Next Steps

1. **Redeploy with debug info** - Follow instructions above
2. **Test again** - With the same video URL
3. **Check CloudWatch logs** - Look for the new debug messages
4. **Share the debug output** - The detailed logs will tell us exactly what's wrong

## Alternative: Test Locally First

Since it works locally, test with Lambda environment variables:

```bash
cd lambda-functions/opus-node-download

# Set your Lambda env vars
$env:BUCKET_NAME="opus-clip-videos"
$env:R2_ENDPOINT="https://your-account.r2.cloudflarestorage.com"
$env:R2_ACCESS_KEY="your-key"
$env:R2_SECRET_KEY="your-secret"
$env:COOKIES_S3_KEY="youtube-cookies.txt"

# Test
node test.js "https://www.youtube.com/watch?v=cWrjp78QebE"
```

If it works locally but not in Lambda, the issue is environment-specific:
- Lambda timeout
- Lambda memory
- Lambda network restrictions
- IAM permissions

## Quick Test with Simple Video

Try this video (first YouTube video, very simple):

```json
{
  "session_id": "test-first-video",
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

If this works but your video doesn't:
- Your video has special restrictions
- Your cookies don't have permission for that video
- Try cookies from an account that can view the video

---

Redeploy with the new debug info and share the CloudWatch logs. We'll figure out exactly what's wrong! 🔍
