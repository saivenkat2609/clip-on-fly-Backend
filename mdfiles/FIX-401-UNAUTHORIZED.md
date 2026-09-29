# Fix 401 Unauthorized Error

## Progress Made ✅

We've gone from:
- ❌ 500 Internal Server Error (Lambda couldn't import modules)
- ✅ 401 Unauthorized (Lambda is running, but authorization is failing)

This is **good progress**! The authorizer is now executing.

---

## Quick Fix

### Step 1: Change Lambda Runtime to Python 3.12

The error shows your Lambda is using Python 3.14, which is causing compatibility issues.

**AWS Console**:
1. Go to **AWS Lambda Console**: https://console.aws.amazon.com/lambda/
2. Find your authorizer function (e.g., `opus-clip-authorizer`)
3. Click on it
4. Scroll to **"Runtime settings"** section
5. Click **"Edit"**
6. Change **Runtime** to: **Python 3.12**
7. Click **"Save"**

**AWS CLI**:
```bash
aws lambda update-function-configuration \
  --function-name opus-clip-authorizer \
  --runtime python3.12 \
  --region us-east-1
```

### Step 2: Set Environment Variable

While you're in the Lambda console:

1. Click **"Configuration"** tab
2. Click **"Environment variables"**
3. Click **"Edit"**
4. **Add or update**:
   - Key: `FIREBASE_PROJECT_ID`
   - Value: `reframe-1e182`
5. Click **"Save"**

### Step 3: Test Again

1. Refresh your app
2. Sign in
3. Click "Generate Clips"
4. Check if it works

---

## If Still Getting 401

Run this diagnostic in browser console (F12):

```javascript
async function diagnose401() {
  console.log('=== Diagnosing 401 Error ===\n');

  // Get user
  const user = firebase.auth().currentUser;
  if (!user) {
    console.error('❌ Not signed in');
    return;
  }
  console.log('✅ User:', user.email);

  // Get token
  const token = await user.getIdToken(true); // Force fresh token
  console.log('✅ Fresh token obtained');

  // Decode token
  const parts = token.split('.');
  const payload = JSON.parse(atob(parts[1]));
  console.log('\nToken details:');
  console.log('  Project (aud):', payload.aud);
  console.log('  User ID (sub):', payload.sub);
  console.log('  Email:', payload.email);
  console.log('  Issued:', new Date(payload.iat * 1000));
  console.log('  Expires:', new Date(payload.exp * 1000));
  console.log('  Issuer:', payload.iss);

  // Check project
  if (payload.aud !== 'reframe-1e182') {
    console.error('❌ Token is for wrong project!');
    console.error('   Expected: reframe-1e182');
    console.error('   Got:', payload.aud);
    return;
  }
  console.log('✅ Token is for correct project');

  // Check if expired
  const now = Date.now() / 1000;
  if (payload.exp < now) {
    console.error('❌ Token is expired!');
    return;
  }
  console.log('✅ Token is not expired');

  // Test API
  console.log('\nTesting API...');
  const response = await fetch('https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod/process', {
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

  console.log('\nAPI Response:');
  console.log('  Status:', response.status);

  const text = await response.text();
  console.log('  Body:', text);

  if (response.status === 401) {
    console.error('\n❌ Still getting 401 - Check authorizer logs');
    console.log('\nTo check logs, run in terminal:');
    console.log('aws logs tail /aws/lambda/opus-clip-authorizer --follow --region us-east-1');
  } else if (response.status === 202) {
    console.log('\n✅ SUCCESS! Authorization working!');
  }

  console.log('\n=== Diagnosis Complete ===');
}

diagnose401();
```

---

## Check Authorizer Logs

**Terminal**:
```bash
aws logs tail /aws/lambda/opus-clip-authorizer --follow --region us-east-1
```

Then click "Generate Clips" in your UI and watch for errors.

**Look for**:
- `[Authorizer] Token verified for user: xxx` - ✅ Good
- `[Authorizer] Token verification failed` - ❌ Problem
- `[Authorizer] Invalid token` - ❌ Problem
- `[Authorizer] Token expired` - ❌ Problem

---

## Common Causes of 401

### Cause 1: Wrong Firebase Project ID

**Check**: Lambda environment variable `FIREBASE_PROJECT_ID` should be `reframe-1e182`

**Fix**: Set it in Lambda Configuration → Environment variables

### Cause 2: Runtime Incompatibility

**Check**: Lambda runtime should be Python 3.12

**Fix**: Change in Lambda Configuration → Runtime settings

### Cause 3: Authorizer Can't Fetch Firebase Keys

**Check**: Lambda has internet access

**Fix**: If Lambda is in VPC, ensure it has NAT Gateway or remove from VPC

### Cause 4: Token Is Invalid

**Check**: Run the diagnostic script above

**Fix**:
- Sign out and sign back in
- Force token refresh: `await user.getIdToken(true)`

---

## Quick Commands Reference

```bash
# Change Lambda runtime to Python 3.12
aws lambda update-function-configuration \
  --function-name opus-clip-authorizer \
  --runtime python3.12 \
  --region us-east-1

# Set Firebase Project ID
aws lambda update-function-configuration \
  --function-name opus-clip-authorizer \
  --environment Variables={FIREBASE_PROJECT_ID=reframe-1e182} \
  --region us-east-1

# View authorizer logs
aws logs tail /aws/lambda/opus-clip-authorizer --follow --region us-east-1

# Test authorizer directly
aws lambda invoke \
  --function-name opus-clip-authorizer \
  --payload '{"type":"TOKEN","authorizationToken":"Bearer YOUR_TOKEN","methodArn":"arn:aws:execute-api:us-east-1:123456789012:*/prod/POST/process"}' \
  --region us-east-1 \
  response.json && cat response.json
```

---

## Next Steps

1. ✅ Change Lambda runtime to Python 3.12
2. ✅ Set FIREBASE_PROJECT_ID environment variable
3. ✅ Test "Generate Clips" again
4. ✅ Run diagnostic script if still failing
5. ✅ Check authorizer logs for specific error

Once we see the exact error from the logs, we can fix it quickly!
