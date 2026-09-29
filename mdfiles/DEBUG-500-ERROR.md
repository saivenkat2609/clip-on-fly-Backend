# Debugging 500 Internal Server Error

## Quick Diagnosis Steps

### Step 1: Check if You Redeployed the Authorizer

Did you upload the new `authorizer.zip` to AWS Lambda after I fixed the code?

**If NO** → Go to "Quick Fix" section below
**If YES** → Continue to Step 2

---

### Step 2: Check AWS Lambda Logs

The 500 error means something is failing on the backend. Let's check the logs:

#### Method A: AWS CLI (Fastest)

**Check authorizer logs**:
```bash
aws logs tail /aws/lambda/opus-clip-authorizer --follow --region us-east-1
```

**Then click "Generate Clips" in your UI** and watch for errors.

**Check API Gateway handler logs**:
```bash
aws logs tail /aws/lambda/opus-clip-api-gateway --follow --region us-east-1
```

Or if your function has a different name:
```bash
# List all Lambda functions
aws lambda list-functions --region us-east-1 --query 'Functions[*].FunctionName' --output table

# Then tail the correct one
aws logs tail /aws/lambda/YOUR-FUNCTION-NAME --follow --region us-east-1
```

#### Method B: AWS Console

1. **Go to AWS Lambda Console**: https://console.aws.amazon.com/lambda/
2. **Find your authorizer function** (e.g., `opus-clip-authorizer`)
3. **Click on it**
4. **Click "Monitor" tab**
5. **Click "View CloudWatch logs"**
6. **Click the most recent log stream**
7. **Look for errors**

Then repeat for your API Gateway handler function.

---

### Step 3: Look for These Common Errors

#### Error Pattern 1: Authorization Failed
```
[Authorizer] Authorization failed: Invalid token
[Authorizer] Token verification failed: Token expired
```

**Solution**: Frontend token issue, see "Fix Frontend Token" section below

#### Error Pattern 2: Missing Environment Variable
```
KeyError: 'STATE_MACHINE_ARN'
KeyError: 'FIREBASE_PROJECT_ID'
```

**Solution**: Set environment variables in Lambda, see "Set Environment Variables" section below

#### Error Pattern 3: Permission Denied
```
AccessDeniedException: User: arn:aws:sts::xxx:assumed-role/xxx is not authorized to perform: states:StartExecution
```

**Solution**: Fix IAM role permissions, see "Fix IAM Permissions" section below

#### Error Pattern 4: No user_id in context
```
[API] ERROR: No user_id in authorizer context - request unauthorized
```

**Solution**: Authorizer not attached to route, see "Fix API Gateway Configuration" section below

---

## Quick Fix (If You Haven't Redeployed)

### Option 1: Set Environment Variable in AWS (Fastest - No Redeployment Needed)

1. **Go to AWS Lambda Console**: https://console.aws.amazon.com/lambda/
2. **Find your authorizer function** (e.g., `opus-clip-authorizer`)
3. **Click on it**
4. **Click "Configuration" tab**
5. **Click "Environment variables"**
6. **Click "Edit"**
7. **Check if `FIREBASE_PROJECT_ID` exists**:
   - **If it exists**: Change value to `reframe-1e182`
   - **If it doesn't exist**: Click "Add environment variable"
     - Key: `FIREBASE_PROJECT_ID`
     - Value: `reframe-1e182`
8. **Click "Save"**
9. **Test again in your UI**

This is the fastest fix and doesn't require redeploying code.

### Option 2: Redeploy Updated Code

If the environment variable method doesn't work, redeploy the code:

1. **Close any editors with `lambda_function.py` open**
2. **Run these commands**:

```powershell
cd C:\Projects\reframeAI\opus-clip-cloud\src\authorizer

# Remove old zip
Remove-Item authorizer.zip -Force -ErrorAction SilentlyContinue

# Wait a moment
Start-Sleep -Seconds 2

# Create new zip
Compress-Archive -Path * -DestinationPath authorizer.zip -Force
```

3. **Upload to AWS**:
   - Go to AWS Lambda Console
   - Select your authorizer function
   - Click "Upload from" → ".zip file"
   - Select `authorizer.zip`
   - Click "Save"

4. **Test again**

---

## Set Environment Variables

Your Lambda functions need these environment variables:

### For Authorizer Lambda

| Variable | Value |
|----------|-------|
| `FIREBASE_PROJECT_ID` | `reframe-1e182` |

### For API Gateway Lambda

| Variable | Value |
|----------|-------|
| `STATE_MACHINE_ARN` | Your Step Functions ARN |
| `BUCKET_NAME` | `opus-clip-videos` (or your bucket name) |
| `ALLOWED_ORIGINS` | `*` (or your domain) |

**To set them**:
1. Go to Lambda function in AWS Console
2. Configuration → Environment variables
3. Click "Edit"
4. Add/Update variables
5. Click "Save"

---

## Fix API Gateway Configuration

The authorizer must be attached to your API routes:

### Step 1: Find Your API Gateway

```bash
# List APIs
aws apigateway get-rest-apis --region us-east-1 --query 'items[*].[name,id]' --output table
```

Note your API ID (e.g., `g78mc4ok92`)

### Step 2: Check Authorizer Configuration

```bash
# Replace API_ID with your actual API ID
aws apigateway get-authorizers --rest-api-id g78mc4ok92 --region us-east-1
```

Look for your Lambda authorizer and note its ID.

### Step 3: Check if POST /process Uses Authorizer

```bash
# Get resources
aws apigateway get-resources --rest-api-id g78mc4ok92 --region us-east-1

# Check specific method (replace RESOURCE_ID with the /process resource ID)
aws apigateway get-method --rest-api-id g78mc4ok92 --resource-id RESOURCE_ID --http-method POST --region us-east-1
```

Look for `authorizationType` and `authorizerId` in the output.

**Should see**:
```json
{
  "httpMethod": "POST",
  "authorizationType": "CUSTOM",
  "authorizerId": "abc123"
}
```

**If you see** `"authorizationType": "NONE"`, the authorizer is NOT attached.

### Step 4: Attach Authorizer (If Not Attached)

**Via AWS Console**:
1. Go to API Gateway Console
2. Select your API
3. Click "Resources"
4. Click `POST /process`
5. Click "Method Request"
6. Click edit icon next to "Authorization"
7. Select your Lambda authorizer
8. Click checkmark to save
9. **Click "Actions" → "Deploy API"**
10. Select stage: `prod`
11. Click "Deploy"

---

## Fix IAM Permissions

Your API Gateway Lambda needs permission to start Step Functions:

### Step 1: Find Lambda Role

```bash
# Get Lambda configuration
aws lambda get-function-configuration --function-name opus-clip-api-gateway --region us-east-1 --query 'Role'
```

Note the role ARN.

### Step 2: Check Current Policy

```bash
# Get role name from ARN (e.g., opus-clip-api-gateway-role)
aws iam get-role-policy --role-name opus-clip-api-gateway-role --policy-name lambda-policy --region us-east-1
```

### Step 3: Add Required Permissions

The Lambda needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "states:StartExecution",
        "states:DescribeExecution"
      ],
      "Resource": "arn:aws:states:us-east-1:*:stateMachine:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::opus-clip-videos",
        "arn:aws:s3:::opus-clip-videos/*"
      ]
    }
  ]
}
```

**To add via Console**:
1. Go to IAM Console
2. Click "Roles"
3. Find your Lambda role
4. Click "Add permissions" → "Attach policies"
5. Search for "StepFunctions"
6. Attach "AWSStepFunctionsFullAccess" (or create custom policy above)

---

## Test with Manual Request

Let's test the API manually to see the exact error:

### Step 1: Get Your Firebase Token

Open browser console on your app:
```javascript
const token = await firebase.auth().currentUser.getIdToken();
console.log(token);
```

Copy the token.

### Step 2: Test with curl

**Windows PowerShell**:
```powershell
$token = "YOUR_TOKEN_HERE"
$body = @{
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    project_name = "Test"
    startFrom = "download"
} | ConvertTo-Json

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

$response = Invoke-WebRequest -Uri "https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod/process" -Method POST -Headers $headers -Body $body -UseBasicParsing

Write-Host "Status:" $response.StatusCode
Write-Host "Body:" $response.Content
```

**Or use curl** (Git Bash / WSL):
```bash
curl -X POST \
  https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod/process \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "project_name": "Test",
    "startFrom": "download"
  }' \
  -v
```

### Step 3: Analyze Response

**If 401 Unauthorized**:
- Authorizer is rejecting the token
- Check authorizer logs
- Verify FIREBASE_PROJECT_ID is correct

**If 500 Internal Server Error**:
- API Gateway Lambda is failing
- Check API Gateway Lambda logs
- Look for specific error message

**If 202 Accepted**:
- Success! The issue might be in the frontend
- Check VITE_API_ENDPOINT in .env.local

---

## Fix Frontend Token Issue

If the authorizer says "Token expired" or "Invalid token":

### Check .env.local

Make sure you have:
```
VITE_API_ENDPOINT=https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod
```

### Verify Token Refresh

In `src/lib/apiClient.ts`, line 26 should be:
```typescript
const idToken = await user.getIdToken(); // This auto-refreshes
```

This automatically refreshes expired tokens.

### Force Token Refresh

Test with a fresh token:

```javascript
// In browser console
const user = firebase.auth().currentUser;
const token = await user.getIdToken(true); // Force refresh
console.log('Fresh token:', token);

// Then try your request again
```

---

## Common Issues Checklist

- [ ] **Redeployed authorizer** with correct Firebase Project ID
- [ ] **Set `FIREBASE_PROJECT_ID` environment variable** in Lambda
- [ ] **Authorizer is attached** to POST /process route
- [ ] **API Gateway is deployed** to prod stage
- [ ] **Lambda has correct IAM permissions** (Step Functions, S3)
- [ ] **STATE_MACHINE_ARN environment variable** is set
- [ ] **Checked Lambda logs** for specific error messages
- [ ] **Frontend is using correct API endpoint**
- [ ] **Firebase token is fresh** (not expired)

---

## Debug Script

Run this in your browser console to get detailed debug info:

```javascript
async function fullDiagnosis() {
  console.log('=== Full API Diagnosis ===\n');

  // 1. Check authentication
  const user = firebase.auth().currentUser;
  if (!user) {
    console.error('❌ Not authenticated');
    return;
  }
  console.log('✅ User:', user.uid, user.email);

  // 2. Get token
  const token = await user.getIdToken();
  console.log('✅ Got token:', token.substring(0, 20) + '...');

  // 3. Decode token
  const parts = token.split('.');
  const payload = JSON.parse(atob(parts[1]));
  console.log('Token payload:', {
    sub: payload.sub,
    email: payload.email,
    aud: payload.aud,
    exp: new Date(payload.exp * 1000),
    iat: new Date(payload.iat * 1000),
  });

  // 4. Check if token is for correct project
  if (payload.aud !== 'reframe-1e182') {
    console.error('❌ Token is for wrong project:', payload.aud);
    console.error('   Expected: reframe-1e182');
  } else {
    console.log('✅ Token is for correct project');
  }

  // 5. Test API
  console.log('\nTesting API...');
  try {
    const response = await fetch('https://g78mc4ok92.execute-api.us-east-1.amazonaws.com/prod/process', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        project_name: 'Diagnostic Test',
        startFrom: 'download'
      })
    });

    console.log('Response status:', response.status);
    console.log('Response headers:', Object.fromEntries(response.headers.entries()));

    const text = await response.text();
    console.log('Response body:', text);

    try {
      const data = JSON.parse(text);
      console.log('Parsed response:', data);
    } catch (e) {
      console.log('Could not parse response as JSON');
    }

    if (response.status === 200 || response.status === 202) {
      console.log('\n✅ API is working!');
    } else if (response.status === 401) {
      console.error('\n❌ Unauthorized - Check authorizer logs');
      console.log('Possible causes:');
      console.log('1. Authorizer has wrong FIREBASE_PROJECT_ID');
      console.log('2. Token is invalid or expired');
      console.log('3. Authorizer can\'t reach Firebase public keys');
    } else if (response.status === 500) {
      console.error('\n❌ Internal Server Error - Check Lambda logs');
      console.log('Possible causes:');
      console.log('1. Missing environment variables (STATE_MACHINE_ARN)');
      console.log('2. Missing IAM permissions');
      console.log('3. Step Functions not configured');
      console.log('4. Lambda execution error');
    } else {
      console.error('\n❌ Unexpected status:', response.status);
    }
  } catch (e) {
    console.error('\n❌ Request failed:', e);
  }

  console.log('\n=== Diagnosis Complete ===');
}

fullDiagnosis();
```

---

## Next Steps

1. **Run the diagnosis script** in browser console
2. **Check Lambda logs** using AWS CLI or Console
3. **Look for the specific error** in the logs
4. **Follow the fix** for that specific error
5. **Test again**

Once we see the exact error from the Lambda logs, we can fix it precisely!
