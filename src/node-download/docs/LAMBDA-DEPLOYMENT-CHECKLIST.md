# Lambda Deployment Checklist ✅

Your code is ready for Lambda! Follow this checklist to deploy:

## ✅ Code Status
- ✅ Working locally
- ✅ All dependencies installed
- ✅ Cookie authentication working
- ✅ S3/R2 uploads working

---

## 📦 Step 1: Create Deployment Package

```bash
cd lambda-functions/opus-node-download

# Run the deployment script
deploy.bat
```

This creates `lambda-deployment.zip` (should be 30-50MB)

---

## ☁️ Step 2: Lambda Configuration

### Create/Update Lambda Function

**Basic Settings:**
```
Function name: opus-clip-download-node
Runtime: Node.js 20.x
Architecture: x86_64 (or arm64)
Handler: index.handler
```

**Timeout & Memory:**
```
Timeout: 300 seconds (5 minutes)
Memory: 1024 MB minimum (2048 MB recommended)
```

**Environment Variables:**
```
BUCKET_NAME=opus-clip-videos
QUALITY_MODE=balanced
AWS_REGION=us-east-1

# Your R2 credentials
R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
R2_ACCESS_KEY=your-r2-access-key
R2_SECRET_KEY=your-r2-secret-key

# IMPORTANT: Cookie file location
COOKIES_S3_KEY=youtube-cookies.txt
```

---

## 🔐 Step 3: IAM Role Permissions

Your Lambda execution role needs these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:HeadObject"
            ],
            "Resource": "arn:aws:s3:::opus-clip-videos/*"
        }
    ]
}
```

**Note:** For R2, the S3 permissions still work since R2 is S3-compatible.

---

## 📤 Step 4: Upload Code

### Option A: AWS Console
1. Go to Lambda function
2. Click "Upload from" → ".zip file"
3. Select `lambda-deployment.zip`
4. Click "Save"
5. Wait for upload to complete

### Option B: AWS CLI
```bash
aws lambda update-function-code \
  --function-name opus-clip-download-node \
  --zip-file fileb://lambda-deployment.zip \
  --region us-east-1
```

---

## 🧪 Step 5: Test in Lambda

Create a test event:

```json
{
  "session_id": "test-lambda-123",
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

Click "Test" and check:
- ✅ Status code 200
- ✅ Video downloads successfully
- ✅ File uploads to R2
- ✅ Execution time < 60 seconds for short video

---

## 🔄 Step 6: Update Step Function (Optional)

If you're using AWS Step Functions, update the download state:

```json
"DownloadVideo": {
    "Type": "Task",
    "Resource": "arn:aws:states:::lambda:invoke",
    "Parameters": {
        "FunctionName": "opus-clip-download-node",
        "Payload": {
            "session_id.$": "$.session_id",
            "youtube_url.$": "$.youtube_url"
        }
    },
    "ResultPath": "$.download_result",
    "ResultSelector": {
        "session_id.$": "$.Payload.session_id",
        "s3_video_key.$": "$.Payload.s3_video_key",
        "video_info.$": "$.Payload.video_info"
    },
    "Next": "TranscribeVideo"
}
```

---

## 🎯 What Will Work Differently in Lambda vs Local

### ✅ Works the Same:
- Cookie loading from R2
- Video downloading with ytdl-core
- S3/R2 uploads
- Error handling

### ⚠️ Different in Lambda:
- **Credentials**: Lambda uses execution role instead of local AWS credentials
- **Logs**: Output goes to CloudWatch Logs instead of console
- **Timeout**: Lambda has max 15 minute timeout (configured to 5 min)
- **/tmp space**: Limited to 512 MB (expandable to 10 GB if needed)

### 🔧 No Code Changes Needed!
The code automatically detects it's running in Lambda and adjusts.

---

## 📊 Expected Performance in Lambda

For a typical 5-minute 480p video:

| Step | Time |
|------|------|
| Cookie load | 0.5s |
| Video info fetch | 2-3s |
| Download | 15-30s |
| Upload to R2 | 5-10s |
| **Total** | **25-45s** |

Cold start adds ~2-3s on first invocation.

---

## 🐛 Troubleshooting

### "Cannot find module '@distube/ytdl-core'"
**Fix:** Make sure `node_modules` folder is in the zip file.

```bash
# Verify zip contents
unzip -l lambda-deployment.zip | grep node_modules
```

### "Task timed out after 3.00 seconds"
**Fix:** Increase Lambda timeout to 300 seconds (5 minutes).

### "ENOSPC: no space left on device"
**Fix:** Increase Lambda memory to 2048 MB (gives more /tmp space).

### Still getting 403 errors in Lambda
**Fixes:**
1. Verify `COOKIES_S3_KEY` environment variable is set
2. Verify cookies file exists in R2 bucket
3. Check Lambda has S3 GetObject permission
4. Try refreshing cookies (re-export from browser)

### "Unable to import module 'index'"
**Fixes:**
1. Verify Handler is `index.handler`
2. Verify Runtime is Node.js 18.x or 20.x
3. Check zip file has index.js at root level

---

## ✨ You're Ready!

If it's working locally with your R2 credentials and cookies, it will work in Lambda with the same configuration.

**Next Steps:**
1. ✅ Run `deploy.bat` to create zip
2. ✅ Upload to Lambda
3. ✅ Test with a short video first
4. ✅ Monitor CloudWatch logs
5. ✅ Update Step Function if needed

Good luck! 🚀
