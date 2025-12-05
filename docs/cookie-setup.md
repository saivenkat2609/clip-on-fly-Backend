# YouTube Cookie Authentication Setup

YouTube is now requiring authentication via cookies to prevent bot access. Here's how to set it up.

## Option 1: Quick Test with Different Video

First, try a different video to see if it's video-specific:
- https://www.youtube.com/watch?v=dQw4w9WgXcQ
- https://www.youtube.com/watch?v=9bZkp7q19f0

## Option 2: Export YouTube Cookies (Recommended)

### Step 1: Install Browser Extension

**For Chrome/Edge:**
1. Install "Get cookies.txt LOCALLY" extension
   - https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc

**For Firefox:**
1. Install "cookies.txt" extension
   - https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/

### Step 2: Export Cookies

1. Open YouTube and **sign in** to your account
2. Browse to any YouTube video
3. Click the extension icon
4. Click "Export" or "Get cookies.txt"
5. Save the file as `youtube-cookies.txt`

### Step 3: Upload Cookies to S3

```bash
# Upload to your S3 bucket
aws s3 cp youtube-cookies.txt s3://YOUR-BUCKET-NAME/config/youtube-cookies.txt
```

### Step 4: Update Lambda Function

Add this environment variable to `opus-download` Lambda:
- Key: `COOKIES_S3_KEY`
- Value: `config/youtube-cookies.txt`

### Step 5: Update IAM Role

Add S3 read permission for the cookies file to `opus-clip-lambda-role`.

---

## Option 3: Use Alternative Downloader (Fastest Fix)

Switch to a different approach that doesn't require cookies:

### Use pytubefix with innertube client

This works without cookies but may be less reliable.

---

## Recommended: Use Cookies

Cookies provide the most reliable solution. They last ~6 months before needing refresh.

### Why Cookies Work:
- ✅ Bypasses all bot detection
- ✅ No rate limiting
- ✅ Access to all videos
- ✅ 99% reliability

### Maintenance:
- Refresh cookies every 6 months
- Just re-export and upload to S3

---

## Security Note

Your cookies contain authentication tokens. Keep them secure:
- Store in private S3 bucket
- Use IAM permissions to restrict access
- Don't commit to git
- Rotate regularly
