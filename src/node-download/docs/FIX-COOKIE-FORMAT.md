# Fix: Cookie Format Issue

## What Was the Problem?

You were getting:
- ✅ Cookies loaded successfully (20 cookies)
- ⚠️ WARNING: "Using old cookie format, please use the new one instead"
- ❌ ERROR: "Failed to find any playable formats"

The issue was that `@distube/ytdl-core` expects cookies in a **CookieJar** format (from the `tough-cookie` package), not as HTTP headers.

## What I Fixed

### 1. Added `tough-cookie` Dependency

**package.json** - Added:
```json
"tough-cookie": "^4.1.3"
```

### 2. Updated Cookie Loading

**Before** (lines 49-91):
- Parsed cookies and created a Cookie header string
- Passed as `Cookie: name=value; name2=value2`
- This was the "old format" that ytdl-core deprecated

**After** (lines 49-113):
- Parse Netscape cookies
- Create a `CookieJar` instance
- Add each cookie to the jar properly
- Return the jar for use with ytdl-core

### 3. Updated ytdl Options

**Before** (line 173):
```javascript
ytdlOptions.requestOptions.headers.Cookie = cookieHeader;
```

**After** (line 195):
```javascript
ytdlOptions.agent = ytdl.createAgent(cookieJar);
```

Now using ytdl-core's `createAgent()` method with the cookie jar, which is the correct/supported way.

## What You Need to Do

### Step 1: Install New Dependency

```bash
cd lambda-functions/opus-node-download
npm install
```

This will install `tough-cookie@^4.1.3`.

### Step 2: Redeploy

```bash
deploy.bat
```

### Step 3: Upload to Lambda

Upload the new `lambda-deployment.zip` to your Lambda function.

**AWS Console:**
- Go to Lambda function
- Code tab → Upload from → .zip file
- Select `lambda-deployment.zip`
- Save

**AWS CLI:**
```bash
aws lambda update-function-code \
  --function-name opus-clip-download-node \
  --zip-file fileb://lambda-deployment.zip
```

### Step 4: Test Again

Use the same test event or invoke from Step Functions.

## Expected Results

**Before (broken):**
```
[Download] Loaded 20 cookies
[Download] Using cookies for authentication
WARNING: Using old cookie format...
ERROR: Failed to find any playable formats
```

**After (fixed):**
```
[Download] Loaded 20 cookies into jar
[Download] Using cookies for authentication
[Download] Fetching video info...
[Download] Info fetched in 2.5s
[Download] Title: SPEED India VS Pakistan Cricket Match!
[Download] Duration: 354 seconds
[Download] Downloading...
✅ SUCCESS!
```

## Why This Fixes It

1. **Correct API**: `ytdl.createAgent(cookieJar)` is the official way to pass cookies
2. **No deprecation warning**: Using the new format eliminates the warning
3. **Better authentication**: CookieJar handles cookie domain matching, expiration, and security properly
4. **More reliable**: The library can properly manage cookies during requests

## Technical Details

### Cookie Flow:

1. **Download** from S3/R2: Netscape format cookie file
2. **Parse**: Extract domain, path, secure, expiry, name, value
3. **Create CookieJar**: Use `tough-cookie` package
4. **Add cookies**: `cookieJar.setCookie()` for each cookie
5. **Create agent**: `ytdl.createAgent(cookieJar)`
6. **Pass to ytdl**: `ytdl.getInfo(url, { agent })`

### Why Netscape Format?

Most browser cookie extensions export in Netscape format:
```
.youtube.com    TRUE    /    TRUE    1735123456    SSID    value123
```

Format: `domain` `flag` `path` `secure` `expiry` `name` `value`

### Why CookieJar?

`tough-cookie`'s CookieJar:
- Handles cookie domain matching (`.youtube.com` matches `www.youtube.com`)
- Manages cookie expiration
- Enforces Secure/HttpOnly flags
- Standard format for Node.js HTTP libraries

## Verification

After redeploying, check CloudWatch logs for:
- ✅ No "old cookie format" warning
- ✅ "Loaded X cookies into jar" message
- ✅ Successful video info fetch
- ✅ Successful download

The cookies should now work properly! 🎉
