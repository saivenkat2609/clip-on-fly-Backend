# Fix: Step Functions Payload Handling

## What Happened

The Lambda was receiving `undefined` for `session_id` and `youtube_url` because Step Functions wraps the payload differently than direct Lambda invocations.

## The Issue

When you invoke Lambda directly:
```json
{
  "session_id": "123",
  "youtube_url": "https://..."
}
```

When Step Functions invokes with `lambda:invoke`:
```json
{
  "Payload": {
    "session_id": "123",
    "youtube_url": "https://..."
  }
}
```

## The Fix

I've updated `index.js` to handle both formats automatically:

```javascript
// Handle Step Functions invocation (event might be wrapped)
let payload = event;

// If invoked from Step Functions with lambda:invoke, payload is nested
if (event.Payload && typeof event.Payload === 'string') {
    payload = JSON.parse(event.Payload);
} else if (event.Payload && typeof event.Payload === 'object') {
    payload = event.Payload;
}

const { session_id, youtube_url } = payload;

// Validate required parameters
if (!session_id || !youtube_url) {
    throw new Error(`Missing required parameters: session_id=${session_id}, youtube_url=${youtube_url}`);
}
```

Now the Lambda works with:
- ✅ Direct invocation (testing, API Gateway, etc.)
- ✅ Step Functions with `lambda:invoke`
- ✅ Manual test events

## Redeploy Instructions

### 1. Recreate Deployment Package

```bash
cd lambda-functions/opus-node-download
deploy.bat
```

### 2. Upload to Lambda

**Option A: AWS Console**
- Go to your Lambda function
- Upload the new `lambda-deployment.zip`

**Option B: AWS CLI**
```bash
aws lambda update-function-code \
  --function-name opus-clip-download-node \
  --zip-file fileb://lambda-deployment.zip
```

### 3. Test Again

Use the same test event in Lambda console:
```json
{
  "session_id": "test-123",
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

Or test from Step Functions directly.

## What's Different

**Before:**
- Only worked with direct payload format
- Would crash with `undefined` in Step Functions

**After:**
- Automatically detects payload format
- Works with both direct and Step Functions invocation
- Better error messages showing the actual event received

## Verify It Works

After redeploying, check the logs. You should see:

```
[Download] ===== NEW INVOCATION =====
[Download] Session: test-123
[Download] URL: https://www.youtube.com/watch?v=jNQXAC9IVRw
[Download] Lambda Request ID: abc123...
[Download] Quality Mode: balanced
```

Instead of:

```
[Download] Session: undefined
[Download] URL: undefined
```

That's it! The Lambda should now work properly in Step Functions. 🚀
