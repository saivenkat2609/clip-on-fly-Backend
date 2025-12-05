# Final Fix: Cookie Array Format

## The Problem

Error: `"cookies must be an array"` from `ytdl-core/lib/agent.js:36`

The `ytdl.createAgent()` function expects cookies as a **plain array of objects**, not a CookieJar.

## The Solution

Changed the cookie loading to return a plain array with the correct structure.

### Cookie Format Expected by ytdl-core:

```javascript
[
  {
    domain: ".youtube.com",
    path: "/",
    secure: true,
    httpOnly: false,
    expires: 1735123456,  // Unix timestamp in seconds
    name: "SSID",
    value: "your-cookie-value"
  },
  // ... more cookies
]
```

### What I Changed:

**Before (lines 49-112):**
- Used `CookieJar` from `tough-cookie`
- Called `cookieJar.setCookie()` for each cookie
- Returned the CookieJar instance

**After (lines 49-112):**
- Create plain array
- Parse Netscape format and push objects to array
- Each object has: `domain`, `path`, `secure`, `httpOnly`, `expires`, `name`, `value`
- Return the array

**Usage (line 194):**
```javascript
ytdlOptions.agent = ytdl.createAgent(cookies);
```

## Redeploy Instructions

The code is already fixed in the file. Just redeploy:

### 1. Rebuild (if you added tough-cookie)

```bash
cd lambda-functions/opus-node-download
npm install
```

### 2. Create Package

```bash
deploy.bat
```

### 3. Upload to Lambda

**AWS Console:**
- Go to Lambda → Code → Upload from → .zip file
- Select `lambda-deployment.zip`

**AWS CLI:**
```bash
aws lambda update-function-code \
  --function-name opus-clip-download-node \
  --zip-file fileb://lambda-deployment.zip
```

### 4. Test

Use your test event or invoke from Step Functions.

## Expected Result

**Success logs:**
```
[Download] Loading cookies from opus-clip-videos/youtube-cookies.txt...
[Download] Loaded 20 cookies
[Download] Using cookies for authentication
[Download] Fetching video info...
[Download] Info fetched in 2.5s
[Download] Title: SPEED India VS Pakistan Cricket Match!
[Download] Duration: 354 seconds
[Download] Downloading to /tmp/124u2349_video.mp4...
[Download] Selected format: 480p (mp4)
[Download] Downloaded 45.23 MB in 18.5s
[Download] Uploaded in 6.2s
✅ Complete! Total time: 32.4s
```

## Why This Format?

The `@distube/ytdl-core` library uses these cookies to:

1. **Create custom HTTP agent** - Attaches cookies to all YouTube API requests
2. **Handle authentication** - Makes YouTube think you're logged in
3. **Bypass restrictions** - Gets access to all video formats
4. **Solve n-parameter challenge** - Automatically handles YouTube's anti-bot measures

The array format matches the standard cookie structure used by Node.js HTTP libraries.

## Verification

After deploying, check CloudWatch logs:
- ✅ "Loaded X cookies" (not "into jar")
- ✅ "Using cookies for authentication"
- ✅ No "old cookie format" warning
- ✅ No "cookies must be an array" error
- ✅ Successful video info fetch
- ✅ Successful download

## Technical Details

### Netscape Cookie Format:
```
.youtube.com    TRUE    /    TRUE    1735123456    SSID    cookie-value
```

Fields:
1. `domain` - Cookie domain (e.g., `.youtube.com`)
2. `flag` - Whether domain includes subdomains (TRUE/FALSE)
3. `path` - Cookie path (e.g., `/`)
4. `secure` - Requires HTTPS (TRUE/FALSE)
5. `expires` - Unix timestamp in seconds
6. `name` - Cookie name
7. `value` - Cookie value

### Conversion to Object:
```javascript
{
  domain: parts[0],           // ".youtube.com"
  path: parts[2],             // "/"
  secure: parts[3] === 'TRUE', // true
  httpOnly: false,            // Default for browser cookies
  expires: parseInt(parts[4]), // 1735123456
  name: parts[5],             // "SSID"
  value: parts[6].trim()      // "cookie-value"
}
```

This is the format `ytdl.createAgent()` expects.

## Note on tough-cookie

The `tough-cookie` package in `package.json` is not being used anymore. It doesn't hurt to keep it, but you can remove it if you want:

```bash
npm uninstall tough-cookie
```

Then redeploy. But leaving it is fine too (only adds ~100KB).

---

This should be the **final fix**! The cookies are now in the correct format that ytdl-core expects. 🎉
