# Fix 404 Not Found Error

## Current Status

✅ **Authorization is WORKING!**
```
[Authorizer] Token verified for user: wA8G7Z0tCIRQIKXyhTyXQzyKzpF3
[Authorizer] Authorized user: wA8G7Z0tCIRQIKXyhTyXQzyKzpF3, email: saivenkat2609@gmail.com, verified: True
```

❌ **Getting 404 for POST /process**

---

## API Gateway Configuration ✅ All Correct

I've verified your API Gateway configuration:

**API Details:**
- API ID: `g78mc4ok92`
- API Type: HTTP API (v2)
- Endpoint: `https://g78mc4ok92.execute-api.us-east-1.amazonaws.com`
- Name: `opus-clip-api`

**Routes:**
- ✅ `POST /process` exists (Route ID: k06gb0f)
- ✅ Integration: `opus-api-gateway` Lambda
- ✅ Authorizer: `FirebaseJWTAuthorizer` (k21dbr) attached
- ✅ Authorizer Lambda: `opus-authorizer`

**Stages:**
- ✅ `prod` stage exists
- ✅ `$default` stage exists
- ✅ Both deployed with latest changes (2025-12-06 07:58:57)
- ✅ Auto-deploy enabled

**Lambda Permissions:**
- ✅ `opus-api-gateway` has permission for API Gateway to invoke it

---

## Root Cause Analysis

Since the authorizer is working (logs show successful authorization), but you're getting 404, there are a few possible causes:

### 1. URL Mismatch

**Your frontend might be calling the wrong URL.**

For HTTP API v2, the correct format is:
```
https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/{route}
```

**Correct URLs:**
- With `prod` stage: `https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod/process`
- With `$default` stage: `https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/process`

Note: When using `$default` stage, you don't include the stage name in the URL!

### 2. Frontend Code Issue

Check your frontend code to ensure it's using the correct URL format.

---

## Solution: Check Frontend URL

### Step 1: Find where the API URL is defined

Look for where you're making the API call in your frontend code:

**Common locations:**
- `src/config.js` or `src/config.ts`
- Environment variables (`.env` files)
- API service files (e.g., `src/services/api.js`)
- Component files where API calls are made

**Search for:**
```javascript
// Look for these patterns:
"execute-api.us-east-1.amazonaws.com"
"g78mc4ok92"
"/process"
fetch(
axios.post(
```

### Step 2: Verify the URL format

**If using `prod` stage:**
```javascript
const API_URL = 'https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod';

// Then call:
fetch(`${API_URL}/process`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    youtube_url: url,
    project_name: name
  })
});
```

**If using `$default` stage:**
```javascript
const API_URL = 'https://g78mc4ok92.execute-api.us-east-1.amazonaws.com';

// Then call:
fetch(`${API_URL}/process`, {  // No stage in URL!
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    youtube_url: url,
    project_name: name
  })
});
```

### Step 3: Test both URLs

Run this in browser console (F12) to test both URLs:

```javascript
async function test404() {
  const user = firebase.auth().currentUser;
  if (!user) {
    console.error('Not signed in');
    return;
  }

  const token = await user.getIdToken();

  // Test 1: prod stage
  console.log('Testing PROD stage URL...');
  try {
    const res1 = await fetch('https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod/process', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        project_name: 'Test'
      })
    });
    console.log('PROD stage:', res1.status, res1.statusText);
    const data1 = await res1.text();
    console.log('PROD response:', data1);
  } catch (e) {
    console.error('PROD error:', e);
  }

  // Test 2: $default stage
  console.log('\nTesting $DEFAULT stage URL...');
  try {
    const res2 = await fetch('https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/process', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        project_name: 'Test'
      })
    });
    console.log('$DEFAULT stage:', res2.status, res2.statusText);
    const data2 = await res2.text();
    console.log('$DEFAULT response:', data2);
  } catch (e) {
    console.error('$DEFAULT error:', e);
  }
}

test404();
```

---

## If Both URLs Return 404

If both URLs return 404, there might be an issue with the deployment. Try this:

### Force Redeploy

```bash
# Create a new deployment
aws apigatewayv2 create-deployment \
  --api-id g78mc4ok92 \
  --description "Manual deployment to fix 404" \
  --stage-name prod \
  --region us-east-1
```

Or in AWS Console:
1. Go to API Gateway Console
2. Select `opus-clip-api`
3. Click **"Deploy"** button
4. Select stage: **prod**
5. Click **"Deploy"**

---

## Check CloudWatch Logs

If still getting 404, check if requests are reaching the Lambda:

```bash
# Check opus-api-gateway Lambda logs (last 30 minutes)
aws logs filter-log-events \
  --log-group-name /aws/lambda/opus-api-gateway \
  --start-time $(($(date +%s) - 1800))000 \
  --region us-east-1 \
  --max-items 50
```

**Expected:**
- If logs show events: Lambda is being invoked (issue might be in Lambda code)
- If no logs: Requests aren't reaching Lambda (API Gateway routing issue)

---

## Alternative: Use $default Stage

The `$default` stage is the standard stage for HTTP APIs. Consider using it instead of `prod`:

**Benefits:**
- Cleaner URLs (no `/prod/` in path)
- Standard for HTTP APIs

**Update frontend:**
```javascript
// Change from:
const API_URL = 'https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod';

// To:
const API_URL = 'https://g78mc4ok92.execute-api.us-east-1.amazonaws.com';
```

---

## Summary

**What's working:**
- ✅ Authorization Lambda (`opus-authorizer`)
- ✅ Firebase token verification
- ✅ API Gateway configuration
- ✅ Routes and integrations

**What to check:**
1. Frontend API URL format (most likely cause)
2. Which stage you're using (`prod` vs `$default`)
3. Whether the URL in your code matches the stage

**Action items:**
1. Run the browser test script above
2. Check which URL works (prod vs $default)
3. Update your frontend code to use the correct URL
4. If both fail, force redeploy API Gateway

Once you identify which URL works, update your frontend configuration to use that URL consistently.
