# Quick Start Guide - Node.js Download Lambda

## 1. Install Dependencies

```bash
cd lambda-functions/opus-node-download
npm install
```

## 2. Create Deployment Package

### Windows:
```bash
deploy.bat
```

### Manual (any OS):
```bash
# Install dependencies
npm install

# Create zip
# Windows PowerShell:
Compress-Archive -Path index.js, package.json, node_modules -DestinationPath lambda-deployment.zip -Force

# Linux/Mac:
zip -r lambda-deployment.zip index.js package.json node_modules
```

## 3. Create Lambda Function (AWS Console)

1. Go to AWS Lambda Console
2. Click "Create function"
3. Choose "Author from scratch"
4. Function name: `opus-clip-download-node`
5. Runtime: **Node.js 20.x**
6. Architecture: x86_64
7. Click "Create function"

## 4. Configure Lambda

### Basic Settings
- Handler: `index.handler`
- Memory: **1024 MB** (minimum)
- Timeout: **5 minutes** (300 seconds)

### Environment Variables

Add these (copy from your existing Python Lambda):

```
BUCKET_NAME=opus-clip-videos
QUALITY_MODE=balanced
AWS_REGION=us-east-1
```

**If using Cloudflare R2:**
```
R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
R2_ACCESS_KEY=your-r2-access-key
R2_SECRET_KEY=your-r2-secret-key
```

**Optional - For better reliability (recommended):**
```
COOKIES_S3_KEY=youtube-cookies.txt
```

> **Note**: If you're still getting 403 errors, you MUST upload YouTube cookies to your bucket.
> See the README for instructions on exporting cookies from your browser.

**If using AWS S3:**
```
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### IAM Role Permissions

Your Lambda execution role needs:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:HeadObject"
            ],
            "Resource": "arn:aws:s3:::opus-clip-videos/*"
        }
    ]
}
```

## 5. Upload Code

### Option A: Console Upload
1. In Lambda function, go to "Code" tab
2. Click "Upload from" → ".zip file"
3. Select `lambda-deployment.zip`
4. Click "Save"

### Option B: AWS CLI
```bash
aws lambda update-function-code \
  --function-name opus-clip-download-node \
  --zip-file fileb://lambda-deployment.zip
```

## 6. Test the Function

Create a test event in Lambda console:

```json
{
  "session_id": "test-123",
  "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

Click "Test" and check the logs.

Expected output:
```json
{
  "statusCode": 200,
  "session_id": "test-123",
  "s3_video_key": "test-123/original_video.mp4",
  "video_info": {
    "title": "Me at the zoo",
    "duration": 18,
    "description": "...",
    "uploader": "jawed",
    "view_count": 280000000,
    "thumbnail_url": "..."
  }
}
```

## 7. Update Step Function

Update your Step Function state machine to use the new Lambda:

Find the download step:
```json
"DownloadVideo": {
    "Type": "Task",
    "Resource": "arn:aws:states:::lambda:invoke",
    "Parameters": {
        "FunctionName": "opus-clip-download-node",  // <-- Change this
        "Payload": {
            "session_id.$": "$.session_id",
            "youtube_url.$": "$.youtube_url"
        }
    },
    ...
}
```

## 8. Common Issues

### "Cannot find module '@distube/ytdl-core'"
- Make sure you ran `npm install` before creating the zip
- Ensure `node_modules` folder is included in the zip

### "Task timed out after 3.00 seconds"
- Increase Lambda timeout to 300 seconds (5 minutes)

### "ENOSPC: no space left on device"
- Increase Lambda memory to 2048 MB (gives more /tmp space)

### "Unable to import module 'index'"
- Verify Handler is set to `index.handler`
- Check Runtime is Node.js 18.x or 20.x

## 9. Local Testing (Optional)

```bash
# Set environment variables (Windows PowerShell)
$env:BUCKET_NAME="opus-clip-videos"
$env:AWS_REGION="us-east-1"
$env:R2_ENDPOINT="https://your-account.r2.cloudflarestorage.com"
$env:R2_ACCESS_KEY="your-key"
$env:R2_SECRET_KEY="your-secret"

# Run test
node test.js "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## Success!

Your Node.js download Lambda should now work without any 403 errors or n-parameter issues. The `@distube/ytdl-core` library handles all the YouTube authentication challenges automatically.

## Performance

Expected times for a 5-minute video:
- Info fetch: 2-3 seconds
- Download: 15-30 seconds
- Upload: 5-10 seconds
- **Total: 25-45 seconds**

Much faster and more reliable than the Python version!
