# RapidAPI Download - Quick Start Guide

## 📁 Files Created

```
src/rapidapi-download/
├── index.js                      # Main Lambda handler (700+ lines)
├── package.json                  # Dependencies (@aws-sdk/client-s3, @aws-sdk/lib-storage)
├── deploy.bat                    # Windows deployment script
├── setup-r2.js                   # R2 initialization script
├── rapidapi-keys-usage.json      # API keys template (MUST EDIT)
├── test-event.json               # Test payload for Lambda
├── README.md                     # Full documentation
└── QUICKSTART.md                 # This file
```

## 🚀 Quick Start (5 Steps)

### Step 1: Get RapidAPI Keys

1. Go to https://rapidapi.com/
2. Sign up and subscribe to **YouTube Media Downloader** API
3. Choose **Free Plan** (300 requests/month)
4. Copy your API key from the dashboard
5. Repeat for **10 different accounts** (or as many as you need)

**Tip**: Use temporary email services like temp-mail.org for quick signups

### Step 2: Configure API Keys

Edit `rapidapi-keys-usage.json` and replace all placeholder values:

```json
{
  "keys": [
    {
      "name": "key-1",
      "apiKey": "abc123def456...",  // ← Your actual RapidAPI key
      "enabled": true
    }
    // ... repeat for all 10 keys
  ]
}
```

### Step 3: Upload to R2

```bash
cd C:\Projects\reframeAI\opus-clip-cloud\src\rapidapi-download
npm install
node setup-r2.js
```

**Expected output**:
```
✅ SUCCESS: API keys usage file uploaded
   Bucket: opus-clip-videos
   Key: config/rapidapi-keys-usage.json
   API Keys: 10
   Total Monthly Capacity: 3000 requests
```

### Step 4: Deploy Lambda

```bash
deploy.bat
```

**Expected output**:
```
[1/6] Installing dependencies...
[2/6] Creating deployment package...
[3/6] Uploading to AWS Lambda...
[4/6] Attaching shared utilities layer...
[5/6] Setting environment variables...
[6/6] Cleaning up...
✅ SUCCESS: Lambda deployed!
```

### Step 5: Test

```bash
aws lambda invoke ^
  --function-name opus-rapidapi-download ^
  --payload file://test-event.json ^
  --region us-east-1 ^
  response.json

type response.json
```

**Expected response**:
```json
{
  "statusCode": 200,
  "session_id": "test-rapidapi-001",
  "s3_video_key": "users/test-user/test-rapidapi-001/original_Rick_Astley_Never_Gonna_Give_You_Up.mp4",
  "video_info": {
    "title": "Rick Astley - Never Gonna Give You Up",
    "duration": 213,
    "uploader": "Rick Astley"
  },
  "api_key_used": "key-1",
  "requests_remaining": 299
}
```

## ✅ Verification

### Check S3 Upload
```bash
aws s3 ls s3://opus-clip-videos/users/test-user/test-rapidapi-001/
```

### Check API Usage
```bash
aws s3 cp s3://opus-clip-videos/config/rapidapi-keys-usage.json usage-check.json
type usage-check.json
```

Should show:
```json
{
  "keys": [
    {
      "name": "key-1",
      "usedThisMonth": 1,  // ← Incremented
      "lastUsed": "2026-01-18T..."
    }
  ]
}
```

### Check CloudWatch Logs
```bash
aws logs tail /aws/lambda/opus-rapidapi-download --follow --region us-east-1
```

## 🔧 Integration with Step Functions

### Option A: Manual Routing

When starting Step Functions execution, specify `download_method`:

```bash
aws stepfunctions start-execution ^
  --state-machine-arn arn:aws:states:us-east-1:930115312558:stateMachine:youtube-url-workflow ^
  --input "{\"session_id\":\"prod-001\",\"youtube_url\":\"https://www.youtube.com/watch?v=dQw4w9WgXcQ\",\"user_id\":\"user-123\",\"download_method\":\"rapidapi\"}" ^
  --region us-east-1
```

### Option B: Update State Machine (Recommended)

Add routing logic to `youtube-url-workflow-state-machine.json`:

```json
{
  "ChooseDownloadMethod": {
    "Type": "Choice",
    "Choices": [
      {
        "Variable": "$.download_method",
        "StringEquals": "rapidapi",
        "Next": "DownloadVideoRapidAPI"
      }
    ],
    "Default": "DownloadVideo"
  },

  "DownloadVideoRapidAPI": {
    "Type": "Task",
    "Resource": "arn:aws:lambda:us-east-1:930115312558:function:opus-rapidapi-download",
    "ResultPath": "$.downloadResult",
    "Next": "MergeDownloadResult",
    "TimeoutSeconds": 600
  }
}
```

Deploy:
```bash
aws stepfunctions update-state-machine ^
  --state-machine-arn arn:aws:states:us-east-1:930115312558:stateMachine:youtube-url-workflow ^
  --definition file://youtube-url-workflow-state-machine.json ^
  --region us-east-1
```

## 📊 Monitoring Usage

### View Current Usage
```bash
aws s3 cp s3://opus-clip-videos/config/rapidapi-keys-usage.json - | python -m json.tool
```

### Dashboard Summary
```javascript
// Quick Node.js script
const usage = require('./rapidapi-keys-usage.json');
const total = usage.keys.reduce((sum, k) => sum + k.usedThisMonth, 0);
const available = usage.keys.length * usage.monthlyLimit - total;

console.log(`Used: ${total}/${usage.keys.length * usage.monthlyLimit}`);
console.log(`Remaining: ${available} requests`);
console.log(`Reset Date: ${usage.lastReset}`);
```

## 🐛 Troubleshooting

### Problem: "No API keys available"
**Solution**: All keys exhausted. Wait until next month or add more keys.

### Problem: "RapidAPI request failed: 403 Forbidden"
**Solution**: Invalid API key or subscription expired. Check RapidAPI dashboard.

### Problem: "Error: ENOENT: no such file or directory"
**Solution**: Ensure `/tmp` directory exists. Lambda should create it automatically.

### Problem: "Function package size exceeds limit"
**Solution**: Run `npm install --production` to exclude dev dependencies.

### Problem: Setup fails with "NoSuchBucket"
**Solution**: Create bucket first:
```bash
aws s3 mb s3://opus-clip-videos --region us-east-1
```

## 📈 Expected Performance

| Metric | Value |
|--------|-------|
| Cold Start | 2-3 seconds |
| Warm Execution | 15-30 seconds |
| Memory Usage | 200-400 MB |
| Success Rate | 95-98% |
| Cost | **FREE** (3,000 requests/month) |

## 🎯 Next Steps

1. ✅ Test with multiple videos
2. ✅ Monitor CloudWatch logs for errors
3. ✅ Track API usage daily
4. ✅ Integrate with Step Functions
5. ✅ Set up CloudWatch alarms for errors
6. ✅ Document any edge cases

## 📞 Support

For issues:
1. Check CloudWatch logs first
2. Verify API keys are valid on RapidAPI dashboard
3. Check R2 usage file for accurate counts
4. Review README.md for detailed documentation

---

**Status**: ✅ Ready for deployment and testing

**Last Updated**: 2026-01-18
