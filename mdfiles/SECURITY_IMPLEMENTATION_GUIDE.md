# Secure Authentication Implementation Guide

## Overview

This guide covers the enterprise-grade authentication security implementation for reframe-ai and opus-clip-cloud. The implementation includes JWT verification, rate limiting, security logging, and comprehensive API protection.

## ✅ Completed Implementation

### Phase 1: Core Security (COMPLETED)

#### 1. Frontend - API Client Layer
**File Created**: `reframe-ai/src/lib/apiClient.ts`

- Centralized API client with automatic Firebase JWT token injection
- Handles token refresh automatically
- Consistent error handling across all API calls
- Supports GET, POST, PUT, DELETE methods

#### 2. Backend - Lambda Authorizer
**Files Created**:
- `opus-clip-cloud/src/authorizer/lambda_function.py`
- `opus-clip-cloud/src/authorizer/requirements.txt`

Features:
- Verifies Firebase JWT tokens before requests reach Lambda functions
- Caches Firebase public keys for 1 hour (performance optimization)
- Extracts verified user information and passes to Lambda context
- Returns IAM policy for API Gateway authorization

#### 3. Lambda Functions - Secure Context Extraction
**Files Modified**:
- `opus-clip-cloud/src/api-gateway/lambda_function.py`
- `opus-clip-cloud/src/upload-api-gateway/lambda_function.py`

Changes:
- Extract `user_id` from authorizer context instead of request body
- Verify user authorization for all endpoints
- Added 401 Unauthorized responses for missing auth
- Added 403 Forbidden responses for unauthorized resource access
- Updated CORS headers to support configurable allowed origins

#### 4. Frontend - Secure API Calls
**Files Modified**:
- `reframe-ai/src/pages/Upload.tsx`
- `reframe-ai/src/components/UploadHero.tsx`

Changes:
- Replaced direct `fetch()` calls with `apiClient`
- Removed `user_id` and `user_email` from request bodies (now from JWT)
- Automatic token injection on every request

#### 5. Firestore Security Rules
**File Modified**: `reframe-ai/firestore.rules`

- Fixed overly permissive `allow update: if true` rule
- Now only allows video updates by the owner
- Lambda functions using Admin SDK still bypass these rules (as intended)

#### 6. Rate Limiting Service
**File Created**: `opus-clip-cloud/src/shared/rate_limiter.py`

Features:
- Per-user, per-endpoint rate limiting
- Sliding window algorithm
- DynamoDB-backed for persistence
- Configurable limits per endpoint
- Automatic TTL cleanup
- Fails open (allows requests if DynamoDB unavailable)

Rate Limits:
- `/process`: 10 requests/hour (YouTube processing)
- `/upload/generate-url`: 20 requests/hour
- `/upload/start`: 10 requests/hour
- `/status`: 100 requests/minute
- `/result`: 100 requests/minute

#### 7. Security Logging Service
**File Created**: `opus-clip-cloud/src/shared/security_logger.py`

Features:
- Structured JSON logging for CloudWatch
- API request logging with user identification
- Rate limit violation tracking
- Authentication failure logging
- Suspicious activity detection (SQL injection, XSS, path traversal)
- Data access audit trails

---

## 🚀 Deployment Steps

### Step 1: Deploy Lambda Authorizer

```bash
cd opus-clip-cloud/src/authorizer

# Install dependencies
pip install -r requirements.txt -t .

# Create deployment package
zip -r authorizer.zip lambda_function.py requirements.txt

# Create Lambda function
aws lambda create-function \
  --function-name opus-authorizer \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://authorizer.zip \
  --timeout 10 \
  --memory-size 256 \
  --environment Variables={FIREBASE_PROJECT_ID=reframeai-87b24}
```

### Step 2: Attach Authorizer to API Gateway

1. Go to AWS API Gateway Console
2. Select your API
3. Click "Authorizers" in left menu
4. Click "Create New Authorizer"
5. Configure:
   - Name: `FirebaseJWTAuthorizer`
   - Type: `Lambda`
   - Lambda Function: `opus-authorizer`
   - Lambda Event Payload: `Token`
   - Token Source: `Authorization`
   - Token Validation: `^Bearer [-0-9a-zA-Z\._]*$`
   - Authorization Caching: `Enabled` (TTL: 300 seconds)

6. Click "Create"
7. Go to each endpoint (`/process`, `/upload/start`, etc.)
8. Click "Method Request"
9. Change "Authorization" to `FirebaseJWTAuthorizer`
10. Deploy API

### Step 3: Create DynamoDB Tables

#### Rate Limiting Table

```bash
aws dynamodb create-table \
  --table-name api_rate_limits \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=endpoint,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
    AttributeName=endpoint,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST

# Enable TTL for automatic cleanup
aws dynamodb update-time-to-live \
  --table-name api_rate_limits \
  --time-to-live-specification \
    Enabled=true,AttributeName=ttl
```

#### Session Management Table (Optional - Future Phase)

```bash
aws dynamodb create-table \
  --table-name user_sessions \
  --attribute-definitions \
    AttributeName=session_id,AttributeType=S \
    AttributeName=user_id,AttributeType=S \
  --key-schema \
    AttributeName=session_id,KeyType=HASH \
  --global-secondary-indexes \
    IndexName=user_id-index,\
    KeySchema=[{AttributeName=user_id,KeyType=HASH}],\
    Projection={ProjectionType=ALL} \
  --billing-mode PAY_PER_REQUEST
```

### Step 4: Update Lambda Environment Variables

For both `api-gateway` and `upload-api-gateway` Lambda functions:

```bash
aws lambda update-function-configuration \
  --function-name opus-api-gateway \
  --environment Variables="{
    ALLOWED_ORIGINS=https://your-frontend-domain.com,
    RATE_LIMIT_TABLE=api_rate_limits,
    FIREBASE_PROJECT_ID=reframeai-87b24
  }"

aws lambda update-function-configuration \
  --function-name opus-upload-api-gateway \
  --environment Variables="{
    ALLOWED_ORIGINS=https://your-frontend-domain.com,
    RATE_LIMIT_TABLE=api_rate_limits,
    FIREBASE_PROJECT_ID=reframeai-87b24
  }"
```

### Step 5: Deploy Updated Lambda Functions

```bash
cd opus-clip-cloud/src/api-gateway
zip -r api-gateway.zip lambda_function.py

aws lambda update-function-code \
  --function-name opus-api-gateway \
  --zip-file fileb://api-gateway.zip

cd ../upload-api-gateway
zip -r upload-api-gateway.zip lambda_function.py

aws lambda update-function-code \
  --function-name opus-upload-api-gateway \
  --zip-file fileb://upload-api-gateway.zip
```

### Step 6: Deploy Shared Libraries as Lambda Layer (Recommended)

```bash
cd opus-clip-cloud/src/shared

mkdir -p python/lib/python3.11/site-packages
cp rate_limiter.py python/lib/python3.11/site-packages/
cp security_logger.py python/lib/python3.11/site-packages/

zip -r shared-layer.zip python

aws lambda publish-layer-version \
  --layer-name opus-shared-security \
  --zip-file fileb://shared-layer.zip \
  --compatible-runtimes python3.11

# Attach layer to Lambda functions
aws lambda update-function-configuration \
  --function-name opus-api-gateway \
  --layers arn:aws:lambda:us-east-1:YOUR_ACCOUNT:layer:opus-shared-security:1

aws lambda update-function-configuration \
  --function-name opus-upload-api-gateway \
  --layers arn:aws:lambda:us-east-1:YOUR_ACCOUNT:layer:opus-shared-security:1
```

### Step 7: Update Frontend Environment Variables

**File**: `reframe-ai/.env`

```bash
VITE_API_ENDPOINT=https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod
VITE_FIREBASE_API_KEY=your-firebase-api-key
VITE_FIREBASE_AUTH_DOMAIN=reframeai-87b24.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=reframeai-87b24
# ... other Firebase config
```

### Step 8: Deploy Frontend

```bash
cd reframe-ai

# Install dependencies (if not already done)
npm install

# Build for production
npm run build

# Deploy to your hosting service (Netlify, Vercel, etc.)
# Example for Netlify:
netlify deploy --prod
```

### Step 9: Deploy Firestore Security Rules

```bash
cd reframe-ai

# Deploy rules to Firebase
firebase deploy --only firestore:rules
```

### Step 10: Create CloudWatch Alarms (Recommended)

```bash
# Alarm for high authentication failure rate
aws cloudwatch put-metric-alarm \
  --alarm-name high-auth-failures \
  --alarm-description "Alert when auth failures exceed threshold" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=opus-authorizer

# Alarm for rate limit violations
# (Custom metric - requires additional implementation)
```

---

## 🧪 Testing

### Test Lambda Authorizer

```bash
# Get a valid Firebase token from your frontend
# (Check browser DevTools → Network → Any API request → Authorization header)

# Test authorizer with valid token
aws lambda invoke \
  --function-name opus-authorizer \
  --payload '{
    "type": "TOKEN",
    "authorizationToken": "Bearer YOUR_FIREBASE_TOKEN",
    "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/prod/POST/process"
  }' \
  response.json

cat response.json
```

### Test API Endpoints

```bash
# Test YouTube processing (should succeed with valid token)
curl -X POST https://YOUR_API.execute-api.us-east-1.amazonaws.com/prod/process \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "project_name": "Test Project"
  }'

# Test without token (should return 401)
curl -X POST https://YOUR_API.execute-api.us-east-1.amazonaws.com/prod/process \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  }'

# Test rate limiting (make 11 requests quickly - 11th should fail)
for i in {1..11}; do
  curl -X POST https://YOUR_API.execute-api.us-east-1.amazonaws.com/prod/process \
    -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"youtube_url": "https://www.youtube.com/watch?v=test"}'
  echo "Request $i"
done
```

### Test Frontend

1. Open frontend in browser
2. Sign in with Firebase
3. Try to process a video
4. Check browser DevTools → Network → See Authorization header with Bearer token
5. Verify successful API call
6. Check CloudWatch logs for security events

---

## 📊 Monitoring

### CloudWatch Insights Queries

#### Find all rate limit violations:
```
fields @timestamp, user_id, endpoint
| filter event_type = "RATE_LIMIT_EXCEEDED"
| sort @timestamp desc
| limit 100
```

#### Find authentication failures:
```
fields @timestamp, reason, ip_address
| filter event_type = "AUTH_FAILED"
| stats count() by reason
```

#### Find suspicious activity:
```
fields @timestamp, user_id, activity_type, details
| filter event_type = "SUSPICIOUS_ACTIVITY"
| sort @timestamp desc
```

#### API request volume by user:
```
fields @timestamp, user_id, endpoint
| filter event_type = "API_REQUEST"
| stats count() by user_id
| sort count desc
```

---

## 🔒 Security Best Practices

### Implemented ✅

1. **JWT Verification**: All API requests verified with Firebase tokens
2. **Rate Limiting**: Per-user, per-endpoint limits prevent abuse
3. **Security Logging**: All security events logged to CloudWatch
4. **CORS Lockdown**: Configurable allowed origins
5. **Firestore Rules**: Proper access control on database
6. **Authorization Checks**: Users can only access their own resources
7. **Automatic Token Refresh**: Frontend handles expired tokens

### Recommended Next Steps 🚧

1. **CAPTCHA Integration** (Phase 4):
   - Add reCAPTCHA v3 to login/signup
   - Prevent bot attacks

2. **Session Management** (Phase 3):
   - Track active sessions per user
   - Allow users to view and revoke sessions
   - Add device fingerprinting

3. **IP Whitelisting** (Optional):
   - For admin operations
   - Additional security layer

4. **Encryption at Rest**:
   - Encrypt sensitive data in DynamoDB
   - Use AWS KMS for key management

5. **Regular Security Audits**:
   - Penetration testing
   - Code security scanning
   - Dependency vulnerability checks

---

## 🐛 Troubleshooting

### Error: "Unauthorized - Invalid or missing authentication token"

**Cause**: JWT token not sent or invalid

**Solution**:
1. Check if user is logged in to Firebase
2. Verify token is being sent in Authorization header
3. Check token hasn't expired (Firebase tokens expire after 1 hour)
4. Verify FIREBASE_PROJECT_ID matches in authorizer and Firebase config

### Error: "Rate limit exceeded"

**Cause**: User exceeded configured rate limit

**Solution**:
1. Check rate limits in `rate_limiter.py`
2. Adjust limits if needed for your use case
3. Reset user's rate limit: Use `reset_rate_limit(user_id, endpoint)`
4. For testing, temporarily increase limits

### Error: "Forbidden - You can only access your own videos"

**Cause**: User trying to access another user's resources

**Solution**:
1. Verify user is requesting their own resources
2. Check if user_id in URL matches authenticated user
3. This is expected behavior for security

### Lambda Authorizer Timing Out

**Cause**: Slow Firebase public key fetch or network issues

**Solution**:
1. Increase authorizer timeout to 15 seconds
2. Check Lambda VPC configuration (if in VPC)
3. Verify internet connectivity from Lambda
4. Monitor authorizer CloudWatch logs

### CORS Errors in Browser

**Cause**: CORS headers not configured correctly

**Solution**:
1. Set `ALLOWED_ORIGINS` environment variable in Lambda
2. Ensure API Gateway has CORS enabled
3. Check if OPTIONS preflight requests succeed
4. Verify `Access-Control-Allow-Credentials: true` in response

---

## 📈 Cost Estimates

Based on 10,000 monthly active users:

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| Lambda Authorizer | 500K invocations | $0.10 |
| DynamoDB (rate limits) | 1M reads, 500K writes | $1.50 |
| CloudWatch Logs | 10GB/month | $5.00 |
| API Gateway | 1M requests | $3.50 |
| Lambda Functions | 1M requests | $0.20 |
| **Total** | | **~$10.30/month** |

---

## 🎯 Summary

### Security Improvements

**Before**:
- ❌ Anyone could impersonate users by changing `user_id` in request body
- ❌ No rate limiting
- ❌ No security logging
- ❌ Wildcard CORS (`*`)
- ❌ Overly permissive Firestore rules

**After**:
- ✅ Every request verified with Firebase JWT
- ✅ Per-user rate limiting on all endpoints
- ✅ Comprehensive security logging to CloudWatch
- ✅ Configurable CORS origins
- ✅ Proper Firestore access control
- ✅ Users can only access their own resources
- ✅ Automatic token refresh
- ✅ Centralized API client

### Risk Reduction

This implementation **eliminates the critical authentication bypass vulnerability** where any user could impersonate any other user. All requests are now properly authenticated, authorized, rate-limited, and logged.

---

## 📚 Additional Resources

- [AWS Lambda Authorizers Documentation](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html)
- [Firebase JWT Verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [CloudWatch Logs Insights Query Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)

---

## 🆘 Support

For issues or questions:
1. Check CloudWatch logs for detailed error messages
2. Review this guide's troubleshooting section
3. Check the main plan file: `~/.claude/plans/gleaming-noodling-moonbeam.md`
