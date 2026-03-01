# Clip on Fly — Backend

Serverless video processing pipeline built on AWS Lambda. Accepts YouTube URLs or direct video uploads, transcribes audio with AI, detects viral moments, and generates multi-format short clips with karaoke-style subtitles.

---

## Features

- **Dual Input Modes** — Process YouTube URLs or direct video uploads
- **AI Transcription** — Groq, AssemblyAI, Deepgram, or local Whisper with automatic fallbacks
- **AI Clip Detection** — Groq Llama 3.3 70B identifies the best viral moments
- **Karaoke Subtitles** — Word-by-word highlighting for Shorts/Reels engagement
- **Multi-Aspect Ratio** — Generates 9:16 (Shorts/Reels), 16:9 (YouTube), 1:1 (Instagram) simultaneously
- **Parallel Processing** — Multiple clips processed at the same time
- **Flexible Storage** — Cloudflare R2, AWS S3, Backblaze B2, or any S3-compatible provider
- **Firebase Integration** — User management and video session tracking
- **Fully Serverless** — Auto-scaling, pay-per-use, no servers to manage

---

## Architecture

```
TWO INPUT FLOWS
─────────────────────────────────────────────────────

FLOW 1: YouTube URL              FLOW 2: Direct Upload
  API Gateway /process             API Gateway /upload/*
        |                                  |
        └──────────────┬───────────────────┘
                       |
                 Step Functions
                       |
             ┌─────────────────┐
             │ Download Lambda │  (Flow 1 only)
             └────────┬────────┘
                      |
             ┌─────────────────┐
             │   Transcribe    │  Groq / AssemblyAI / Deepgram
             └────────┬────────┘
                      |
             ┌─────────────────┐
             │  Detect Clips   │  Groq Llama 3.3 70B
             └────────┬────────┘
                      |
             ┌─────────────────┐
             │  Process Clip   │  Parallel x N clips
             │  + Karaoke Subs │
             └────────┬────────┘
                      |
             ┌─────────────────┐
             │    Finalize     │  Generate signed URLs
             └─────────────────┘
                      |
              Result + Clips
         (9:16 / 16:9 / 1:1 formats)
```

---

## Lambda Functions

| Function | Runtime | Purpose | Memory | Timeout |
|---|---|---|---|---|
| download | Python 3.11 | Download YouTube videos via yt-dlp | 3 GB | 5 min |
| node-download | Node.js 18 | Alternative download (Node.js) | 3 GB | 5 min |
| node-upload | Node.js 18 | Generate pre-signed upload URLs | 512 MB | 30 sec |
| transcribe | Python 3.11 | Multi-service audio transcription | 3 GB | 10 min |
| detect-clips | Python 3.11 | AI-powered clip detection | 2 GB | 2 min |
| process-clip | Python 3.11 | Clip extraction + karaoke subtitles | 4 GB | 5 min |
| finalize | Python 3.11 | Generate download URLs | 512 MB | 30 sec |
| api-gateway | Python 3.11 | YouTube flow API handler | 512 MB | 30 sec |
| upload-api-gateway | Python 3.11 | Upload flow API handler | 512 MB | 30 sec |

> boto3 and botocore are pre-installed in the AWS Lambda Python runtime — no need to package them.

---

## Project Structure

```
opus-clip-cloud/
├── src/
│   ├── download/                    # Lambda: YouTube download (Python)
│   ├── node-download/               # Lambda: YouTube download (Node.js)
│   ├── node-upload/                 # Lambda: Pre-signed URL generation
│   ├── transcribe/                  # Lambda: Multi-service transcription
│   ├── detect-clips/                # Lambda: AI clip detection
│   ├── process-clip/                # Lambda: Clip processing + subtitles
│   ├── finalize/                    # Lambda: URL generation
│   ├── api-gateway/                 # Lambda: YouTube flow API
│   ├── upload-api-gateway/          # Lambda: Upload flow API
│   └── cloudflare-worker-upload-proxy.js  # Optional: Cloudflare R2 proxy
├── deployment/                      # Build and deploy scripts
│   ├── dockerfiles/                 # Docker build files for container lambdas
│   ├── *.bat / *.sh                 # Windows/Linux deployment scripts
│   └── step-functions-*.json        # State machine definitions
└── docs/                            # Deployment and setup guides
```

---

## Getting Started

### Prerequisites

- AWS account with Lambda, S3, Step Functions, and API Gateway access
- AWS CLI configured (`aws configure`)
- Python 3.11+ (for Python lambdas)
- Node.js 18+ (for Node.js lambdas, optional)
- Cloudflare R2 bucket or AWS S3 bucket
- Groq API key (free tier available)

### 1. Clone and configure

```bash
git clone https://github.com/saivenkat2609/opus-clip.git
cd opus-clip-cloud

cp deployment/config.env.example deployment/config.env
# Fill in your credentials in deployment/config.env
```

### 2. Deploy Lambda functions

**Functions with no dependencies** (just zip and upload):

```bash
cd src/detect-clips
zip function.zip lambda_function.py
aws lambda create-function \
  --function-name opus-detect-clips \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --zip-file fileb://function.zip \
  --memory-size 2048 \
  --timeout 60
```

Repeat for: `process-clip`, `finalize`, `api-gateway`, `upload-api-gateway`

**Functions with dependencies:**

```bash
# Transcribe Lambda
cd src/transcribe
pip install -r requirements.txt -t ./package
cd package && zip -r ../function.zip . && cd ..
zip function.zip lambda_function.py

# Download Lambda (Python)
cd src/download
pip install -r requirements.txt -t ./package
cd package && zip -r ../function.zip . && cd ..
zip function.zip lambda_function.py
```

### 3. Attach Lambda layers

```bash
# FFmpeg layer for process-clip
aws lambda update-function-configuration \
  --function-name opus-process-clip \
  --layers arn:aws:lambda:us-east-1:145266761615:layer:ffmpeg:4
```

### 4. Configure environment variables

Set these on each Lambda function in the AWS Console or via CLI:

**All functions:**
```env
BUCKET_NAME=your-bucket-name

# Cloudflare R2 (recommended)
R2_ENDPOINT=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
R2_ACCESS_KEY=your-r2-access-key
R2_SECRET_KEY=your-r2-secret-key
R2_PUBLIC_DOMAIN=pub-xxxxx.r2.dev
```

**Transcribe & Detect-Clips:**
```env
GROQ_API_KEY=gsk_xxxxx
ASSEMBLYAI_API_KEY=xxxxx      # Optional fallback
DEEPGRAM_API_KEY=xxxxx        # Optional fallback
```

**Detect-Clips:**
```env
NUM_CLIPS=3
MIN_CLIP_DURATION=15
MAX_CLIP_DURATION=60
TARGET_CLIP_DURATION=45
USE_AI_SCORING=true
```

**Process-Clip:**
```env
ASPECT_RATIO=9:16
ADD_SUBTITLES=true
FFMPEG_PATH=/opt/bin/ffmpeg
```

**API Gateway Lambdas:**
```env
STATE_MACHINE_ARN=arn:aws:states:region:account:stateMachine:YourStateMachine
```

### 5. Create Step Functions state machines

Import from `deployment/step-functions-*.json`. You need two state machines:
- YouTube Download Flow
- Upload Flow

---

## Testing the Pipeline

**YouTube flow:**
```bash
curl -X POST https://your-api-gateway-url/process \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=EXAMPLE", "user_id": "test-user"}'
```

**Upload flow:**
```bash
# Step 1: Get pre-signed upload URL
curl -X POST https://your-api-gateway-url/upload/generate-url \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user", "fileName": "video.mp4", "fileSize": 50000000, "contentType": "video/mp4"}'

# Step 2: Upload the video
curl -X PUT "PRESIGNED_URL_FROM_STEP_1" --upload-file video.mp4 -H "Content-Type: video/mp4"

# Step 3: Start processing
curl -X POST https://your-api-gateway-url/upload/start \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SESSION_ID", "user_id": "test-user", "s3_key": "S3_KEY"}'
```

---

## Storage Layout

```
your-bucket/
└── users/{user-id}/
    └── {session-id}/
        ├── original_video.mp4
        ├── transcript.json
        ├── result.json
        └── clips/
            ├── clip_0_9x16.mp4
            ├── clip_0_16x9.mp4
            ├── clip_0_1x1.mp4
            └── ...
```

---

## Transcription Service Priority

The transcribe Lambda tries services in this order:
1. **Groq** (primary) — fast, free tier available
2. **AssemblyAI** (fallback 1)
3. **Deepgram** (fallback 2)
4. **Local Whisper** (fallback 3) — container deployments only

---

## Cost Estimate

For 100 videos/month (15 min avg, 3 clips each):

| Service | Cost |
|---|---|
| AWS Lambda + Step Functions | ~$5–7/month |
| Cloudflare R2 storage | $0 (up to 10GB free) |
| Groq API | $0 (free tier: 14,400 sec/day) |
| **Total** | **~$5–7/month** |

---

## Monitoring

Each Lambda logs to `/aws/lambda/opus-{function-name}` in CloudWatch.

Key log prefixes:
- `[Download]` — download progress
- `[Transcribe]` — transcription status and service used
- `[Detect]` — clip scores and selections
- `[ProcessClip]` — processing timing
- `[Finalize]` — URL generation

---

## Troubleshooting

**Lambda timeout** — Increase timeout; for transcribe, use Groq API instead of local Whisper.

**Out of memory** — Increase Lambda memory; use API transcription services instead of local Whisper.

**FFmpeg not found** — Ensure FFmpeg layer is attached to `process-clip` and `FFMPEG_PATH=/opt/bin/ffmpeg`.

**No karaoke effect** — Groq requires `timestamp_granularities: ["word", "segment"]`; check transcript.json for a `words` array in segments.

**YouTube download fails** — Add YouTube cookies (see `docs/cookie-setup.md`); update yt-dlp layer.

---

## Security

- All secrets are stored in AWS Lambda environment variables — nothing hardcoded in source
- Firebase Admin credentials are managed via environment variables, never committed
- IAM roles follow least-privilege principle
- Razorpay and R2 webhook signatures are verified server-side
- Pre-signed URLs expire after 7 days

---

## Documentation

- [Lambda Deployment Guide](docs/lambda-deployment.md)
- [Cloudflare R2 Setup](docs/cloudflare-setup.md)
- [Cookie Setup for YouTube](docs/cookie-setup.md)
- [yt-dlp Layer Deployment](docs/ytdlp-deployment.md)

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push and open a pull request

---

## License

MIT
