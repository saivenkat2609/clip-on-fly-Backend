# 🏗️ WHAT WE BUILT - Architecture Summary

**Quick overview of all scalability features and how they're used in your video processing application.**

---

## 📦 1. Lambda Layer (shared-utilities)

**What**: Python package with shared utilities for all Lambda functions

**Location**: AWS Lambda → Layers → `shared-utilities`

**Contains**:
- `shared/logger.py` - Structured JSON logging
- `shared/metrics.py` - CloudWatch custom metrics
- `shared/circuit_breaker.py` - API fault tolerance
- `shared/dynamodb_client.py` - Session tracking
- `shared/websocket_notifier.py` - Real-time notifications
- `shared/s3_utils.py` - S3/R2 helper functions
- `shared/redis_client.py` - Caching (optional, not deployed)

**Used by**:
- ✅ `opus-download` (Node.js Lambda - has its own utilities)
- ✅ `opus-transcribe` (transcribe-apis)
- ✅ `opus-detect` (detect-clips)
- ✅ `opus-process-clip` (process-clip) - Docker-based, utilities baked in
- ✅ `opus-finalize` (finalize)

**How it works**:
- Attached as a Layer to each Lambda
- Lambdas import with `from shared.logger import get_logger`
- Graceful fallback if Layer not available

**Benefits**:
- ✅ No code duplication across Lambdas
- ✅ Easy updates (update Layer, all Lambdas get new version)
- ✅ Consistent logging, metrics, error handling

---

## 📊 2. CloudWatch Custom Metrics

**What**: Real-time performance monitoring for your video processing pipeline

**Location**: CloudWatch → Metrics → Custom Namespaces → `VideoProcessing`

**Metrics tracked**:
1. **AIAPICall** - Count of AI API calls (Groq, AssemblyAI, Deepgram)
2. **AIAPILatency** - AI API response times (milliseconds)
3. **TranscriptionTime** - Time to transcribe video audio
4. **ClipDetectionTime** - Time to detect viral clips with AI
5. **ClipProcessingTime** - Time to process each clip (crop, subtitles)
6. **ClipsGenerated** - Total number of clips created
7. **VideoProcessingComplete** - Count of successful completions

**How it's used**:
- Each Lambda publishes metrics during execution
- Example: `track_transcription_time(session_id, 12500)` → Creates metric in CloudWatch
- Metrics visible in 1-5 minutes

**Benefits**:
- ✅ Monitor performance bottlenecks
- ✅ Track API usage and costs
- ✅ Set alarms for failures (e.g., if TranscriptionTime > 60s)
- ✅ Identify slow operations

**Dashboard**: Create CloudWatch Dashboard to visualize all metrics in one place

---

## 🗄️ 3. DynamoDB Tables (Session Tracking)

**What**: Real-time session management and progress tracking

**Tables created**:
1. **`prod-video-sessions`** - Tracks video processing sessions
   - Primary key: `session_id`
   - Attributes: `status`, `current_step`, `user_id`, `clips_count`, `created_at`, `updated_at`

2. **`prod-websocket-connections`** - Manages WebSocket connections
   - Primary key: `connection_id`
   - Attributes: `session_id`, `connected_at`, `ttl` (auto-cleanup)

**How it's used**:
- When video uploaded → Create session in DynamoDB
- During processing → Update session status (`transcribing` → `detecting_clips` → `processing` → `completed`)
- WebSocket connections → Store `connection_id` to send real-time updates
- Frontend → Query session status for progress bars

**Benefits**:
- ✅ Track progress of every video
- ✅ Handle concurrent users (DynamoDB auto-scales)
- ✅ Session history for debugging
- ✅ WebSocket connection management

---

## 🌐 4. WebSocket API (Real-time Updates)

**What**: Live dashboard updates without page refresh

**Components**:
- **API Gateway WebSocket API** - Manages connections
- **Lambda handlers** - Handle connect, disconnect, message events
- **Frontend hook** - `useVideoStatus()` in Dashboard.tsx

**How it works**:
1. User opens dashboard → Frontend connects to WebSocket
2. User uploads video → Processing starts
3. Each Lambda publishes updates → `notify_processing_progress(session_id, 20, "Transcribing...")`
4. WebSocket sends message to frontend → Dashboard updates in real-time
5. **Live badge** shows 🟢 Live when processing

**Benefits**:
- ✅ Instant updates (< 1 second latency)
- ✅ No polling needed (saves API calls)
- ✅ Better user experience
- ✅ See progress without refreshing page

**Frontend integration**:
```typescript
const { isConnected, status, progress } = useVideoStatus({
  sessionId: video.sessionId,
  enabled: true
});
```

---

## 🛡️ 5. Circuit Breakers (API Fault Tolerance)

**What**: Automatic retry and failure handling for external APIs

**Protected APIs**:
- **Groq API** - AI clip detection and title generation
- **AssemblyAI** - Transcription fallback
- **Deepgram** - Transcription fallback

**How it works**:
- Wrap API calls with circuit breaker
- If API fails → Automatically retry with exponential backoff
- If API consistently fails → Circuit "opens", skip API calls temporarily
- Fallback to alternative methods (e.g., Groq fails → Use AssemblyAI)

**Example**:
```python
response = groq_circuit_breaker.call(
    lambda: requests.post(url, data=data)
)
```

**Benefits**:
- ✅ Prevent cascading failures
- ✅ Automatic fallback to alternative APIs
- ✅ Graceful degradation (e.g., skip AI titles if API down)
- ✅ No complete pipeline failure from one API issue

---

## 📝 6. Structured JSON Logging

**What**: Professional logs in JSON format for easy querying

**Format**:
```json
{
  "timestamp": "2025-12-27T10:30:45.123Z",
  "level": "INFO",
  "service": "detect-clips",
  "message": "Starting clip detection",
  "session_id": "abc123",
  "user_id": "user456",
  "clip_count": 2
}
```

**Benefits**:
- ✅ Easy to search in CloudWatch Logs Insights
- ✅ Machine-readable for log aggregation
- ✅ Consistent format across all Lambdas
- ✅ Structured context (session_id, user_id, etc.)

**Query example** (CloudWatch Logs Insights):
```
fields @timestamp, message, session_id, clip_count
| filter service = "detect-clips"
| filter level = "ERROR"
| sort @timestamp desc
```

---

## 🗂️ 7. S3 Prefix Sharding (High Throughput)

**What**: Distribute files across 256 prefixes for higher upload/download throughput

**Structure**:
```
opus-clip-videos/
  └── users/
      └── 7a/              ← Hash prefix (00-ff, 256 possibilities)
          └── user123/
              └── session456/
                  ├── original_video.mp4
                  ├── transcript.json
                  └── clips/
                      ├── clip_0_9x16.mp4
                      ├── clip_1_9x16.mp4
```

**How it works**:
- Calculate hash from `user_id`: `hash = md5(user_id)[:2]`
- Use hash as prefix: `users/7a/user123/...`
- S3/R2 distributes load across 256 partitions

**Benefits**:
- ✅ **896,000 requests/sec** (vs 3,500 without sharding)
- ✅ No S3 rate limit issues
- ✅ Supports millions of concurrent users
- ✅ Works with Cloudflare R2 too

**Toggle**: Set `ENABLE_S3_SHARDING=true` in Lambda env vars

---

## 🚫 8. What We DIDN'T Build (Cost Optimization)

**Intentionally skipped to save ~$100/month**:

### ❌ **No VPC (Virtual Private Cloud)**
- All Lambdas run OUTSIDE VPC
- Direct internet access to Cloudflare R2
- **Saves**: ~$32/month (NAT Gateway cost)

### ❌ **No ElastiCache Redis**
- Caching optional, not required for MVP
- **Saves**: ~$50/month (t3.micro Redis)

### ❌ **No VPC Endpoints**
- Not needed since no VPC
- **Saves**: ~$20/month (S3 + DynamoDB endpoints)

**Why this works**:
- Cloudflare R2 is public-facing (accessible without VPC)
- DynamoDB/CloudWatch accessible from Lambda by default
- Redis caching nice-to-have, not required

**Architecture decision**: Internet-facing Lambdas → Zero networking costs

---

## 🏗️ Complete Data Flow

**Step-by-step: How everything works together**

### 1. **User uploads video**
- Frontend → API Gateway → SQS → `opus-download` Lambda
- **DynamoDB**: Create session with status `pending`
- **S3/R2**: Upload video to `{shard}/{user_id}/{session_id}/original_video.mp4`
- **WebSocket**: Notify "Download started"

### 2. **Transcription** (opus-transcribe)
- **Metrics**: Track `TranscriptionTime`, `AIAPICall`, `AIAPILatency`
- **Circuit Breaker**: Try Groq → Fallback to AssemblyAI → Fallback to Deepgram
- **DynamoDB**: Update status to `transcribing`
- **WebSocket**: Notify progress 20%
- **Logging**: Structured JSON logs in CloudWatch

### 3. **Clip Detection** (opus-detect)
- **Metrics**: Track `ClipDetectionTime`, `AIAPICall`
- **Circuit Breaker**: Use Groq with auto-retry
- **DynamoDB**: Update status to `detecting_clips`
- **WebSocket**: Notify progress 40%

### 4. **Clip Processing** (opus-process-clip)
- **Metrics**: Track `ClipProcessingTime` for each clip
- **S3 Sharding**: Save clips to sharded paths
- **DynamoDB**: Update progress
- **WebSocket**: Notify progress 60-90%

### 5. **Finalization** (opus-finalize)
- **Metrics**: Track `ClipsGenerated`, `VideoProcessingComplete`
- **DynamoDB**: Update status to `completed`, set `clips_count`
- **WebSocket**: Notify "Processing complete" → 🟢 Live badge disappears
- **Logging**: Final summary in structured JSON

### 6. **User sees results**
- Dashboard auto-updates (no refresh needed)
- All metrics visible in CloudWatch
- Session history in DynamoDB
- Videos in R2 with sharded paths

---

## 📊 Infrastructure Overview

| Component | Purpose | Benefit | Cost (Year 1) |
|-----------|---------|---------|---------------|
| Lambda Layer | Shared code | No duplication | Free |
| CloudWatch Metrics | Monitoring | Track performance | $0.30/month |
| DynamoDB | Session tracking | Concurrent users | Free tier |
| WebSocket API | Real-time updates | Instant feedback | $1/million messages |
| Circuit Breakers | Fault tolerance | No downtime | Free (code-level) |
| JSON Logging | Debugging | Easy troubleshooting | Free |
| S3 Sharding | High throughput | 896K req/sec | Free |
| **TOTAL** | - | Production-ready | **$5-29/month** |

**After Year 1**: $67-122/month (still very cost-effective)

---

## 🎯 Why This Architecture?

**Scalability**:
- ✅ Handle 1,000+ concurrent users
- ✅ 896,000 S3 operations/sec
- ✅ Auto-scaling Lambdas and DynamoDB

**Reliability**:
- ✅ Circuit breakers prevent cascading failures
- ✅ Multiple API fallbacks (Groq → AssemblyAI → Deepgram)
- ✅ Retry logic for transient errors

**Observability**:
- ✅ Custom metrics for every operation
- ✅ Structured logs for easy debugging
- ✅ Real-time progress tracking

**Cost-Effective**:
- ✅ No VPC = No NAT Gateway costs
- ✅ No Redis = No cache server costs
- ✅ Serverless = Pay only for usage

**Developer Experience**:
- ✅ Shared utilities = No code duplication
- ✅ Lambda Layer = Easy updates
- ✅ Graceful fallbacks = Simple to test

---

## 📚 Key Files

**Infrastructure**:
- `shared-utilities-layer.zip` - Lambda Layer (18MB)
- `COMPLETE_SCALABILITY_DEPLOYMENT_GUIDE.md` - Full setup guide
- `CLOUDFLARE_R2_DEPLOYMENT_GUIDE.md` - R2 configuration

**Lambda Functions**:
- `node-download/index.js` - Download Lambda (Node.js)
- `transcribe-apis/lambda_function.py` - Transcription
- `detect-clips/lambda_function.py` - Clip detection
- `process-clip/lambda_function.py` - Clip processing (Docker)
- `finalize/lambda_function.py` - Finalization

**Shared Utilities**:
- `shared/logger.py` - Structured logging
- `shared/metrics.py` - CloudWatch metrics
- `shared/circuit_breaker.py` - Fault tolerance
- `shared/dynamodb_client.py` - Session management
- `shared/websocket_notifier.py` - Real-time updates
- `shared/s3_utils.py` - S3/R2 helpers

---

## ✅ Success Criteria

**Your application is production-ready when**:
1. ✅ All 7 CloudWatch metrics showing data
2. ✅ WebSocket Live badge working in dashboard
3. ✅ End-to-end video processing completes successfully
4. ✅ Concurrent users can upload without conflicts
5. ✅ API failures gracefully fallback
6. ✅ Monthly cost under $30 (Year 1)

**Next**: See `SCALABILITY_TESTING_GUIDE.md` for complete testing checklist.
