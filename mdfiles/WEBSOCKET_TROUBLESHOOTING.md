# WebSocket Real-Time Updates Troubleshooting Guide

This guide helps you diagnose and fix WebSocket real-time progress update issues.

## Quick Diagnosis

### 1. Check Frontend Console Logs

**✅ Good Signs:**
```
[WebSocket] ✅ Connected successfully!
[WebSocket] 📤 Sending subscribe message for session: xxx
[WebSocket] 📥 Raw message received: {event: 'subscribed', ...}
[WebSocket] 📥 Raw message received: {event: 'processing_progress', status: 'downloading', ...}
```

**❌ Bad Signs:**
```
[WebSocket] Closed (code: 1006)
[WebSocket] Error: Event {...}
WebSocket status: pending → Stage index: -1  (stuck forever)
```

### 2. Check Lambda Logs (AWS CloudWatch)

#### WebSocket Handler Lambda Logs
**Location:** CloudWatch → `/aws/lambda/websocket-handler`

**✅ Should see:**
```
✅ Subscribed connection ABC123 to session xxx for user web-user
✅ Sent subscription confirmation to ABC123
```

**❌ Problem if you see:**
```
Error in subscribe: ...
Error saving WebSocket connection: ...
```

#### Download Lambda Logs
**Location:** CloudWatch → `/aws/lambda/opus-node-download`

**✅ Should see:**
```
📡 Looking for WebSocket connections for session: xxx
📊 Found 1 connection(s) for session xxx
📤 Sending WebSocket message:
   Event: processing_progress
   Status: downloading
   📡 Sending to connection: ABC123
      ✅ Success
```

**❌ Problem if you see:**
```
❌ Error: WEBSOCKET_API_ENDPOINT not configured
⚠️ No WebSocket connections found for session xxx
```

---

## Common Issues & Solutions

### Issue 1: WEBSOCKET_API_ENDPOINT Not Configured

**Symptom:**
Lambda logs show:
```
❌ Error: WEBSOCKET_API_ENDPOINT not configured for session xxx
```

**Solution:**

1. Get your WebSocket API endpoint:
   ```bash
   AWS Console → API Gateway → Your WebSocket API → Stages → prod
   ```
   Copy the **Invoke URL** (e.g., `wss://abc123.execute-api.us-east-1.amazonaws.com/prod`)

2. Convert to Management API format:
   ```
   Change: wss://abc123.execute-api.us-east-1.amazonaws.com/prod
   To:     https://abc123.execute-api.us-east-1.amazonaws.com/prod
   ```

3. Add to ALL Lambda functions:
   - `opus-node-download`
   - `opus-transcribe` or `opus-transcribe-apis`
   - `opus-detect-clips`
   - `opus-process-clip`
   - `opus-finalize`

   **Via AWS Console:**
   ```
   Lambda → Configuration → Environment variables → Edit
   Key: WEBSOCKET_API_ENDPOINT
   Value: https://abc123.execute-api.us-east-1.amazonaws.com/prod
   ```

   **Via AWS CLI:**
   ```bash
   aws lambda update-function-configuration \
     --function-name opus-node-download \
     --environment "Variables={WEBSOCKET_API_ENDPOINT=https://abc123.execute-api.us-east-1.amazonaws.com/prod,...}"
   ```

---

### Issue 2: No WebSocket Connections Found

**Symptom:**
Lambda logs show:
```
⚠️ No WebSocket connections found for session xxx
   This could mean:
   1. Client hasn't subscribed yet
   2. Connection was closed
   3. DynamoDB GSI 'session_id-index' not configured
```

**Solution A: DynamoDB Table Missing**

Check if table exists:
```bash
aws dynamodb describe-table --table-name prod-websocket-connections --region us-east-1
```

If error "Table not found", create it:
```bash
# Windows PowerShell
cd opus-clip-cloud\infrastructure
.\create-dynamodb-tables.ps1

# Linux/Mac
cd opus-clip-cloud/infrastructure
chmod +x create-dynamodb-tables.sh
./create-dynamodb-tables.sh
```

**Solution B: GSI (Global Secondary Index) Missing**

1. Open AWS Console → DynamoDB → Tables → `prod-websocket-connections`
2. Go to **Indexes** tab
3. Verify `session_id-index` exists with:
   - Partition key: `session_id` (String)
   - Projection type: ALL

If missing, create it:
```bash
aws dynamodb update-table \
  --table-name prod-websocket-connections \
  --attribute-definitions AttributeName=session_id,AttributeType=S \
  --global-secondary-index-updates \
    '[{
      "Create": {
        "IndexName": "session_id-index",
        "KeySchema": [{"AttributeName": "session_id", "KeyType": "HASH"}],
        "Projection": {"ProjectionType": "ALL"},
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
      }
    }]' \
  --region us-east-1
```

**Solution C: Timing Issue (Lambda starts before subscription)**

This happens when video processing starts **before** the WebSocket subscribes.

**Fix:** Add retry logic (already implemented in the code - check if Lambda has latest code deployed)

---

### Issue 3: Connection Closes Immediately

**Symptom:**
```
[WebSocket] Connected successfully!
[WebSocket] Closed (code: 1006, reason: )
```

**Solution:**

1. **Check WebSocket Lambda has permissions:**
   ```bash
   AWS Console → Lambda → websocket-handler → Configuration → Permissions
   ```
   Should have:
   - `dynamodb:PutItem` (for saving connections)
   - `dynamodb:Query` (for finding connections)
   - `dynamodb:DeleteItem` (for cleanup)
   - `execute-api:ManageConnections` (for sending messages)

2. **Check API Gateway routes:**
   ```bash
   AWS Console → API Gateway → Your WebSocket API → Routes
   ```
   Should have:
   - `$connect` → websocket-handler Lambda
   - `$disconnect` → websocket-handler Lambda
   - `subscribe` → websocket-handler Lambda
   - `ping` → websocket-handler Lambda

---

### Issue 4: Frontend Env Variable Wrong

**Symptom:**
```
[createVideoWebSocket] ⚠️ VITE_WEBSOCKET_URL not set! Using default URL.
```

**Solution:**

1. Create/edit `reframe-ai/.env`:
   ```bash
   VITE_WEBSOCKET_URL=wss://abc123.execute-api.us-east-1.amazonaws.com/prod
   ```

2. Restart dev server:
   ```bash
   npm run dev
   ```

---

## Manual Testing

### Test WebSocket Subscription

Use `wscat` to manually test:

```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c wss://abc123.execute-api.us-east-1.amazonaws.com/prod

# After connected, send subscribe message
{"action": "subscribe", "session_id": "test-123", "user_id": "test-user"}

# Should receive
{"event":"subscribed","session_id":"test-123","message":"Successfully subscribed..."}
```

### Test DynamoDB Connection Saving

Check if subscription was saved:
```bash
aws dynamodb query \
  --table-name prod-websocket-connections \
  --index-name session_id-index \
  --key-condition-expression "session_id = :sid" \
  --expression-attribute-values '{":sid":{"S":"test-123"}}' \
  --region us-east-1
```

Should return the connection item.

---

## Complete Checklist

Before processing a video, verify:

- [ ] ✅ DynamoDB table `prod-websocket-connections` exists
- [ ] ✅ DynamoDB table has GSI `session_id-index`
- [ ] ✅ WebSocket Lambda has DynamoDB permissions
- [ ] ✅ All processing Lambdas have `WEBSOCKET_API_ENDPOINT` env var set
- [ ] ✅ `WEBSOCKET_API_ENDPOINT` uses `https://` NOT `wss://`
- [ ] ✅ Frontend has correct `VITE_WEBSOCKET_URL` (with `wss://`)
- [ ] ✅ Latest Lambda code deployed with WebSocket notification calls
- [ ] ✅ API Gateway WebSocket routes configured

---

## Debug Commands

### Check Lambda Environment Variables
```bash
# Check download Lambda
aws lambda get-function-configuration \
  --function-name opus-node-download \
  --query 'Environment.Variables.WEBSOCKET_API_ENDPOINT' \
  --region us-east-1

# Check all Lambdas at once (PowerShell)
@('opus-node-download','opus-transcribe','opus-detect-clips','opus-process-clip','opus-finalize') | ForEach-Object {
  Write-Host "Checking $_..." -ForegroundColor Yellow
  aws lambda get-function-configuration --function-name $_ --query 'Environment.Variables.WEBSOCKET_API_ENDPOINT' --region us-east-1
}
```

### View Real-Time Lambda Logs
```bash
# Watch download Lambda logs
aws logs tail /aws/lambda/opus-node-download --follow --region us-east-1

# Watch WebSocket handler logs
aws logs tail /aws/lambda/websocket-handler --follow --region us-east-1
```

### Check DynamoDB Tables
```bash
# List all tables
aws dynamodb list-tables --region us-east-1

# Describe websocket-connections table
aws dynamodb describe-table \
  --table-name prod-websocket-connections \
  --region us-east-1 \
  | grep -A 5 "GlobalSecondaryIndexes"

# Count active connections
aws dynamodb scan \
  --table-name prod-websocket-connections \
  --select "COUNT" \
  --region us-east-1
```

---

## Success Indicators

When everything works correctly, you should see:

### Frontend Console:
```
[WebSocket] ✅ Connected successfully!
[WebSocket] 📤 Sending subscribe message for session: caa1c737...
[WebSocket] 📥 Raw message received: {event: 'subscribed', ...}
[WebSocket] 📥 Raw message received: {event: 'processing_progress', status: 'downloading', progress: 5}
[useVideoStatus] ✏️ Updating status: downloading
[useVideoStatus] ✏️ Updating progress: 5
[ProjectDetails] 🔄 WebSocket State Changed: {wsStatus: 'downloading', wsProgress: 5, isConnected: true}
```

### Lambda Logs:
```
[Download] Lambda Request ID: abc-123
✅ Subscribed connection XYZ to session caa1c737... for user web-user
✅ Sent subscription confirmation to XYZ
📡 Looking for WebSocket connections for session: caa1c737...
📊 Found 1 connection(s) for session caa1c737...
📤 Sending WebSocket message:
   Event: processing_progress
   Status: downloading
   Data: {status: 'downloading', progress: 5}
   📡 Sending to connection: XYZ
      ✅ Success
Notified 1/1 clients for session caa1c737...
```

### UI Display:
- ✅ "Downloading" stage highlighted with animated spinner
- ✅ Progress bar showing 5% → 20% → 25% (transcribing) → ...
- ✅ Green "Connected" dot visible
- ✅ Smooth transitions between stages

---

## Still Not Working?

1. **Export full logs and share:**
   ```bash
   # Lambda logs
   aws logs tail /aws/lambda/opus-node-download --since 5m > download-logs.txt
   aws logs tail /aws/lambda/websocket-handler --since 5m > websocket-logs.txt

   # DynamoDB table details
   aws dynamodb describe-table --table-name prod-websocket-connections > table-details.txt
   ```

2. **Check Lambda IAM permissions:**
   ```bash
   aws lambda get-policy --function-name websocket-handler
   ```

3. **Verify API Gateway deployment:**
   ```bash
   aws apigatewayv2 get-apis | grep -A 10 "websocket"
   ```

---

## Contact & Support

If you've followed all steps and it's still not working:
1. Share the Lambda logs (download-logs.txt, websocket-logs.txt)
2. Share DynamoDB table structure (table-details.txt)
3. Share exact error messages from browser console
4. Share session ID that failed

This will help diagnose the exact issue.
