# Opus Clip - Serverless Video Processing Pipeline

A serverless video processing system built on AWS Lambda that automatically downloads YouTube videos (or accepts uploads), transcribes them using multiple AI services, detects viral moments with AI, and generates multi-format clips with karaoke-style subtitles.

## 🌟 Features

- **Dual Input Modes**: Download from YouTube OR direct video upload
- **Multi-Service Transcription**: Supports Groq, AssemblyAI, Deepgram, and local Whisper
- **AI-Powered Clip Detection**: Uses Groq Llama 3.3 70B for intelligent viral moment detection
- **Karaoke Subtitles**: Word-by-word highlighting for maximum engagement
- **Multi-Aspect Ratio**: Generates clips in 9:16 (Shorts/Reels), 16:9 (YouTube), 1:1 (Instagram)
- **Parallel Processing**: Processes multiple clips simultaneously
- **Flexible Storage**: Supports AWS S3, Cloudflare R2, Backblaze B2, or any S3-compatible storage
- **Firebase Integration**: User management and video tracking
- **Serverless Architecture**: Fully serverless for automatic scaling and cost efficiency

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    TWO INPUT FLOWS                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  FLOW 1: YouTube Download    FLOW 2: Direct Upload     │
│  ┌──────────────────┐        ┌──────────────────┐      │
│  │  API Gateway     │        │ Upload API GW    │      │
│  │  /process        │        │ /upload/*        │      │
│  └────────┬─────────┘        └────────┬─────────┘      │
│           │                           │                 │
│           ├───────────────────────────┤                 │
│           ↓                           ↓                 │
│     Step Functions          Step Functions              │
│           ↓                           ↓                 │
│  ┌────────────────┐         ┌────────────────┐         │
│  │ Download Lambda│         │  (skip this)   │         │
│  └────────┬───────┘         └────────┬───────┘         │
│           │                          │                  │
│           └──────────┬───────────────┘                  │
│                      ↓                                  │
│           ┌──────────────────┐                          │
│           │ Transcribe Lambda│                          │
│           │ (Groq/Whisper/   │                          │
│           │  AssemblyAI)     │                          │
│           └────────┬─────────┘                          │
│                    ↓                                    │
│           ┌──────────────────┐                          │
│           │ Detect Clips     │                          │
│           │ (AI-powered)     │                          │
│           └────────┬─────────┘                          │
│                    ↓                                    │
│           ┌──────────────────┐                          │
│           │ Process Clip     │                          │
│           │ (Parallel x N)   │                          │
│           │ + Karaoke Subs   │                          │
│           └────────┬─────────┘                          │
│                    ↓                                    │
│           ┌──────────────────┐                          │
│           │ Finalize Lambda  │                          │
│           │ (Generate URLs)  │                          │
│           └────────┬─────────┘                          │
│                    ↓                                    │
│              Result + Clips                             │
│        (9:16, 16:9, 1:1 formats)                        │
└─────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
opus-clip/
├── README.md                           # This file
├── .gitignore                          # Git ignore patterns
├── docs/                               # Documentation
│   ├── lambda-deployment.md            # Lambda deployment guide
│   ├── cloudflare-setup.md             # Cloudflare R2 setup
│   ├── cookie-setup.md                 # YouTube cookie setup
│   └── ytdlp-deployment.md             # yt-dlp layer deployment
├── src/                                # Source code
│   ├── cloudflare-worker-upload-proxy.js  # Optional: Cloudflare Worker for R2 uploads
│   │
│   ├── download/                       # Lambda 1a: Download (Python)
│   │   ├── lambda_function.py          # Uses yt-dlp for downloads
│   │   └── requirements.txt            # Dependencies: yt-dlp
│   │
│   ├── node-download/                  # Lambda 1b: Download (Node.js)
│   │   ├── index.js                    # Uses yt-dlp for downloads
│   │   └── package.json                # Dependencies: @aws-sdk/client-s3
│   │
│   ├── node-upload/                    # Lambda 1c: Upload handler (Node.js)
│   │   ├── index.js                    # Pre-signed URL generation
│   │   └── package.json                # Dependencies: @aws-sdk/s3-request-presigner
│   │
│   ├── transcribe/                     # Lambda 2: Smart transcription
│   │   ├── lambda_function.py          # Multi-service with fallbacks
│   │   └── requirements.txt            # Dependencies: requests
│   │
│   ├── detect-clips/                   # Lambda 3: AI clip detection
│   │   ├── lambda_function.py          # Uses Groq Llama 3.3 70B
│   │   └── requirements.txt            # No dependencies!
│   │
│   ├── process-clip/                   # Lambda 4: Process individual clip
│   │   ├── lambda_function.py          # Multi-aspect ratio + karaoke subs
│   │   └── requirements.txt            # No dependencies!
│   │
│   ├── finalize/                       # Lambda 5: Generate URLs
│   │   ├── lambda_function.py          # Creates download links
│   │   └── requirements.txt            # No dependencies!
│   │
│   ├── api-gateway/                    # Lambda 6: YouTube flow API
│   │   ├── lambda_function.py          # Handles /process endpoint
│   │   └── requirements.txt            # No dependencies!
│   │
│   └── upload-api-gateway/             # Lambda 7: Upload flow API
│       ├── lambda_function.py          # Handles /upload/* endpoints
│       └── requirements.txt            # No dependencies!
│
└── deployment/                         # Deployment scripts & configs
    ├── dockerfiles/                    # Docker build files
    ├── *.bat                           # Windows deployment scripts
    ├── *.sh                            # Linux deployment scripts
    └── step-functions-*.json           # State machine definitions
```

## 🔄 Python vs Node.js Lambda Functions

Some functions are available in both Python and Node.js versions:

### Download Lambda
- **Python version** (`src/download/`): Original implementation, uses yt-dlp
- **Node.js version** (`src/node-download/`): Alternative implementation with identical functionality
- **Choose one**: Both versions do the same thing - download YouTube videos using yt-dlp

### Upload Handler Lambda
- **Python version** (`src/upload-api-gateway/`): REST API handler for upload flow
- **Node.js version** (`src/node-upload/`): Alternative implementation for pre-signed URL generation
- **Choose one**: Both handle video upload via pre-signed URLs

### Cloudflare Worker (Optional)
- **Cloudflare Worker** (`src/cloudflare-worker-upload-proxy.js`): Optional proxy for R2 uploads
- **Use case**: Bypasses CORS issues when uploading directly from browser to R2
- **Deploy to**: Cloudflare Workers (not AWS Lambda)

**Recommendation:** Use Python versions for consistency with the rest of the pipeline, or Node.js versions if your team prefers JavaScript.

## 🚀 Quick Start

### Prerequisites

- AWS Account with Lambda, S3, and Step Functions access
- AWS CLI configured (`aws configure`)
- **For Python lambdas**: Python 3.11+
- **For Node.js lambdas** (optional): Node.js 18+ and npm
- Storage: AWS S3 OR Cloudflare R2 (recommended, 10GB free)
- API Keys:
  - Groq API (free, for transcription & clip detection)
  - Optional: AssemblyAI, Deepgram (for transcription fallbacks)

### 1. Storage Setup

**Option A: Cloudflare R2 (Recommended - 10GB Free)**

```bash
# Create R2 bucket in Cloudflare dashboard
# Get: Access Key, Secret Key, Bucket Name, Account ID
```

See [docs/cloudflare-setup.md](docs/cloudflare-setup.md) for detailed setup.

**Option B: AWS S3**

```bash
aws s3 mb s3://your-opus-clips-bucket
```

### 2. Deploy Lambda Functions

**Quick Deployment (Minimal Dependencies):**

5 out of 7 functions need NO pip packages! Only need the Python file.

```bash
# Functions with NO dependencies (just zip the Python file):
cd opus-clip/src/detect-clips
zip function.zip lambda_function.py
aws lambda create-function \
  --function-name opus-detect-clips \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --zip-file fileb://function.zip \
  --memory-size 2048 \
  --timeout 60

# Repeat for: process-clip, finalize, api-gateway, upload-api-gateway
```

**Functions with Dependencies:**

```bash
# Transcribe Lambda (needs requests)
cd opus-clip/src/transcribe
pip install -r requirements.txt -t ./package
cd package && zip -r ../function.zip . && cd ..
zip function.zip lambda_function.py
aws lambda create-function \
  --function-name opus-transcribe \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --zip-file fileb://function.zip \
  --memory-size 3072 \
  --timeout 600

# Download Lambda - Python version (needs yt-dlp)
cd opus-clip/src/download
pip install -r requirements.txt -t ./package
cd package && zip -r ../function.zip . && cd ..
zip function.zip lambda_function.py
aws lambda create-function \
  --function-name opus-download \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --zip-file fileb://function.zip \
  --memory-size 3072 \
  --timeout 300
```

**Node.js Lambda Functions (Alternative):**

```bash
# Node.js Download Lambda (alternative to Python download)
cd opus-clip/src/node-download
npm install
zip -r function.zip index.js node_modules/
aws lambda create-function \
  --function-name opus-node-download \
  --runtime nodejs18.x \
  --handler index.handler \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --zip-file fileb://function.zip \
  --memory-size 3072 \
  --timeout 300

# Node.js Upload Lambda (pre-signed URL generation)
cd opus-clip/src/node-upload
npm install
zip -r function.zip index.js node_modules/
aws lambda create-function \
  --function-name opus-node-upload \
  --runtime nodejs18.x \
  --handler index.handler \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --zip-file fileb://function.zip \
  --memory-size 512 \
  --timeout 30
```

### 3. Attach Lambda Layers

**FFmpeg Layer** (for process-clip):
```bash
# Use public layer or create your own
aws lambda update-function-configuration \
  --function-name opus-process-clip \
  --layers arn:aws:lambda:us-east-1:145266761615:layer:ffmpeg:4
```

### 4. Configure Environment Variables

**All Lambda Functions:**
```bash
# Storage configuration (choose S3 OR R2)
BUCKET_NAME=your-bucket-name

# If using Cloudflare R2:
R2_ENDPOINT=https://[account-id].r2.cloudflarestorage.com
R2_ACCESS_KEY=your-r2-access-key
R2_SECRET_KEY=your-r2-secret-key
R2_PUBLIC_DOMAIN=pub-xxxxx.r2.dev  # Optional: for public URLs

# If using AWS S3 (leave R2 variables empty)
AWS_REGION=us-east-1
```

**Transcribe Lambda:**
```bash
# API Keys (Groq is primary, others are fallbacks)
GROQ_API_KEY=gsk_xxxxx              # Required
ASSEMBLYAI_API_KEY=xxxxx            # Optional
DEEPGRAM_API_KEY=xxxxx              # Optional

# Model selection
USE_LOCAL_WHISPER=false             # Set true only for container deployments
WHISPER_MODEL=base                  # tiny/base/small/large
```

**Detect Clips Lambda:**
```bash
GROQ_API_KEY=gsk_xxxxx              # Required for AI clip detection
USE_AI_SCORING=true                 # Enable AI-powered scoring
NUM_CLIPS=3                         # Number of clips to generate
MIN_CLIP_DURATION=15                # Minimum clip length (seconds)
MAX_CLIP_DURATION=60                # Maximum clip length (seconds)
TARGET_CLIP_DURATION=45             # Preferred clip length (seconds)
```

**Process Clip Lambda:**
```bash
ASPECT_RATIO=9:16                   # Options: 9:16, 16:9, 1:1
ADD_SUBTITLES=true                  # Enable karaoke subtitles
FFMPEG_PATH=/opt/bin/ffmpeg         # FFmpeg binary path
```

**Finalize Lambda:**
```bash
FIREBASE_PROJECT_ID=your-project-id         # Optional: for user tracking
FIREBASE_WEB_API_KEY=your-api-key           # Optional: for Firestore
```

**API Gateway Lambdas:**
```bash
STATE_MACHINE_ARN=arn:aws:states:region:account:stateMachine:YourStateMachine
```

### 5. Create Step Functions State Machines

You need TWO state machines:

1. **YouTube Download Flow** - For processing YouTube URLs
2. **Upload Flow** - For processing user uploads

Import state machine definitions from `deployment/step-functions-*.json`.

### 6. Test the Pipeline

**YouTube Flow:**
```bash
curl -X POST https://your-api-gateway-url/process \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "user_id": "test-user-123"
  }'
```

**Upload Flow:**
```bash
# 1. Generate upload URL
curl -X POST https://your-api-gateway-url/upload/generate-url \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "fileName": "video.mp4",
    "fileSize": 50000000,
    "contentType": "video/mp4"
  }'

# 2. Upload video using the returned URL (PUT request)
curl -X PUT "returned-presigned-url" \
  --upload-file video.mp4 \
  -H "Content-Type: video/mp4"

# 3. Start processing
curl -X POST https://your-api-gateway-url/upload/start \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-id-from-step-1",
    "user_id": "test-user-123",
    "s3_key": "s3-key-from-step-1"
  }'
```

## 📊 Lambda Functions Overview

| Function | Language | Purpose | Memory | Timeout | Dependencies | Binary Layers |
|----------|----------|---------|--------|---------|--------------|---------------|
| **download** (Python) | Python 3.11 | Downloads YouTube videos | 3 GB | 5 min | yt-dlp | yt-dlp layer |
| **node-download** (Node.js) | Node.js 18+ | Downloads YouTube videos | 3 GB | 5 min | @aws-sdk/client-s3, @aws-sdk/lib-storage | yt-dlp layer |
| **node-upload** (Node.js) | Node.js 18+ | Pre-signed URL generation | 512 MB | 30 sec | @aws-sdk/client-s3, @aws-sdk/s3-request-presigner | - |
| **transcribe** | Python 3.11 | Transcribes audio with AI | 3 GB | 10 min | requests | - |
| **detect-clips** | Python 3.11 | AI-powered clip detection | 2 GB | 2 min | **None!** | - |
| **process-clip** | Python 3.11 | Extracts clips + karaoke subs | 4 GB | 5 min | **None!** | FFmpeg layer |
| **finalize** | Python 3.11 | Generates download URLs | 512 MB | 30 sec | **None!** | - |
| **api-gateway** | Python 3.11 | Handles YouTube flow API | 512 MB | 30 sec | **None!** | - |
| **upload-api-gateway** | Python 3.11 | Handles upload flow API | 512 MB | 30 sec | **None!** | - |

**Notes:**
- **Python**: boto3 and botocore are pre-installed in AWS Lambda runtime - no need to package them!
- **Node.js**: You can use either Python or Node.js versions for download functionality - both are functionally equivalent
- **node-upload**: Alternative to Python upload-api-gateway for upload URL generation

## ⚙️ Configuration Options

### Transcription Service Priority

The transcribe lambda tries services in this order:
1. **Groq API** (primary) - Fast, free tier available
2. **AssemblyAI** (fallback 1) - If Groq fails
3. **Deepgram** (fallback 2) - If AssemblyAI fails
4. **Local Whisper** (fallback 3) - Requires container deployment

### Aspect Ratio Modes

Set `ASPECT_RATIO` in process-clip lambda:
- `9:16` - Vertical (TikTok, Instagram Reels, YouTube Shorts)
- `16:9` - Horizontal (YouTube landscape)
- `1:1` - Square (Instagram feed)

### Clip Detection Parameters

Configure in detect-clips lambda:
- `NUM_CLIPS` - How many clips to generate (default: 3)
- `MIN_CLIP_DURATION` - Minimum clip length (default: 15s)
- `MAX_CLIP_DURATION` - Maximum clip length (default: 60s)
- `TARGET_CLIP_DURATION` - Preferred length (default: 45s)
- `USE_AI_SCORING` - Use AI or fallback heuristics (default: true)

### Subtitle Options

Karaoke subtitles are always enabled and automatically adapt based on available data:
- **Word-level timestamps available** → Karaoke effect (word-by-word highlighting)
- **Only segment timestamps** → Simple subtitles (sentence-level)
- **No timestamps** → No subtitles

## 💰 Cost Estimation

### For 100 videos/month (15 min avg, 3 clips each):

**AWS Costs:**
- Lambda Compute: ~$4-6/month
- Data Transfer: ~$1/month
- Step Functions: ~$0.25/month

**Storage Costs:**
- AWS S3: ~$2.19/month
- Cloudflare R2: **$0/month (free up to 10GB)**
- Backblaze B2: ~$0.50/month

**API Costs:**
- Groq (transcription + AI): Free tier (14,400 sec/day)
- AssemblyAI: Free tier or ~$0.25/video
- Deepgram: Free tier or ~$0.20/video

**Total:**
- **With Cloudflare R2 + Groq free tier: ~$4-7/month**
- **With AWS S3 + paid APIs: ~$10-15/month**

## 📖 Documentation

- [Lambda Deployment Guide](docs/lambda-deployment.md) - Complete deployment instructions
- [Cloudflare R2 Setup](docs/cloudflare-setup.md) - Free storage setup (10GB)
- [Cookie Setup](docs/cookie-setup.md) - YouTube authentication for restricted videos
- [yt-dlp Deployment](docs/ytdlp-deployment.md) - Lambda layer setup

## 🔍 Monitoring

### CloudWatch Logs

Each function logs to: `/aws/lambda/opus-{function-name}`

Key log prefixes to search:
- `[Download]` - Video download progress
- `[Transcribe]` - Transcription status and method used
- `[Detect]` - Clip detection with AI scores
- `[ProcessClip]` - Clip processing with timing breakdowns
- `[Finalize]` - Final URL generation
- `[API]` - API request handling

### Step Functions

Monitor workflow execution in the AWS Step Functions console. Each session has a unique execution name.

### Storage Structure

```
your-bucket/
└── users/{user-id}/          # Optional: user-specific organization
    └── {session-id}/
        ├── original_video.mp4        # Or uploaded_video.mp4
        ├── transcript.json           # Full transcript with timestamps
        ├── result.json              # Final result with URLs
        └── clips/
            ├── clip_0_9x16.mp4      # Vertical format
            ├── clip_0_16x9.mp4      # Horizontal format (if generated)
            ├── clip_0_1x1.mp4       # Square format (if generated)
            ├── clip_1_9x16.mp4
            └── ...
```

## 🐛 Troubleshooting

**Lambda Timeout:**
- Increase timeout in Lambda configuration
- For transcribe: Use Groq API instead of local Whisper
- For download: Check network speed, use faster quality mode

**Out of Memory:**
- Increase Lambda memory allocation
- For transcribe: Use API services instead of local Whisper
- For process-clip: Reduce concurrent clip processing

**FFmpeg Not Found:**
- Ensure FFmpeg Lambda Layer is attached to process-clip function
- Verify FFMPEG_PATH environment variable: `/opt/bin/ffmpeg`
- Test layer: `ls /opt/bin/` in Lambda

**No Word-Level Timestamps (No Karaoke Effect):**
- Groq requires `timestamp_granularities: ["word", "segment"]` parameter
- Ensure transcribe lambda is updated to request word timestamps
- Check transcript.json - segments should have `words` array

**YouTube Download Fails:**
- Add YouTube cookies (see [docs/cookie-setup.md](docs/cookie-setup.md))
- Update yt-dlp to latest version
- Check video is not age-restricted or private

**Groq API Errors:**
- Check API key is valid
- Verify free tier limits (14,400 sec/day for transcription)
- Fallbacks should activate automatically

## 🔒 Security Best Practices

1. **IAM Roles**: Use least-privilege IAM roles for Lambda functions
2. **API Keys**: Store API keys in AWS Secrets Manager or environment variables
3. **CORS**: Configure appropriate CORS settings in API Gateway
4. **Pre-signed URLs**: Set reasonable expiration times (7 days default)
5. **Input Validation**: API Gateway lambdas validate user inputs
6. **Rate Limiting**: Consider adding API Gateway throttling

## 🛠️ Development

**Local Testing:**
```bash
# Set environment variables
export BUCKET_NAME=test-bucket
export GROQ_API_KEY=your-key

# Run function locally
cd src/transcribe
python lambda_function.py
```

**Deployment Scripts:**
```bash
# Windows
deployment/build-all.bat

# Linux/Mac
deployment/build-all.sh
```

## 📝 License

This project uses:
- OpenAI Whisper (MIT License)
- yt-dlp (Unlicense)
- FFmpeg (GPL/LGPL License - use static binaries)
- Groq API (API service, check terms)

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 💬 Support

For issues and questions:
- Check the [documentation](docs/)
- Review CloudWatch Logs for error details
- Search existing GitHub issues
- Open a new GitHub issue with:
  - Lambda function name
  - Error message from CloudWatch
  - Environment configuration (without secrets)

## 🎯 Roadmap

- [ ] Add support for more transcription services
- [ ] Implement custom subtitle styling
- [ ] Add video quality presets
- [ ] Support batch processing
- [ ] Add webhook notifications
- [ ] Implement retry logic with exponential backoff
- [ ] Add video preview generation
- [ ] Support more aspect ratios (4:5, 2:3)

---

Built with ❤️ for serverless video processing
