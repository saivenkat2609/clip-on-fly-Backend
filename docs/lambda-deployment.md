# Opus Clip - AWS Lambda Deployment Package

This directory contains everything you need to deploy your video processing project to AWS Lambda.

## 📦 What's Included

### Lambda Function Files

1. **1-lambda-download.py** - Downloads YouTube videos to S3
   - Memory: 3 GB
   - Timeout: 5 minutes
   - Dependencies: pytubefix, boto3

2. **2-lambda-transcribe.py** - Transcribes audio using Whisper
   - Memory: 10 GB (maximum)
   - Timeout: 10 minutes
   - Dependencies: openai-whisper, boto3, numpy
   - ⚠️ Large deployment package (~1.8 GB)

3. **3-lambda-detect-clips.py** - Detects viral clip segments
   - Memory: 2 GB
   - Timeout: 1 minute
   - Dependencies: boto3

4. **4-lambda-process-clip.py** - Processes clips (extract, convert, add subtitles)
   - Memory: 4 GB
   - Timeout: 5 minutes
   - Dependencies: boto3
   - Requires: FFmpeg Lambda Layer

5. **5-lambda-finalize.py** - Generates download URLs and saves results
   - Memory: 512 MB
   - Timeout: 30 seconds
   - Dependencies: boto3

6. **6-lambda-api-gateway.py** - API Gateway handler
   - Memory: 512 MB
   - Timeout: 30 seconds
   - Dependencies: boto3
   - Handles: POST /process, GET /status, GET /result

### Configuration Files

- **step-functions-state-machine.json** - Step Functions workflow definition
- **requirements-download.txt** - Dependencies for download function
- **requirements-transcribe.txt** - Dependencies for transcribe function
- **requirements-process.txt** - Dependencies for process function

### Documentation

- **README-DEPLOYMENT.md** - Complete deployment guide (2-3 hours)
- **QUICK-START.md** - Fast track deployment guide (30 minutes)
- **00-README.md** - This file

### Packaging Scripts

- **package-lambda.bat** - Windows batch script to create all deployment ZIPs

---

## 🚀 Quick Start

### Option 1: Follow Quick Start Guide (Recommended)

```cmd
1. Read QUICK-START.md
2. Run: package-lambda.bat
3. Follow the 30-minute deployment steps
```

### Option 2: Full Deployment Guide

```cmd
1. Read README-DEPLOYMENT.md
2. Run: package-lambda.bat
3. Follow detailed step-by-step instructions
```

---

## 📂 File Structure After Packaging

```
lambda-functions/
├── 00-README.md                      (this file)
├── QUICK-START.md                    (30-min guide)
├── README-DEPLOYMENT.md              (full guide)
│
├── 1-lambda-download.py              (source code)
├── 2-lambda-transcribe.py
├── 3-lambda-detect-clips.py
├── 4-lambda-process-clip.py
├── 5-lambda-finalize.py
├── 6-lambda-api-gateway.py
│
├── step-functions-state-machine.json (workflow definition)
├── package-lambda.bat                (packaging script)
│
├── requirements-download.txt         (dependencies)
├── requirements-transcribe.txt
├── requirements-process.txt
│
└── After running package-lambda.bat:
    ├── opus-download.zip             (~20 MB)
    ├── opus-transcribe.zip           (~1.8 GB) ⚠️
    ├── opus-detect.zip               (~15 MB)
    ├── opus-process-clip.zip         (~15 MB)
    ├── opus-finalize.zip             (~15 MB)
    ├── opus-api-gateway.zip          (~15 MB)
    │
    └── deploy-* folders/             (temporary build dirs)
```

---

## 🏗️ Architecture Overview

```
                    [Your Web UI]
                          ↓
                   [API Gateway]
                          ↓
              [Lambda: API Handler] ────────┐
                          ↓                  │
                [Step Functions]             │
                          ↓                  │
         ┌────────────────┴────────────┐    │
         ↓                             ↓    │
  [Lambda: Download]          [S3 Bucket] ←─┘
         ↓                             ↑
  [Lambda: Transcribe] ────────────────┤
         ↓                             │
  [Lambda: Detect Clips]               │
         ↓                             │
  [Lambda: Process Clip] ──────────────┤
    (runs in parallel × N)             │
         ↓                             │
  [Lambda: Finalize] ──────────────────┘
         ↓
    [Result JSON + Pre-signed URLs]
```

**Processing Flow:**
1. User submits YouTube URL via your UI
2. API Gateway triggers Lambda → starts Step Functions
3. Download Lambda fetches video → uploads to S3
4. Transcribe Lambda uses Whisper → transcript to S3
5. Detect Lambda analyzes transcript → finds 3 best clips
6. Process Lambda runs in parallel (3 instances) → extracts & processes clips
7. Finalize Lambda generates download URLs → returns to user

**Total Time:** ~12-15 minutes for 15-minute video

---

## 💰 Cost Estimate

### For 100 videos/month (15 min avg, 3 clips each):

| Service | Free Tier | Actual Usage | Your Cost |
|---------|-----------|--------------|-----------|
| Lambda Compute | 400K GB-sec | ~640K GB-sec | **$3.94** |
| Lambda Invocations | 1M requests | 700 | $0 |
| Step Functions | 4K transitions | 800 | $0 |
| S3 Storage | 5 GB | 100 GB | **$2.19** |
| S3 Requests | 20K | 1.5K | $0.01 |
| Data Transfer | 100 GB | 50 GB | $0 |
| **TOTAL** | | | **~$6.14/month** |

**Scaling:**
- 500 videos/month: ~$30
- 1000 videos/month: ~$60

**Comparison to Oracle Free Tier:**
- Oracle: $0/month but limited to 1-2 concurrent videos
- Lambda: $6/month but scales to 100+ concurrent videos

---

## ⚙️ Configuration Options

### Environment Variables

**All Functions:**
- `BUCKET_NAME` - Your S3 bucket name (required)

**opus-transcribe:**
- `WHISPER_MODEL` - Model size: `tiny`, `base`, `small`, `medium`, `large`
  - `tiny`: Fastest, least accurate (~3 min for 15-min video)
  - `base`: Balanced (default) (~6 min for 15-min video)
  - `small`: More accurate (~10 min for 15-min video)

**opus-detect:**
- `MIN_CLIP_DURATION` - Minimum clip length in seconds (default: 15)
- `MAX_CLIP_DURATION` - Maximum clip length in seconds (default: 60)
- `TARGET_CLIP_DURATION` - Target clip length (default: 30)
- `NUM_CLIPS` - Number of clips to generate (default: 3)

**opus-process-clip:**
- `FFMPEG_PATH` - Path to FFmpeg binary (default: `/opt/bin/ffmpeg`)

**opus-api-gateway:**
- `STATE_MACHINE_ARN` - ARN of your Step Functions state machine (required)

---

## 🔍 Monitoring & Debugging

### CloudWatch Logs

Each Lambda function logs to CloudWatch Logs:
- Log Group: `/aws/lambda/opus-FUNCTION_NAME`
- View in: https://console.aws.amazon.com/cloudwatch/

**Common Log Patterns:**
```
[Download] Session: abc-123
[Download] URL: https://...
[Download] Complete!

[Transcribe] Loading Whisper model...
[Transcribe] Transcribed 45 segments

[Detect] Found 3 clips

[ProcessClip] Clip 0: 12.5s - 42.3s
[ProcessClip] Complete!
```

### Step Functions Execution

Visual workflow monitoring:
1. Go to Step Functions console
2. Click on execution
3. See which step is running/failed
4. Click failed step → see error details

### S3 Bucket Structure

```
your-bucket/
└── {session-id}/
    ├── original_video.mp4
    ├── transcript.json
    ├── result.json
    └── clips/
        ├── clip_0.mp4
        ├── clip_1.mp4
        └── clip_2.mp4
```

---

## 🛠️ Customization

### Change Number of Clips

Edit `opus-detect` Lambda environment variable:
- `NUM_CLIPS=5` (generate 5 clips instead of 3)

### Change Clip Duration

Edit `opus-detect` Lambda environment variables:
- `MIN_CLIP_DURATION=20` (minimum 20 seconds)
- `MAX_CLIP_DURATION=90` (maximum 90 seconds)
- `TARGET_CLIP_DURATION=45` (prefer 45-second clips)

### Change Whisper Model

Edit `opus-transcribe` Lambda environment variable:
- `WHISPER_MODEL=tiny` (faster, less accurate)
- `WHISPER_MODEL=large` (slower, more accurate)

**Impact on Processing Time (15-min video):**
- `tiny`: ~3 minutes transcription
- `base`: ~6 minutes transcription (default)
- `small`: ~10 minutes transcription
- `medium`: ~20 minutes transcription
- `large`: ~40 minutes transcription

---

## 🐛 Common Issues

### 1. "No module named 'pytubefix'"

**Solution:** Deployment package missing dependencies
```cmd
cd lambda-functions
package-lambda.bat
```

### 2. Lambda Timeout

**Solution:** Increase timeout in Lambda Configuration → General configuration

**Recommended Timeouts:**
- Download: 5 minutes
- Transcribe: 10 minutes (or 15 for longer videos)
- Detect: 1 minute
- Process: 5 minutes
- Finalize: 30 seconds

### 3. "FFmpeg: command not found"

**Solution:** Add FFmpeg Lambda Layer to `opus-process-clip` function
- Use public layer: `arn:aws:lambda:us-east-1:145266761615:layer:ffmpeg:4`
- Or build your own (see README-DEPLOYMENT.md)

### 4. "Out of Memory"

**Solutions:**
- Increase Lambda memory in Configuration
- For transcribe: Reduce Whisper model to `tiny`
- For process: Increase ephemeral storage to 10 GB

### 5. "Rate Exceeded"

**Solution:** Request Lambda concurrency limit increase
- Default: 1000 concurrent executions
- Contact AWS Support to increase

---

## 📊 Performance Optimization

### Speed Up Processing

1. **Use smaller Whisper model**: `WHISPER_MODEL=tiny`
   - Saves 3-4 minutes per video
   - Trade-off: Lower transcription accuracy

2. **Reduce number of clips**: `NUM_CLIPS=1`
   - Saves processing time
   - Generates fewer clips

3. **Increase Lambda memory**: More CPU allocated
   - Transcribe: 10 GB → more CPU for Whisper
   - Process: 4 GB → faster FFmpeg encoding

### Reduce Costs

1. **Use Oracle Free Tier for development**
   - Test on Oracle Cloud (free)
   - Deploy to Lambda for production

2. **Reduce Whisper model**: `WHISPER_MODEL=tiny`
   - Uses less Lambda compute time
   - Saves ~$1-2 per 100 videos

3. **Set S3 lifecycle policy**: Auto-delete after 7 days
   - Saves storage costs
   - Already configured in deployment guide

---

## 🔐 Security Best Practices

### 1. Restrict S3 Bucket Access

- Keep "Block Public Access" enabled
- Use pre-signed URLs for downloads (already implemented)

### 2. Add API Authentication

Options:
- API Gateway API Keys
- AWS Cognito User Pools
- Custom Lambda Authorizer

### 3. Enable CloudTrail

- Track API calls
- Monitor for suspicious activity

### 4. Set Resource Limits

- Lambda concurrent execution limits
- API Gateway throttling

---

## 📞 Support

### Getting Help

1. **Check CloudWatch Logs** for error messages
2. **Check Step Functions execution** for failed steps
3. **Review this documentation** for common issues
4. **AWS Documentation**:
   - Lambda: https://docs.aws.amazon.com/lambda/
   - Step Functions: https://docs.aws.amazon.com/step-functions/
   - S3: https://docs.aws.amazon.com/s3/

### Useful AWS Console Links

- Lambda: https://console.aws.amazon.com/lambda/
- Step Functions: https://console.aws.amazon.com/states/
- S3: https://console.aws.amazon.com/s3/
- CloudWatch: https://console.aws.amazon.com/cloudwatch/
- API Gateway: https://console.aws.amazon.com/apigateway/

---

## 🎉 Next Steps

1. **Run `package-lambda.bat`** to create deployment packages
2. **Follow QUICK-START.md** for 30-minute deployment
3. **Test with a sample YouTube video**
4. **Connect your UI** using the API endpoints
5. **Monitor costs** in AWS Cost Explorer
6. **Optimize** based on your usage patterns

---

## 📝 Changelog

- **v1.0** (2025-01-24): Initial Lambda conversion
  - 6 Lambda functions
  - Step Functions orchestration
  - Parallel clip processing
  - Full deployment guide

---

## 📄 License

This project uses:
- OpenAI Whisper (MIT License)
- PyTubeFix (MIT License)
- FFmpeg (GPL License - use static binaries)

---

**Ready to deploy? Start with QUICK-START.md!** 🚀
