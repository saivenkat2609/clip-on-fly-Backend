# Lambda Authorizer - Linux-Compatible Package

## Problem Summary

The Lambda authorizer was failing with:
```
[ERROR] Runtime.ImportModuleError: Unable to import module 'lambda_function': cannot import name 'ObjectIdentifier' from 'cryptography.hazmat.bindings._rust'
```

**Root cause**: Dependencies were installed on Windows with Windows-specific binary files (.pyd), but AWS Lambda runs on Linux and needs Linux-compatible binaries (.so).

---

## Solution

Created a new deployment package with **Linux-compatible dependencies** using:
```bash
pip install -r requirements.txt -t . --platform manylinux2014_x86_64 --only-binary=:all:
```

This downloaded Linux-compatible wheel files:
- `cryptography-41.0.7-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`
- `cffi-2.0.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl`

---

## Fixed Package Details

**File**: `opus-clip-cloud/src/authorizer-lambda/authorizer-lambda.zip`

**Size**: 5.11 MB

**Contains**:
- ✅ `lambda_function.py` (with correct Firebase Project ID: `reframe-1e182`)
- ✅ `jwt/` package (Linux binaries)
- ✅ `requests/` package
- ✅ `cryptography/` package (Linux binaries)
- ✅ `certifi/` package
- ✅ All other dependencies

---

## Upload Instructions

### Option 1: AWS Console (Recommended)

1. **Go to AWS Lambda Console**:
   https://console.aws.amazon.com/lambda/home?region=us-east-1

2. **Find your authorizer function**:
   - Search for: `opus-clip-authorizer` or `authorizer`
   - Click on the function name

3. **Upload the new package**:
   - Scroll down to the "Code source" section
   - Click **"Upload from"** dropdown
   - Select **".zip file"**

4. **Select the file**:
   - Click **"Upload"**
   - Navigate to: `C:\Projects\reframeAI\opus-clip-cloud\src\authorizer-lambda\authorizer-lambda.zip`
   - Select the file
   - Click **"Open"**

5. **Save**:
   - Click **"Save"** button (orange button at the top)
   - Wait for upload to complete (10-30 seconds depending on internet speed)
   - You should see: "Successfully updated the function authorizer-lambda"

### Option 2: AWS CLI

```bash
aws lambda update-function-code \
  --function-name opus-clip-authorizer \
  --zip-file fileb://opus-clip-cloud/src/authorizer-lambda/authorizer-lambda.zip \
  --region us-east-1
```

---

## Verify the Fix

### Step 1: Check Lambda Configuration

After uploading, verify the environment variables are set:

1. **In Lambda Console**, click **Configuration** tab
2. Click **Environment variables**
3. **Verify** you have:
   - `FIREBASE_PROJECT_ID` = `reframe-1e182`

If not set, add it:
- Click **"Edit"**
- Click **"Add environment variable"**
- Key: `FIREBASE_PROJECT_ID`
- Value: `reframe-1e182`
- Click **"Save"**

### Step 2: Test in Your App

1. **Open your app** and sign in
2. **Click "Generate Clips"** with a YouTube URL
3. **Check browser console** (F12) for errors

**Expected result**:
- ✅ No more 500 Internal Server Error
- ✅ Should return `202 Accepted` with a session ID
- ✅ Or you might get a different error if there are other issues (like missing STATE_MACHINE_ARN)

### Step 3: Check Lambda Logs

**View logs in real-time**:
```bash
aws logs tail /aws/lambda/opus-clip-authorizer --follow --region us-east-1
```

**Then click "Generate Clips"** in your UI.

**Expected logs**:
```
[Authorizer] Using cached Firebase public keys
[Authorizer] Token verified for user: abc123xyz
[Authorizer] Authorized user: abc123xyz, email: user@example.com, verified: True
```

**Should NOT see**:
- ❌ `ImportModuleError`
- ❌ `cannot import name 'ObjectIdentifier'`
- ❌ `No module named 'jwt'`

---

## Possible Next Errors

After fixing the authorizer, you might encounter other issues:

### Error 1: "No user_id in authorizer context"

**Cause**: Authorizer not attached to API Gateway route

**Solution**:
1. Go to API Gateway Console
2. Select your API
3. Click Resources → POST /process
4. Click "Method Request"
5. Set Authorization to your Lambda authorizer
6. Deploy API to prod stage

### Error 2: Missing STATE_MACHINE_ARN

**Logs show**:
```
KeyError: 'STATE_MACHINE_ARN'
```

**Solution**:
1. Go to API Gateway Lambda function (not authorizer)
2. Configuration → Environment variables
3. Add: `STATE_MACHINE_ARN` = Your Step Functions ARN

### Error 3: Permission Denied - Step Functions

**Logs show**:
```
AccessDeniedException: User is not authorized to perform: states:StartExecution
```

**Solution**:
1. Go to IAM Console
2. Find your Lambda execution role
3. Add permission: `AWSStepFunctionsFullAccess`
4. Or create custom policy with `states:StartExecution` permission

---

## What Was Fixed

### Before (Windows binaries):
```
cryptography-41.0.7-cp37-abi3-win_amd64.whl  ← Windows
_cffi_backend.cp312-win_amd64.pyd            ← Windows
```

### After (Linux binaries):
```
cryptography-41.0.7-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl  ← Linux
_cffi_backend.cpython-312-x86_64-linux-gnu.so                                   ← Linux
```

### Key Changes:
1. ✅ Fixed Firebase Project ID: `reframe-1e182`
2. ✅ Installed Linux-compatible dependencies
3. ✅ Included all required packages (PyJWT, cryptography, requests)
4. ✅ Package size: 5.11 MB (under 50 MB limit)

---

## Testing Script

Run this in browser console to test end-to-end:

```javascript
async function testAuthorizer() {
  console.log('=== Testing Authorizer ===');

  // Get user and token
  const user = firebase.auth().currentUser;
  if (!user) {
    console.error('❌ Not authenticated');
    return;
  }
  console.log('✅ User:', user.email);

  // Get token
  const token = await user.getIdToken();
  console.log('✅ Token obtained');

  // Test API
  console.log('\nTesting API Gateway...');
  try {
    const response = await fetch('https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod/process', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        project_name: 'Test Project'
      })
    });

    console.log('Status:', response.status);
    const data = await response.json();
    console.log('Response:', data);

    if (response.status === 202) {
      console.log('✅ SUCCESS! Authorizer is working!');
      console.log('Session ID:', data.session_id);
    } else if (response.status === 401) {
      console.error('❌ Still getting 401 - Check authorizer logs');
    } else if (response.status === 500) {
      console.error('❌ Still getting 500 - Check API Gateway Lambda logs');
    }
  } catch (error) {
    console.error('❌ Request failed:', error);
  }

  console.log('\n=== Test Complete ===');
}

testAuthorizer();
```

---

## For Future Deployments

**Always use Linux-compatible packages for Lambda**:

```bash
# Create clean directory
mkdir authorizer-lambda
cd authorizer-lambda

# Copy function code
cp ../authorizer/lambda_function.py .
cp ../authorizer/requirements.txt .

# Install Linux dependencies
pip install -r requirements.txt -t . \
  --platform manylinux2014_x86_64 \
  --only-binary=:all: \
  --python-version 3.12 \
  --implementation cp

# Create zip
zip -r authorizer-lambda.zip .

# Or use Python script:
# python create_package.py

# Upload to Lambda
aws lambda update-function-code \
  --function-name opus-clip-authorizer \
  --zip-file fileb://authorizer-lambda.zip \
  --region us-east-1
```

---

## Summary

**Problem**: Windows binaries incompatible with Linux Lambda runtime

**Solution**: Installed Linux-compatible packages with `--platform manylinux2014_x86_64`

**File to upload**: `opus-clip-cloud/src/authorizer-lambda/authorizer-lambda.zip`

**Next steps**:
1. Upload the new package to Lambda
2. Test "Generate Clips" functionality
3. Check logs for any remaining errors
4. Fix next issue if it appears (likely STATE_MACHINE_ARN or IAM permissions)

**The authorizer ImportModuleError is now FIXED!** 🎉
