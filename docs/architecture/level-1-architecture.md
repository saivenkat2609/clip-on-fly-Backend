# Level 1 Architecture: Queue-Based Scalable Video Processing

## Overview

**Target Scale**: 100 concurrent users, 2,000-5,000 videos/day
**Complexity**: Low
**Setup Time**: 1-2 days
**Monthly Cost**: ~$55 for 1,000 videos/day

### Key Features
- Asynchronous processing via SQS queue
- Job status tracking with DynamoDB
- Auto-retry on failures
- Reserved concurrency (100 Lambda instances)
- Plugin-based classification (existing system intact)

---

## Architecture Diagram

```
User Request → API Gateway → API Handler Lambda → SQS Queue
                                                      ↓
                                            Process-Clip Lambda
                                                      ↓
                                                  DynamoDB ← Status Handler Lambda
                                                      ↓
                                                    S3/R2
```

---

## Components

### 1. **API Gateway (HTTP API)**
- Endpoints: POST /process, GET /jobs/{job_id}
- CORS enabled
- Request validation

### 2. **API Handler Lambda**
- Validates requests
- Generates job_id
- Sends to SQS
- Returns 202 Accepted immediately
- Memory: 512MB, Timeout: 30s

### 3. **SQS Queue**
- Name: video-processing-queue
- Visibility timeout: 900s
- Message retention: 24 hours
- Dead letter queue: video-processing-dlq

### 4. **Process-Clip Lambda** (Modified)
- SQS trigger (batch size: 1)
- Updates DynamoDB status
- Downloads video → Classify → Process → Upload
- Memory: 3GB, Timeout: 900s
- Reserved concurrency: 100

### 5. **DynamoDB Table (VideoJobs)**
- Schema: job_id (PK), user_id, status, result, error
- TTL enabled (24 hour auto-cleanup)
- On-demand billing

### 6. **Status Handler Lambda**
- GET /jobs/{job_id}
- Queries DynamoDB
- Returns status + results
- Memory: 256MB, Timeout: 10s

---

## Data Flow

### Submit Request
```
1. Client → POST /process (video info)
2. API Handler → Validate & generate job_id
3. API Handler → Send to SQS
4. API Handler → Write to DynamoDB (status: "queued")
5. API Handler → Return {job_id, status_url}
   Total time: ~100ms
```

### Background Processing
```
1. Lambda polls SQS → Receives message
2. Update DynamoDB (status: "processing")
3. Download video from S3/R2
4. Classify with plugin system
5. Process with appropriate strategy
6. Upload result to S3/R2
7. Update DynamoDB (status: "completed" + results)
8. SQS message auto-deleted
   Total time: 21-55 seconds
```

### Check Status
```
1. Client → GET /jobs/{job_id}
2. Status Handler → Query DynamoDB
3. Return {status, result}
   Total time: ~50ms
```

---

## Scaling

- **100 concurrent executions** = ~10,000 videos/hour
- Queue buffers traffic spikes
- Can increase to 1000 concurrent
- Linear cost scaling ($0.002 per video)

---

## Cost Breakdown

Per video: $0.00176
- Lambda: $0.00175
- API Gateway: $0.000002
- SQS: $0.0000004
- DynamoDB: $0.00000375

Monthly (1000 videos/day): ~$55

---

## Deployment

See: `deployment/level-1/` folder
- Terraform: `terraform/`
- Serverless: `serverless/`
- Manual: `manual-setup.md`

---

## Monitoring

**Key Metrics**:
- Queue depth (should be < 100)
- Lambda errors (should be < 1%)
- Processing duration (avg 35s)
- DynamoDB throttles (should be 0)

**Alarms**:
- High queue backlog (> 100 messages)
- High error rate (> 10 in 5 min)
- Lambda throttles (> 0)

---

## When to Upgrade to Level 2

- Concurrent users > 100
- Videos/day > 2,000
- Need faster processing
- Need better fault isolation

See: [Level 2 Architecture](level-2-architecture.md)
