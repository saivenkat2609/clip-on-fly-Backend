# Firebase Admin SDK Migration Guide

## Overview

This guide covers the migration from Firebase Web API Key authentication to Firebase Admin SDK for backend Firestore operations (High Priority Issue #9).

## Why This Change is Critical

### Security Issue: Web API Key Exposure
**Problem:** Firebase Web API Keys are designed for client-side use and can be extracted from frontend bundles.

**Attack Scenario:**
1. Attacker opens browser DevTools and extracts Firebase Web API Key from network requests or JavaScript bundle
2. Attacker uses the key to directly call Firestore REST API
3. Attacker can add/modify clips to any user's video, manipulate statistics, or create fake data

**Solution:** Use Firebase Admin SDK with service account credentials that never leave the backend.

---

## What Changed

### Files Modified

#### 1. `src/shared/firestore_client.py` (Complete Rewrite)
**Before:** Used Firebase Web API Key with Firestore REST API
```python
req.add_header('Authorization', f'Bearer {FIREBASE_WEB_API_KEY}')
```

**After:** Uses Firebase Admin SDK with service account
```python
from firebase_admin import firestore, credentials
db = firestore.client()
doc_ref = db.collection('users').document(user_id).collection('videos').document(session_id)
```

#### 2. `src/finalize/lambda_function.py` (Updated)
**Changes:**
- Replaced `update_firestore_video()` function to use Admin SDK
- Replaced `update_user_stats()` function to use Admin SDK
- Added firestore_client import
- Removed Firebase Web API Key dependency

#### 3. `src/finalize/requirements.txt` (Updated)
**Added:**
```
firebase-admin==6.5.0
```

---

## Deployment Prerequisites

### 1. Get Firebase Service Account Credentials

1. **Go to Firebase Console:**
   - Navigate to https://console.firebase.google.com
   - Select your project: `reframeai-87b24`

2. **Generate Service Account Key:**
   - Click the gear icon (⚙️) → Project Settings
   - Navigate to "Service Accounts" tab
   - Click "Generate New Private Key"
   - Confirm and download the JSON file
   - **IMPORTANT:** Keep this file secure - it grants full admin access to your Firestore database

3. **Rename the file:**
   ```bash
   mv ~/Downloads/reframeai-87b24-firebase-adminsdk-*.json firebase-service-account.json
   ```

### 2. Store Service Account in AWS Secrets Manager

```bash
# Create secret in AWS Secrets Manager
aws secretsmanager create-secret \
    --name prod/opus-clip/firebase-service-account \
    --description "Firebase Admin SDK service account credentials" \
    --secret-string file://firebase-service-account.json \
    --region us-east-1

# Verify secret was created
aws secretsmanager describe-secret \
    --secret-id prod/opus-clip/firebase-service-account \
    --region us-east-1
```

**Security Note:** Never commit `firebase-service-account.json` to git. Add it to `.gitignore`:
```bash
echo "firebase-service-account.json" >> .gitignore
```

### 3. Alternative: Store in Lambda Environment (Less Secure)

If you prefer not to use Secrets Manager initially, you can store the service account as a Lambda environment variable:

```bash
# Convert JSON to base64
cat firebase-service-account.json | base64 > firebase-service-account.base64.txt
```

Then in your Lambda configuration:
- Environment variable: `FIREBASE_SERVICE_ACCOUNT_BASE64`
- Value: [paste base64 content]

Update `firestore_client.py` to decode it:
```python
import base64
import tempfile

service_account_base64 = os.environ.get('FIREBASE_SERVICE_ACCOUNT_BASE64')
if service_account_base64:
    service_account_json = base64.b64decode(service_account_base64)
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        f.write(service_account_json.decode())
        cred_path = f.name
```

**Note:** This approach is less secure than Secrets Manager but simpler for initial testing.

---

## Deployment Steps

### Step 1: Update Shared Firestore Client

The shared Firestore client has already been updated. Deploy it to Lambda Layer:

```bash
cd opus-clip-cloud/src/shared

# Create deployment package
mkdir -p python
cp firestore_client.py python/

# Create ZIP for Lambda Layer
zip -r firestore-layer.zip python/

# Upload to Lambda Layer
aws lambda publish-layer-version \
    --layer-name opus-clip-firestore-admin \
    --description "Firestore Admin SDK client" \
    --zip-file fileb://firestore-layer.zip \
    --compatible-runtimes python3.9 python3.10 python3.11 \
    --region us-east-1

# Note the LayerVersionArn from the output
```

### Step 2: Update IAM Permissions

Add Secrets Manager permissions to Lambda execution role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:prod/opus-clip/firebase-service-account-*"
      ]
    }
  ]
}
```

Update in `serverless.yml`:
```yaml
provider:
  iam:
    role:
      statements:
        - Effect: Allow
          Action:
            - secretsmanager:GetSecretValue
            - secretsmanager:DescribeSecret
          Resource:
            - arn:aws:secretsmanager:${aws:region}:${aws:accountId}:secret:prod/opus-clip/firebase-service-account-*
```

### Step 3: Install Firebase Admin SDK

```bash
cd opus-clip-cloud/src/finalize
pip install -r requirements.txt -t .
```

Or if using Lambda layers:
```bash
mkdir -p python
pip install firebase-admin==6.5.0 -t python/
zip -r firebase-admin-layer.zip python/

aws lambda publish-layer-version \
    --layer-name opus-clip-firebase-admin-sdk \
    --description "Firebase Admin SDK" \
    --zip-file fileb://firebase-admin-layer.zip \
    --compatible-runtimes python3.9 python3.10 python3.11 \
    --region us-east-1
```

### Step 4: Deploy Updated Lambda Functions

#### Option A: Using Serverless Framework

```bash
cd opus-clip-cloud
serverless deploy --stage prod
```

#### Option B: Manual Deployment

```bash
# Deploy finalize Lambda
cd opus-clip-cloud/src/finalize
zip -r finalize-lambda.zip lambda_function.py

aws lambda update-function-code \
    --function-name opus-clip-finalize \
    --zip-file fileb://finalize-lambda.zip \
    --region us-east-1

# Add Lambda layers (if using layers approach)
aws lambda update-function-configuration \
    --function-name opus-clip-finalize \
    --layers \
        arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:layer:opus-clip-firestore-admin:1 \
        arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:layer:opus-clip-firebase-admin-sdk:1 \
    --region us-east-1
```

### Step 5: Configure Environment Variables

Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to the service account location.

**If using Secrets Manager:**
Create a Lambda initialization script that fetches the secret and stores it in `/tmp`:

```python
import boto3
import json
import os

def initialize_firebase_credentials():
    """Fetch Firebase service account from Secrets Manager and save to /tmp"""
    if os.path.exists('/tmp/firebase-service-account.json'):
        return  # Already initialized

    secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
    secret = secrets_client.get_secret_value(SecretId='prod/opus-clip/firebase-service-account')

    with open('/tmp/firebase-service-account.json', 'w') as f:
        f.write(secret['SecretString'])

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/tmp/firebase-service-account.json'

# Call this at the top of lambda_function.py
initialize_firebase_credentials()
```

**If using Lambda environment variable:**
```bash
aws lambda update-function-configuration \
    --function-name opus-clip-finalize \
    --environment Variables="{GOOGLE_APPLICATION_CREDENTIALS=/tmp/firebase-service-account.json}" \
    --region us-east-1
```

### Step 6: Test the Deployment

#### Test 1: Verify Firestore Client Initialization

Check CloudWatch logs for successful initialization:
```
[Firestore] ✓ Admin SDK initialized successfully
```

#### Test 2: Process a Video

1. Upload a video through your application
2. Wait for processing to complete
3. Check CloudWatch logs for finalize Lambda:
   - Should see: `[Firestore] ✓ Successfully updated video {session_id}`
   - Should see: `[Firestore] ✓ Incremented user stats: totalClips += N`

#### Test 3: Verify Firestore Data

```bash
# Use Firebase CLI to check Firestore data
firebase firestore:get users/{USER_ID}/videos/{SESSION_ID} --project reframeai-87b24
```

Or check in Firebase Console:
- Navigate to Firestore Database
- Check that video documents are being updated correctly
- Verify user statistics are incrementing

---

## Rollback Plan

If issues occur, you can quickly rollback:

### Quick Rollback (Restore Previous Version)

```bash
# Restore previous Lambda version
aws lambda update-function-code \
    --function-name opus-clip-finalize \
    --s3-bucket your-deployment-bucket \
    --s3-key previous-version/finalize-lambda.zip \
    --region us-east-1
```

### Temporary Fix (Hybrid Mode)

The new code includes fallback logic. If Firebase Admin SDK fails, it will log warnings but won't crash:

```python
if not FIRESTORE_CLIENT_AVAILABLE:
    print("[Firestore] WARNING: Firestore client not available, skipping update")
    return
```

This allows the rest of the processing to continue even if Firestore updates fail.

---

## Verification Checklist

After deployment, verify:

- [ ] Firebase Admin SDK installed in Lambda
- [ ] Service account credentials stored securely (Secrets Manager or env var)
- [ ] Lambda has IAM permissions to access Secrets Manager
- [ ] CloudWatch logs show successful Firestore client initialization
- [ ] Video processing completes successfully
- [ ] Firestore documents are being updated with clips
- [ ] User statistics are incrementing correctly
- [ ] No errors in CloudWatch logs related to Firestore
- [ ] Environment variable `FIREBASE_WEB_API_KEY` removed from Lambda config

---

## Troubleshooting

### Issue: "firebase-admin not installed"

**Solution:**
```bash
cd opus-clip-cloud/src/finalize
pip install firebase-admin==6.5.0 -t .
# Or create/update Lambda layer
```

### Issue: "Could not initialize Firestore client"

**Possible Causes:**
1. Service account JSON not found
2. Invalid service account credentials
3. Missing IAM permissions for Secrets Manager

**Debug Steps:**
```python
# Add to lambda_function.py for debugging
import os
print(f"GOOGLE_APPLICATION_CREDENTIALS: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
print(f"File exists: {os.path.exists(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', ''))}")
```

### Issue: "Permission denied" errors in Firestore

**Solution:**
- Verify service account has correct Firestore permissions
- Check Firebase IAM & Admin settings
- Service account should have "Firebase Admin SDK Administrator Service Agent" role

### Issue: Lambda timeout when initializing Firebase

**Solution:**
- Increase Lambda timeout (recommended: 30 seconds for finalize)
- Firebase Admin SDK initialization can take 2-5 seconds on cold start
- Consider keeping Lambda warm with CloudWatch Events

```yaml
# In serverless.yml
functions:
  finalize:
    timeout: 30  # Increased from default 6 seconds
```

---

## Performance Considerations

### Cold Start Impact
- Firebase Admin SDK adds ~2-3 seconds to cold start
- Warm Lambda invocations have negligible overhead
- Consider using Lambda provisioned concurrency for critical paths

### Caching
The Firestore client is cached globally across invocations:
```python
_firestore_client = None  # Cached across invocations

if _firestore_client is not None:
    return _firestore_client  # Reuse existing client
```

### Connection Pooling
Firebase Admin SDK automatically manages connection pooling. No additional configuration needed.

---

## Security Benefits

### Before (Web API Key)
- ❌ API key extractable from frontend
- ❌ Anyone with key can access Firestore
- ❌ No audit trail of backend operations
- ❌ Key in environment variables (visible in console)

### After (Admin SDK)
- ✅ Service account credentials never exposed to frontend
- ✅ Only backend Lambda functions can access Firestore
- ✅ Full audit trail in Firebase console
- ✅ Credentials in Secrets Manager with encryption
- ✅ IAM-based access control

---

## Cost Impact

### Firebase Admin SDK
- No additional cost
- Same Firestore pricing as before
- Slightly higher Lambda cold start time (2-3 seconds)

### AWS Secrets Manager (if used)
- $0.40 per secret per month
- $0.05 per 10,000 API calls
- With caching, minimal API calls (~$0.01/month)

**Total Additional Cost:** ~$0.41/month

---

## Next Steps After Migration

1. **Remove FIREBASE_WEB_API_KEY from all Lambdas:**
   ```bash
   aws lambda update-function-configuration \
       --function-name opus-clip-finalize \
       --environment Variables="{}" \
       --region us-east-1
   ```

2. **Update .env.example:**
   Remove `FIREBASE_WEB_API_KEY` line

3. **Update Documentation:**
   Update README to reflect Admin SDK usage

4. **Rotate Service Account Key:**
   Set up automatic rotation every 90 days using AWS Lambda

5. **Monitor CloudWatch Logs:**
   Set up alarms for Firestore errors

---

## Support

If you encounter issues:
1. Check CloudWatch logs: `/aws/lambda/opus-clip-finalize`
2. Verify service account permissions in Firebase Console
3. Test service account locally:
   ```python
   import firebase_admin
   from firebase_admin import credentials, firestore

   cred = credentials.Certificate('firebase-service-account.json')
   firebase_admin.initialize_app(cred)
   db = firestore.client()

   # Test read
   doc = db.collection('users').document('test-user-id').get()
   print(f"Document exists: {doc.exists}")
   ```

For additional help, consult:
- [Firebase Admin SDK Documentation](https://firebase.google.com/docs/admin/setup)
- [Firestore Security Rules](https://firebase.google.com/docs/firestore/security/get-started)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
