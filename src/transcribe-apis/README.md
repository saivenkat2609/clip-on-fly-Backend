# Opus Transcribe APIs Lambda Function

Lightweight transcription Lambda function that uses only third-party APIs (Groq, AssemblyAI, Deepgram) without the heavy local Whisper model.

## Features

- ✅ **Lightweight**: No PyTorch, no Whisper model - just API calls
- ✅ **Fast deployment**: Simple zip package instead of Docker container
- ✅ **Cost effective**: Only pay for API usage, not compute time
- ✅ **Word-level timestamps**: All APIs return karaoke-ready transcripts
- ✅ **Automatic fallback**: Tries Groq → AssemblyAI → Deepgram in order
- ✅ **Same interface**: Drop-in replacement for the Docker-based transcribe function

## Comparison: API-only vs Docker Whisper

| Feature | transcribe-apis (this) | transcribe (Docker) |
|---------|----------------------|---------------------|
| Deployment | ZIP package (~5MB) | Docker image (~2GB) |
| Cold start | ~1-2 seconds | ~30-60 seconds |
| Transcription | External API | Local Whisper model |
| Cost | API usage only | High compute cost |
| Speed | Fast (API dependent) | Slower (compute bound) |
| Dependencies | boto3, requests | PyTorch, Whisper, ffmpeg |

## Environment Variables

### Required
- `BUCKET_NAME`: S3/R2 bucket name for video storage
- At least ONE API key from the following:
  - `GROQ_API_KEY`: Groq API key (recommended - fastest and free tier)
  - `ASSEMBLYAI_API_KEY`: AssemblyAI API key
  - `DEEPGRAM_API_KEY`: Deepgram API key

### Optional (for R2/S3-compatible storage)
- `R2_ENDPOINT`: Custom S3-compatible endpoint (e.g., Cloudflare R2)
- `R2_ACCESS_KEY`: Access key for R2/S3-compatible storage
- `R2_SECRET_KEY`: Secret key for R2/S3-compatible storage
- `AWS_REGION`: AWS region (default: from config)

### Optional (for ffmpeg)
- `FFMPEG_PATH`: Path to ffmpeg binary (default: `/opt/bin/ffmpeg`)

## Deployment

### Prerequisites
1. Python 3.11+ installed locally
2. AWS CLI configured
3. IAM role with:
   - `AWSLambdaBasicExecutionRole`
   - S3 read/write permissions for your bucket
4. At least one API key configured in `deployment/config.env`

### Deploy Steps

1. **Configure API keys** in `deployment/config.env`:
```env
GROQ_API_KEY=your_groq_key_here
ASSEMBLYAI_API_KEY=your_assemblyai_key_here
DEEPGRAM_API_KEY=your_deepgram_key_here
```

2. **Run the deployment script**:
```batch
cd C:\Vijay\Work\Clipforge\opus-clip\deployment
.\deploy-transcribe-apis.bat
```

3. **Attach ffmpeg layer** (if not already attached):
```bash
aws lambda update-function-configuration \
  --function-name opus-transcribe-apis \
  --layers arn:aws:lambda:us-east-1:YOUR_ACCOUNT:layer:ffmpeg:1 \
  --region us-east-1
```

## API Key Setup

### Groq API (Recommended)
- Sign up: https://console.groq.com/
- Free tier: 14,400 seconds/day
- Model: whisper-large-v3
- Speed: Very fast

### AssemblyAI
- Sign up: https://www.assemblyai.com/
- Free tier: 5 hours/month
- Speed: Moderate

### Deepgram
- Sign up: https://deepgram.com/
- Free tier: $200 credits
- Speed: Very fast

## Usage

The function uses the same input/output format as the Docker-based transcribe function:

### Input Event
```json
{
  "session_id": "uuid-here",
  "s3_video_key": "session_id/original_video.mp4",
  "video_info": {
    "title": "Video Title",
    "duration": 120
  }
}
```

### Output
```json
{
  "statusCode": 200,
  "session_id": "uuid-here",
  "s3_video_key": "session_id/original_video.mp4",
  "s3_transcript_key": "session_id/transcript.json",
  "video_info": { ... },
  "transcript_preview": {
    "text": "First 200 chars of transcript...",
    "segments_count": 45,
    "method": "groq-api",
    "has_word_timestamps": true
  }
}
```

## Integration with Step Functions

Update your Step Functions state machine to use this function instead of `opus-transcribe`:

```json
{
  "Type": "Task",
  "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:opus-transcribe-apis",
  "Next": "DetectClips"
}
```

## Transcription Flow

1. Download video from S3/R2
2. Extract audio using ffmpeg
3. Try Groq API first (fastest, free tier)
4. If Groq fails, try AssemblyAI
5. If AssemblyAI fails, try Deepgram
6. Return transcript with word-level timestamps
7. Clean up temporary files

## Cost Comparison

### API-only (this function)
- Lambda: ~$0.01 per video (minimal compute)
- Groq: Free (14,400s/day) or $0.05 per hour
- **Total**: ~$0.01-0.06 per video

### Docker Whisper
- Lambda: ~$0.50 per video (10GB memory, 2-3 min)
- **Total**: ~$0.50 per video

**Savings: ~90% cheaper!**

## Troubleshooting

### No API key error
- Ensure at least one API key is set in environment variables
- Check config.env has the correct key

### ffmpeg not found
- Attach the ffmpeg Lambda layer
- Or set FFMPEG_PATH to your custom ffmpeg location

### All APIs failed
- Check API key validity
- Check API rate limits
- Check CloudWatch logs for detailed errors

## Limitations

- Requires external API (internet connectivity)
- Subject to API rate limits
- Cannot work offline
- Dependent on third-party service availability

## Support

For issues or questions, check:
1. CloudWatch Logs: `/aws/lambda/opus-transcribe-apis`
2. Lambda function configuration in AWS Console
3. Test with a small video first

## License

Same as parent project
