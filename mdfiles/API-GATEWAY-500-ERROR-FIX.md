# API Gateway 500 Error - Fix Guide

## Problem Summary

When clicking "Generate Clips", you get a **500 Internal Server Error** from:
```
POST https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod/process
```

## Root Causes Identified

### 1. **CRITICAL**: Wrong Firebase Project ID in Lambda Authorizer

**File**: `opus-clip-cloud/src/authorizer/lambda_function.py:21`

**Current code**:
```python
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'reframeai-87b24')
```

**Problem**: The default value is `'reframeai-87b24'`, but your actual Firebase project is `'reframe-1e182'`

**Impact**: The Lambda authorizer can't verify Firebase JWT tokens, causing authentication to fail.

---

### 2. Firestore Permission Errors

**Error**: `"Missing or insufficient permissions"` when fetching notifications

**Problem**: Firestore security rules are too restrictive or notifications collection doesn't have proper rules.

---

### 3. Cross-Origin-Opener-Policy (COOP) Warnings

**Error**: Multiple COOP policy warnings with Firebase Auth

**Problem**: Browser security policy blocking popup/redirect detection

**Impact**: Non-critical, just warnings

---

### 4. Ad Blocker Blocking Firebase Requests

**Error**: `net::ERR_BLOCKED_BY_CLIENT`

**Problem**: Browser extension (likely ad blocker) blocking Firestore requests

**Impact**: May cause intermittent failures

---

## Fix Instructions

### Fix 1: Update Lambda Authorizer Firebase Project ID

#### Option A: Update Environment Variable in AWS Lambda (Recommended)

1. **Go to AWS Lambda Console**:   https://console.aws.amazon.com/lambda/

2. **Find your authorizer function**:
   - Search for: `opus-clip-authorizer` or `authorizer`

3. **Update environment variable**:
   - Click on **Configuration** tab
   - Click **Environment variables**
   - Look for `FIREBASE_PROJECT_ID`
   - If it exists:
     - Click **Edit**
     - Change value to: `reframe-1e182`
     - Click **Save**
   - If it doesn't exist:
     - Click **Add environment variable**
     - Key: `FIREBASE_PROJECT_ID`
     - Value: `reframe-1e182`
     - Click **Save**

4. **Test the function** (optional but recommended):
   - Click **Test** tab
   - Create a test event with:
   ```json
   {
     "type": "TOKEN",
     "authorizationToken": "Bearer your-actual-firebase-token-here",
     "methodArn": "arn:aws:execute-api:us-east-1:123456789012:*/prod/POST/process"
   }
   ```
   - Click **Test**
   - Should see `"Effect": "Allow"` in response

#### Option B: Update Code and Redeploy

1. **Update the Lambda function code**:

**Edit**: `opus-clip-cloud/src/authorizer/lambda_function.py`

Change line 21 from:
```python
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'reframeai-87b24')
```

To:
```python
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'reframe-1e182')
```

2. **Recreate deployment package**:
```powershell
cd opus-clip-cloud/src/authorizer

# Remove old zip
Remove-Item authorizer.zip -ErrorAction SilentlyContinue

# Create new zip
Compress-Archive -Path * -DestinationPath authorizer.zip -Force
```

3. **Redeploy to AWS Lambda**:
   - Go to AWS Lambda Console
   - Select your authorizer function
   - Click **Upload from** → **.zip file**
   - Select `authorizer.zip`
   - Click **Save**

---

### Fix 2: Verify API Gateway Configuration

1. **Go to API Gateway Console**:
   https://console.aws.amazon.com/apigateway/

2. **Find your API**:
   - Should be: `opus-clip-api` or similar

3. **Check authorizer configuration**:
   - Click **Authorizers** (left sidebar)
   - Should see your Lambda authorizer
   - **Verify**:
     - **Type**: Lambda
     - **Lambda Function**: Your authorizer function ARN
     - **Token Source**: `Authorization` (header name)
     - **Token Validation**: (can be empty or regex)
     - **Authorization Caching**: Enabled (recommended, 300 seconds)

4. **Check route/method configuration**:
   - Click **Resources** (left sidebar)
   - Find `POST /process`
   - Click **Method Request**
   - **Verify**:
     - **Authorization**: Should point to your Lambda authorizer (NOT "NONE")
     - **API Key Required**: False (unless you're using API keys)

5. **Deploy API** (if you made changes):
   - Click **Actions** → **Deploy API**
   - Stage: `prod`
   - Click **Deploy**

---

### Fix 3: Update Firestore Security Rules

**Edit**: `reframe-ai/firestore.rules`

Make sure you have these rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // User documents - users can read/write their own
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;

      // Videos subcollection
      match /videos/{videoId} {
        allow read, write: if request.auth != null && request.auth.uid == userId;
      }

      // Notifications subcollection
      match /notifications/{notificationId} {
        allow read, write: if request.auth != null && request.auth.uid == userId;
      }
    }

    // Social media connections (YouTube)
    match /user_social_connections/{connectionId} {
      allow read: if request.auth != null && request.auth.uid == resource.data.userId;
      allow write: if request.auth != null && request.auth.uid == request.resource.data.userId;
      allow delete: if request.auth != null && request.auth.uid == resource.data.userId;
    }
  }
}
```

**Deploy rules**:
```bash
cd reframe-ai
firebase deploy --only firestore:rules
```

---

### Fix 4: Handle COOP Policy Warnings

The COOP warnings are caused by Firebase Auth using popups. You have two options:

#### Option A: Ignore Warnings (Recommended)

These are just warnings and don't break functionality. Firebase Auth works despite the warnings.

#### Option B: Add Headers to Your App

If hosting on Netlify/Vercel, add to `netlify.toml` or `vercel.json`:

**Netlify** (`netlify.toml`):
```toml
[[headers]]
  for = "/*"
  [headers.values]
    Cross-Origin-Opener-Policy = "same-origin-allow-popups"
```

**Vercel** (`vercel.json`):
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Cross-Origin-Opener-Policy",
          "value": "same-origin-allow-popups"
        }
      ]
    }
  ]
}
```

---

### Fix 5: Disable Ad Blocker (For Testing)

The `ERR_BLOCKED_BY_CLIENT` error is caused by browser extensions blocking Firebase requests.

**Temporary fix** (for testing):
1. Open browser extension settings
2. Disable ad blocker for your app domain
3. Reload page

**Permanent fix**:
- None needed, users will need to whitelist your domain
- Or use a custom domain instead of localhost

---

## Testing the Fix

### Step 1: Test Authentication

1. **Get a Firebase ID Token**:

Open browser console on your app and run:
```javascript
// Get current user's token
const token = await firebase.auth().currentUser.getIdToken();
console.log('Token:', token);
```

2. **Test the authorizer directly**:

Using AWS CLI:
```bash
# Create test event
cat > test-event.json << 'EOF'
{
  "type": "TOKEN",
  "authorizationToken": "Bearer <YOUR_TOKEN_HERE>",
  "methodArn": "arn:aws:execute-api:us-east-1:123456789012:*/prod/POST/process"
}
EOF

# Invoke authorizer
aws lambda invoke \
  --function-name opus-clip-authorizer \
  --payload file://test-event.json \
  --region us-east-1 \
  response.json

# Check response
cat response.json
```

Expected response:
```json
{
  "principalId": "user-id-here",
  "policyDocument": {
    "Version": "2012-10-17",
    "Statement": [{
      "Action": "execute-api:Invoke",
      "Effect": "Allow",
      "Resource": "arn:aws:execute-api:..."
    }]
  },
  "context": {
    "userId": "user-id-here",
    "email": "user@example.com",
    "emailVerified": "True",
    "provider": "google.com"
  }
}
```

### Step 2: Test API Endpoint

1. **Open your app**
2. **Sign in with Google**
3. **Open browser console** (F12)
4. **Paste this code**:

```javascript
// Test API directly
async function testAPI() {
  const token = await firebase.auth().currentUser.getIdToken();

  const response = await fetch('https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod/process', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
      project_name: 'Test Project',
      startFrom: 'download'
    })
  });

  const data = await response.json();
  console.log('Status:', response.status);
  console.log('Response:', data);
}

testAPI();
```

**Expected response** (202 Accepted):
```json
{
  "session_id": "uuid-here",
  "status": "processing",
  "execution_arn": "arn:aws:states:..."
}
```

**If you still get 500**, check Lambda logs (next step).

### Step 3: Check Lambda Logs

**View authorizer logs**:
```bash
aws logs tail /aws/lambda/opus-clip-authorizer --follow
```

**View API Gateway logs**:
```bash
aws logs tail /aws/lambda/opus-clip-api-gateway --follow
```

**Look for errors**:
- `Token verification failed`
- `Invalid token`
- `Token expired`
- `No user_id in authorizer context`

---

## Common Errors After Fix

### Error: "Token verification failed"

**Cause**: Authorizer can't fetch Firebase public keys

**Solution**: Check Lambda has internet access (not in VPC without NAT)

---

### Error: "Invalid key ID"

**Cause**: Firebase public keys cache is stale

**Solution**: Wait 1 hour or clear cache by redeploying Lambda

---

### Error: "No user_id in authorizer context"

**Cause**: Authorizer is not attached to API Gateway route

**Solution**: Check API Gateway configuration (Fix 2 above)

---

### Error: "Token expired"

**Cause**: Firebase token expired (tokens expire after 1 hour)

**Solution**: Frontend should automatically refresh token. Check `apiClient.ts` line 26:
```typescript
const idToken = await user.getIdToken(); // This auto-refreshes
```

---

## Quick Diagnosis Script

Run this in browser console to diagnose issues:

```javascript
async function diagnose() {
  console.log('=== Diagnosis Start ===');

  // 1. Check if user is authenticated
  const user = firebase.auth().currentUser;
  if (!user) {
    console.error('❌ Not authenticated');
    return;
  }
  console.log('✅ Authenticated:', user.uid);

  // 2. Get Firebase ID token
  let token;
  try {
    token = await user.getIdToken();
    console.log('✅ Got Firebase token');

    // Decode token (client-side, just to see claims)
    const parts = token.split('.');
    const payload = JSON.parse(atob(parts[1]));
    console.log('Token claims:', {
      uid: payload.sub,
      email: payload.email,
      exp: new Date(payload.exp * 1000),
      project: payload.aud
    });

    if (payload.aud !== 'reframe-1e182') {
      console.warn('⚠️ Token project mismatch!', payload.aud);
    }
  } catch (e) {
    console.error('❌ Failed to get token:', e);
    return;
  }

  // 3. Test API endpoint
  try {
    const response = await fetch('https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod/process', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        youtube_url: 'https://www.youtube.com/watch?v=test',
        project_name: 'Diagnostic Test'
      })
    });

    console.log('API Response Status:', response.status);
    const data = await response.json();
    console.log('API Response Data:', data);

    if (response.status === 200 || response.status === 202) {
      console.log('✅ API working!');
    } else {
      console.error('❌ API error:', data);
    }
  } catch (e) {
    console.error('❌ API request failed:', e);
  }

  console.log('=== Diagnosis End ===');
}

diagnose();
```

---

## Priority Order

To fix the 500 error, follow this order:

### 1. **Fix Lambda Authorizer** (CRITICAL - Do This First!)
   - Update `FIREBASE_PROJECT_ID` to `reframe-1e182`
   - Redeploy authorizer Lambda

### 2. **Verify API Gateway Configuration**
   - Check authorizer is attached to routes
   - Deploy API if needed

### 3. **Test with browser console**
   - Run diagnosis script
   - Check for authorization errors

### 4. **Fix Firestore Rules**
   - Deploy updated rules
   - Test notifications

### 5. **Handle COOP Warnings** (Optional)
   - Add headers to hosting config
   - Or ignore (non-critical)

---

## Summary

**Main Issue**: Lambda authorizer has wrong Firebase Project ID

**Quick Fix**:
1. AWS Lambda Console → `opus-clip-authorizer`
2. Configuration → Environment variables
3. Add/Update: `FIREBASE_PROJECT_ID` = `reframe-1e182`
4. Save and test

**After fix**, the 500 error should be resolved and "Generate Clips" should work!

---

## Need More Help?

If the issue persists after following this guide:

1. **Check Lambda logs**:
   ```bash
   aws logs tail /aws/lambda/opus-clip-authorizer --follow
   ```

2. **Run diagnosis script** in browser console

3. **Check API Gateway logs**:
   - API Gateway Console → Your API → Stages → prod → Logs/Tracing
   - Enable CloudWatch logs if not already enabled

4. **Verify Step Functions**:
   - Check if State Machine ARN is set correctly
   - Test Step Functions execution manually
