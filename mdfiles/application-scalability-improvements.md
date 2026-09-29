# Application Scalability Improvements
## ReframeAI & Opus Clip Cloud

## Executive Summary

This document provides a comprehensive, actionable plan to scale your video processing application to handle multiple concurrent users processing videos simultaneously. It identifies specific bottlenecks in both your frontend (reframe-ai) and backend (opus-clip-cloud) and provides concrete solutions with implementation details.

**Current Architecture:** Serverless (AWS Lambda + Step Functions) with React frontend
**Target:** Support 100+ concurrent users processing videos without degradation

---

## Table of Contents

1. [Critical Scalability Issues](#1-critical-scalability-issues)
2. [Backend Improvements](#2-backend-improvements)
3. [Frontend Improvements](#3-frontend-improvements)
4. [Database & Storage Improvements](#4-database--storage-improvements)
5. [Monitoring & Observability](#5-monitoring--observability)
6. [Implementation Priority](#6-implementation-priority)
7. [Cost Implications](#7-cost-implications)

---

## 1. Critical Scalability Issues

### 1.1 Identified Bottlenecks

| Component | Issue | Impact | Priority |
|-----------|-------|--------|----------|
| **Lambda Concurrency** | 1000 concurrent execution limit (account-wide) | Users get throttled after 30-100 concurrent videos | **CRITICAL** |
| **S3 Prefix Structure** | `users/{user_id}/` prefix limits throughput to 3,500 PUTs/sec | Can't handle 100+ users uploading simultaneously | **HIGH** |
| **No Distributed Queue** | Step Functions orchestrates directly, no backpressure handling | YouTube rate limiting, cascading failures | **HIGH** |
| **No Caching Layer** | All status queries hit S3, slow and expensive | High latency for status checks | **MEDIUM** |
| **Synchronous Polling** | Frontend polls `/status/{session_id}` every few seconds | Wastes API calls, slow feedback | **MEDIUM** |
| **No API Rate Limiting** | API Gateway has no explicit throttling configured | Vulnerable to abuse, cost overruns | **HIGH** |
| **Session Storage Caching** | Frontend caches aggressively in sessionStorage | Stale data across tabs, no invalidation | **MEDIUM** |
| **No Connection Pooling** | Each Lambda creates new external API connections | Slow external API calls, connection exhaustion | **LOW** |

### 1.2 Scalability Targets

| Metric | Current | Target | Solution |
|--------|---------|--------|----------|
| **Concurrent Users** | ~10-30 | 100-500 | Increase Lambda concurrency, add SQS queue |
| **Videos Processed/Hour** | ~50-100 | 500-1000 | Parallel processing with queue |
| **API Response Time (p95)** | ~500ms | < 200ms | Add Redis caching layer |
| **Video Processing Time** | 3-5 min | 2-3 min | Optimize FFmpeg, use faster instances |
| **Cost per Video** | ~$0.10-0.20 | ~$0.08-0.15 | Optimize Lambda memory, caching |

---

## 2. Backend Improvements

### 2.1 Implement SQS Queue for Video Processing

**Problem:** Direct Step Functions invocation from API Gateway has no backpressure handling. When YouTube rate-limits downloads or external APIs throttle, entire workflows fail.

**Solution:** Add SQS queue between API Gateway and Step Functions for controlled processing.

**Implementation:**

#### Step 1: Create SQS Queues

**File:** `opus-clip-cloud/infrastructure/sqs-queues.yml` (new file)

```yaml
Resources:
  VideoProcessingQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: video-processing-queue
      VisibilityTimeout: 900  # 15 minutes (max Lambda duration + buffer)
      MessageRetentionPeriod: 86400  # 24 hours
      ReceiveMessageWaitTimeSeconds: 20  # Long polling
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt VideoProcessingDLQ.Arn
        maxReceiveCount: 3  # After 3 failures, move to DLQ

  VideoProcessingDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: video-processing-dlq
      MessageRetentionPeriod: 1209600  # 14 days

  UploadProcessingQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: upload-processing-queue
      VisibilityTimeout: 900
      MessageRetentionPeriod: 86400
      ReceiveMessageWaitTimeSeconds: 20
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt UploadProcessingDLQ.Arn
        maxReceiveCount: 3

  UploadProcessingDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: upload-processing-dlq
      MessageRetentionPeriod: 1209600
```

#### Step 2: Update API Gateway to Send to Queue

**File:** `opus-clip-cloud/src/api-gateway/lambda_function.py`

**Current (Lines ~50-80):**
```python
# Directly invoke Step Functions
response = step_functions.start_execution(
    stateMachineArn=STATE_MACHINE_ARN,
    input=json.dumps(execution_input)
)
```

**Replace with:**
```python
import boto3
import json
import uuid

sqs = boto3.client('sqs')
QUEUE_URL = os.environ['VIDEO_PROCESSING_QUEUE_URL']

def handler_process(event, context):
    # ... existing validation code ...

    # Create queue message
    message = {
        'session_id': session_id,
        'user_id': user_id,
        'youtube_url': youtube_url,
        'template_id': template_id,
        'project_name': project_name,
        'startFrom': startFrom,
        'created_at': datetime.utcnow().isoformat()
    }

    # Send to SQS instead of Step Functions
    response = sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message),
        MessageDeduplicationId=session_id,  # For FIFO queue (optional)
        MessageAttributes={
            'user_id': {'StringValue': user_id, 'DataType': 'String'},
            'priority': {'StringValue': 'normal', 'DataType': 'String'}
        }
    )

    # Return immediately (don't wait for processing)
    return {
        'statusCode': 202,  # Accepted
        'body': json.dumps({
            'session_id': session_id,
            'status': 'queued',  # New status
            'message': 'Video queued for processing',
            'queue_position': get_approximate_queue_depth()  # Optional
        })
    }
```

#### Step 3: Create Queue Consumer Lambda

**File:** `opus-clip-cloud/src/queue-consumer/lambda_function.py` (new file)

```python
import boto3
import json
import os

step_functions = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

def lambda_handler(event, context):
    """
    Consumes messages from SQS and triggers Step Functions.
    Lambda is triggered by SQS event source mapping.
    """
    successful_messages = []
    failed_messages = []

    for record in event['Records']:
        try:
            message = json.loads(record['body'])
            session_id = message['session_id']

            # Start Step Functions execution
            response = step_functions.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=session_id,  # Unique execution name
                input=json.dumps(message)
            )

            print(f"Started execution for session {session_id}: {response['executionArn']}")
            successful_messages.append(record['messageId'])

        except Exception as e:
            print(f"Error processing message {record['messageId']}: {str(e)}")
            failed_messages.append(record['messageId'])

    # Return batch item failures (SQS will retry only failed messages)
    return {
        'batchItemFailures': [
            {'itemIdentifier': msg_id} for msg_id in failed_messages
        ]
    }
```

**Configuration:**
- **Batch Size:** 10 (process 10 videos in parallel per invocation)
- **Batch Window:** 5 seconds (wait up to 5s to collect batch)
- **Concurrency:** 10 reserved concurrency (max 10 concurrent consumers)
- **Error Handling:** Return failed message IDs for retry

#### Step 4: Update Environment Variables

Add to all relevant Lambdas:
```bash
VIDEO_PROCESSING_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456/video-processing-queue
UPLOAD_PROCESSING_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456/upload-processing-queue
```

**Benefits:**
- Controlled processing rate (prevent YouTube rate limiting)
- Automatic retries with exponential backoff
- Dead letter queue for failed jobs
- Queue depth metrics for auto-scaling
- Decouples API from processing (faster response)

---

### 2.2 Increase Lambda Concurrency & Add Reserved Concurrency

**Problem:** Default AWS account limit is 1000 concurrent Lambda executions. With 10 clips processed in parallel per video, you can only handle 100 videos simultaneously. After that, users get throttled.

**Solution:** Request AWS quota increase and configure reserved concurrency for critical functions.

#### Step 1: Request AWS Quota Increase

1. Go to AWS Service Quotas console
2. Search for "Lambda concurrent executions"
3. Request increase to **5,000 concurrent executions**
4. Justification: "Video processing application scaling to support 500+ concurrent users"

#### Step 2: Set Reserved Concurrency for Critical Functions

**File:** Update Lambda function configurations (CloudFormation/Terraform)

```yaml
Resources:
  ProcessClipFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: process-clip
      ReservedConcurrentExecutions: 200  # Reserve 200 for clip processing
      # ... other properties ...

  TranscribeFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: transcribe
      ReservedConcurrentExecutions: 50  # Reserve 50 for transcription
      # ... other properties ...

  ApiGatewayFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: api-gateway
      ReservedConcurrentExecutions: 100  # Reserve 100 for API requests
      # ... other properties ...
```

**Allocation Strategy:**
- **process-clip:** 200 (highest concurrency need, 10 clips × 20 videos)
- **transcribe:** 50 (one per video, long-running)
- **detect-clips:** 50 (one per video, CPU-intensive)
- **download:** 50 (one per video, I/O-bound)
- **api-gateway:** 100 (handles all API requests)
- **Other functions:** Unreserved pool (shared 4,550)

#### Step 3: Optimize Lambda Memory for Cost/Performance

**File:** `opus-clip-cloud/src/process-clip/lambda_function.py`

**Current Memory:** 4096 MB (4 GB)

**Test Configurations:**
Run load tests with different memory configs and measure:
- Execution time
- Cost per invocation
- CPU utilization

**Recommended Testing:**
```bash
# Test with 3 GB (current is 4 GB)
aws lambda update-function-configuration \
  --function-name process-clip \
  --memory-size 3072

# Monitor CloudWatch metrics for 24 hours
# If execution time increases < 20%, keep 3 GB (25% cost savings)
```

**Likely Optimal Configuration:**
- **download:** 2048 MB (2 GB) - I/O-bound, less memory needed
- **transcribe:** 3072 MB (3 GB) - CPU-bound, more memory = faster
- **detect-clips:** 2048 MB (2 GB) - API calls, less memory
- **process-clip:** 3072 MB (3 GB) - FFmpeg, balance cost/speed

---

### 2.3 Add Redis Cache for Session State

**Problem:** Every `/status/{session_id}` and `/result/{session_id}` request reads from S3, which is slow (100-200ms latency) and expensive at scale.

**Solution:** Add ElastiCache Redis cluster for fast session state lookups.

#### Step 1: Create ElastiCache Redis Cluster

**File:** `opus-clip-cloud/infrastructure/redis.yml` (new file)

```yaml
Resources:
  VideoProcessingCache:
    Type: AWS::ElastiCache::CacheCluster
    Properties:
      CacheNodeType: cache.t3.micro  # Start small, scale up
      Engine: redis
      NumCacheNodes: 1
      Port: 6379
      VpcSecurityGroupIds:
        - !Ref CacheSecurityGroup

  CacheSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Allow Lambda access to Redis
      VpcId: !Ref VpcId
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 6379
          ToPort: 6379
          SourceSecurityGroupId: !Ref LambdaSecurityGroup
```

#### Step 2: Update Lambdas to Use Redis

**File:** `opus-clip-cloud/src/api-gateway/lambda_function.py`

Add Redis client (requires Lambda VPC configuration):

```python
import redis
import os
import json

# Redis connection (reuse across invocations)
redis_client = None

def get_redis_client():
    global redis_client
    if redis_client is None:
        redis_client = redis.Redis(
            host=os.environ['REDIS_ENDPOINT'],
            port=6379,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )
    return redis_client

def handler_status(event, context):
    session_id = event['pathParameters']['session_id']
    cache = get_redis_client()

    # Check cache first
    cached_status = cache.get(f"status:{session_id}")
    if cached_status:
        print(f"Cache HIT for session {session_id}")
        return {
            'statusCode': 200,
            'body': cached_status  # Already JSON string
        }

    # Cache miss - query Step Functions
    print(f"Cache MISS for session {session_id}")
    response = step_functions.describe_execution(
        executionArn=get_execution_arn(session_id)
    )

    status_data = {
        'session_id': session_id,
        'status': response['status'],
        'start_time': response['startDate'].isoformat()
    }

    # Cache for 30 seconds (status changes frequently)
    cache.setex(
        f"status:{session_id}",
        30,  # TTL: 30 seconds
        json.dumps(status_data)
    )

    return {
        'statusCode': 200,
        'body': json.dumps(status_data)
    }

def handler_result(event, context):
    session_id = event['pathParameters']['session_id']
    cache = get_redis_client()

    # Check cache first
    cached_result = cache.get(f"result:{session_id}")
    if cached_result:
        print(f"Cache HIT for result {session_id}")
        return {
            'statusCode': 200,
            'body': cached_result
        }

    # Cache miss - fetch from S3
    print(f"Cache MISS for result {session_id}")
    result = fetch_result_from_s3(session_id)

    # Cache for 1 hour (results are immutable once completed)
    cache.setex(
        f"result:{session_id}",
        3600,  # TTL: 1 hour
        json.dumps(result)
    )

    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }
```

#### Step 3: Update Finalize Lambda to Populate Cache

**File:** `opus-clip-cloud/src/finalize/lambda_function.py`

```python
def lambda_handler(event, context):
    # ... existing result generation code ...

    # Write result to S3 (existing)
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"{s3_prefix}/result.json",
        Body=json.dumps(result)
    )

    # NEW: Populate Redis cache
    cache = get_redis_client()
    cache.setex(
        f"result:{session_id}",
        3600,  # 1 hour TTL
        json.dumps(result)
    )

    print(f"Cached result for session {session_id}")

    return result
```

**Benefits:**
- 95%+ cache hit rate after warmup
- Latency: 200ms → 10ms (20x faster)
- Cost: Reduces S3 GET requests by 95%
- Auto-expiring keys (no manual cleanup)

#### Step 4: Add Cache Invalidation on Updates

When user reprocesses clip with new template:

**File:** `opus-clip-cloud/src/reprocess-clip/lambda_function.py`

```python
def lambda_handler(event, context):
    # ... reprocessing logic ...

    # Invalidate cache after reprocessing
    cache = get_redis_client()
    cache.delete(f"result:{session_id}")
    cache.delete(f"status:{session_id}")

    print(f"Invalidated cache for session {session_id}")
```

---

### 2.4 Implement API Rate Limiting

**Problem:** No rate limiting on API Gateway. Users can spam endpoints, causing cost overruns and potential abuse.

**Solution:** Configure API Gateway throttling and per-user rate limits.

#### Step 1: Set API Gateway Throttling

**File:** Update API Gateway configuration

```yaml
Resources:
  VideoProcessingAPI:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      Name: video-processing-api
      ProtocolType: HTTP
      # Add throttling settings
      ThrottleSettings:
        BurstLimit: 5000  # Max requests in burst
        RateLimit: 2000   # Requests per second

  # Per-route throttling
  ProcessRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties:
      ApiId: !Ref VideoProcessingAPI
      RouteKey: POST /process
      # More conservative for expensive operations
      ThrottleSettings:
        BurstLimit: 100
        RateLimit: 50  # Max 50 video submissions/sec
```

#### Step 2: Implement Per-User Rate Limiting in Lambda

**File:** `opus-clip-cloud/src/api-gateway/lambda_function.py`

```python
import time

def check_rate_limit(user_id, action):
    """
    Check if user has exceeded rate limit using Redis.

    Rate limits:
    - /process: 10 videos/hour for free, 100/hour for pro
    - /status: 100 requests/minute
    - /result: 100 requests/minute
    """
    cache = get_redis_client()

    # Define rate limits by action and plan
    rate_limits = {
        'process': {
            'free': (10, 3600),      # 10 per hour
            'starter': (50, 3600),   # 50 per hour
            'pro': (200, 3600)       # 200 per hour
        },
        'status': {
            'all': (100, 60)         # 100 per minute
        },
        'result': {
            'all': (100, 60)         # 100 per minute
        }
    }

    # Get user plan from cache or database
    user_plan = get_user_plan(user_id)  # 'free', 'starter', 'pro'

    # Get rate limit for this action
    if action in rate_limits:
        if user_plan in rate_limits[action]:
            limit, window = rate_limits[action][user_plan]
        else:
            limit, window = rate_limits[action]['all']
    else:
        return True  # No limit for this action

    # Redis key for rate limiting (sliding window)
    key = f"ratelimit:{user_id}:{action}"

    # Increment counter
    current_count = cache.incr(key)

    # Set expiry on first request in window
    if current_count == 1:
        cache.expire(key, window)

    # Check if limit exceeded
    if current_count > limit:
        ttl = cache.ttl(key)
        raise Exception(f"Rate limit exceeded. Try again in {ttl} seconds.")

    return True

def handler_process(event, context):
    user_id = event['requestContext']['authorizer']['lambda']['userId']

    # Check rate limit before processing
    try:
        check_rate_limit(user_id, 'process')
    except Exception as e:
        return {
            'statusCode': 429,  # Too Many Requests
            'headers': {
                'Retry-After': '3600',
                'X-RateLimit-Limit': '10',
                'X-RateLimit-Remaining': '0'
            },
            'body': json.dumps({
                'error': str(e),
                'message': 'Upgrade to Pro plan for higher limits'
            })
        }

    # ... continue with normal processing ...
```

**Benefits:**
- Prevents abuse and cost overruns
- Fair resource allocation across users
- Encourages upgrades to paid plans
- Standard HTTP 429 response

---

### 2.5 Optimize S3 Prefix Structure for Higher Throughput

**Problem:** Current structure `users/{user_id}/{session_id}/` can hit S3 throughput limit of 3,500 PUTs/sec per prefix when many users upload simultaneously.

**Solution:** Add hash-based prefix sharding.

#### Step 1: Update S3 Key Generation

**File:** `opus-clip-cloud/src/shared/s3_utils.py` (new file)

```python
import hashlib

def get_s3_prefix(user_id, session_id):
    """
    Generate S3 prefix with hash-based sharding for higher throughput.

    Structure: users/{hash_prefix}/{user_id}/{session_id}/

    Example:
      user_id = "user123"
      hash = md5("user123") = "a1b2c3d4..."
      hash_prefix = "a1"  (first 2 chars)
      prefix = "users/a1/user123/session456/"

    This distributes load across 256 prefixes (16^2) instead of 1.
    Throughput: 3,500 PUTs/sec → 896,000 PUTs/sec
    """
    # Hash user_id to get consistent prefix
    hash_object = hashlib.md5(user_id.encode())
    hash_hex = hash_object.hexdigest()

    # Use first 2 characters as shard key (256 possible values)
    shard_prefix = hash_hex[:2]

    # Full prefix
    prefix = f"users/{shard_prefix}/{user_id}/{session_id}"

    return prefix

# Usage in Lambda functions
s3_key = f"{get_s3_prefix(user_id, session_id)}/original_video.mp4"
```

#### Step 2: Update All Lambdas to Use New Prefix

**Files to Update:**
- `src/download/lambda_function.py`
- `src/node-upload/index.js`
- `src/process-clip/lambda_function.py`
- `src/reprocess-clip/lambda_function.py`
- `src/finalize/lambda_function.py`

**Example (download Lambda):**

**Before:**
```python
s3_key = f"users/{user_id}/{session_id}/original_video.mp4"
```

**After:**
```python
from shared.s3_utils import get_s3_prefix

s3_key = f"{get_s3_prefix(user_id, session_id)}/original_video.mp4"
```

#### Step 3: Add Backwards Compatibility

Support both old and new prefix structures during migration:

```python
def get_result_from_s3(user_id, session_id):
    """
    Try new prefix first, fallback to old prefix for backwards compatibility.
    """
    # Try new prefix (with hash)
    new_key = f"{get_s3_prefix(user_id, session_id)}/result.json"
    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=new_key)
        return json.loads(obj['Body'].read())
    except s3.exceptions.NoSuchKey:
        pass

    # Fallback to old prefix (without hash)
    old_key = f"users/{user_id}/{session_id}/result.json"
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=old_key)
    return json.loads(obj['Body'].read())
```

**Benefits:**
- S3 throughput: 3,500 → 896,000 PUTs/sec (256x improvement)
- No hot prefix issues
- Supports 1000+ concurrent uploads
- Backwards compatible with existing data

---

### 2.6 Add Circuit Breaker for External APIs

**Problem:** When Groq API or YouTube is down/rate-limited, requests fail immediately and retry indefinitely, wasting resources.

**Solution:** Implement circuit breaker pattern to fail fast and fallback gracefully.

#### Implementation

**File:** `opus-clip-cloud/src/shared/circuit_breaker.py` (new file)

```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = 1   # Normal operation
    OPEN = 2     # Failing, reject requests immediately
    HALF_OPEN = 3  # Testing if service recovered

class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60, success_threshold=2):
        """
        Circuit breaker for external API calls.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before trying again (OPEN → HALF_OPEN)
            success_threshold: Consecutive successes needed to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""

        # If circuit is OPEN, check if timeout has passed
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                print("Circuit breaker: OPEN → HALF_OPEN (testing)")
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"Circuit breaker OPEN (service unavailable)")

        try:
            # Call the function
            result = func(*args, **kwargs)

            # Success
            self.on_success()
            return result

        except Exception as e:
            # Failure
            self.on_failure()
            raise e

    def on_success(self):
        """Handle successful call."""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                print("Circuit breaker: HALF_OPEN → CLOSED (recovered)")
                self.state = CircuitState.CLOSED
                self.success_count = 0

    def on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.success_count = 0

        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                print(f"Circuit breaker: {self.state} → OPEN (too many failures)")
                self.state = CircuitState.OPEN

# Global circuit breakers (reused across Lambda invocations)
groq_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=30)
youtube_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
```

#### Usage in Transcribe Lambda

**File:** `opus-clip-cloud/src/transcribe/lambda_function.py`

```python
from shared.circuit_breaker import groq_circuit_breaker

def transcribe_with_groq(audio_path):
    """Transcribe audio using Groq API with circuit breaker."""
    try:
        return groq_circuit_breaker.call(_transcribe_groq_internal, audio_path)
    except Exception as e:
        if "Circuit breaker OPEN" in str(e):
            print("Groq API unavailable, falling back to AssemblyAI")
            return transcribe_with_assemblyai(audio_path)
        raise e

def _transcribe_groq_internal(audio_path):
    """Internal function that makes actual API call."""
    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        files={"file": open(audio_path, "rb")},
        data={"model": "whisper-large-v3"}
    )
    response.raise_for_status()
    return response.json()
```

**Benefits:**
- Fails fast when service is down (saves time and money)
- Automatic recovery detection
- Graceful fallback to alternative services
- Reduces cascading failures

---

### 2.7 Add CloudWatch Alarms & Monitoring

**Problem:** No proactive monitoring. Issues discovered by users, not operators.

**Solution:** Add CloudWatch alarms for critical metrics.

**File:** `opus-clip-cloud/infrastructure/alarms.yml` (new file)

```yaml
Resources:
  HighErrorRateAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: video-processing-high-error-rate
      AlarmDescription: Alert when error rate > 5%
      MetricName: Errors
      Namespace: AWS/Lambda
      Statistic: Sum
      Period: 300  # 5 minutes
      EvaluationPeriods: 2
      Threshold: 5
      ComparisonOperator: GreaterThanThreshold
      TreatMissingData: notBreaching
      AlarmActions:
        - !Ref SNSAlertTopic

  LambdaThrottlingAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: lambda-throttling-detected
      AlarmDescription: Alert when Lambda functions are throttled
      MetricName: Throttles
      Namespace: AWS/Lambda
      Statistic: Sum
      Period: 60  # 1 minute
      EvaluationPeriods: 1
      Threshold: 10
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref SNSAlertTopic

  HighLatencyAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: api-gateway-high-latency
      AlarmDescription: Alert when p95 latency > 3 seconds
      MetricName: Latency
      Namespace: AWS/ApiGateway
      ExtendedStatistic: p95
      Period: 300
      EvaluationPeriods: 2
      Threshold: 3000  # 3 seconds in ms
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref SNSAlertTopic

  QueueDepthAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: sqs-queue-depth-high
      AlarmDescription: Alert when queue depth > 100 (backlog building)
      MetricName: ApproximateNumberOfMessagesVisible
      Namespace: AWS/SQS
      Statistic: Average
      Period: 300
      EvaluationPeriods: 2
      Threshold: 100
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref SNSAlertTopic

  SNSAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: video-processing-alerts
      Subscription:
        - Endpoint: your-email@example.com
          Protocol: email
```

---

## 3. Frontend Improvements

### 3.1 Replace Polling with WebSocket for Real-Time Updates

**Problem:** Frontend polls `/status/{session_id}` every 3-5 seconds, wasting API calls and adding latency.

**Solution:** Use WebSocket (AWS API Gateway WebSocket API) for real-time status updates.

#### Step 1: Create WebSocket API Gateway

**File:** `opus-clip-cloud/infrastructure/websocket-api.yml` (new file)

```yaml
Resources:
  VideoStatusWebSocket:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      Name: video-status-websocket
      ProtocolType: WEBSOCKET
      RouteSelectionExpression: "$request.body.action"

  ConnectRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties:
      ApiId: !Ref VideoStatusWebSocket
      RouteKey: $connect
      AuthorizationType: NONE
      Target: !Sub integrations/${ConnectIntegration}

  DisconnectRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties:
      ApiId: !Ref VideoStatusWebSocket
      RouteKey: $disconnect
      Target: !Sub integrations/${DisconnectIntegration}

  SubscribeRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties:
      ApiId: !Ref VideoStatusWebSocket
      RouteKey: subscribe
      Target: !Sub integrations/${SubscribeIntegration}
```

#### Step 2: Create WebSocket Handler Lambda

**File:** `opus-clip-cloud/src/websocket-handler/lambda_function.py` (new file)

```python
import boto3
import json

dynamodb = boto3.resource('dynamodb')
connections_table = dynamodb.Table('websocket-connections')

def lambda_handler(event, context):
    route_key = event['requestContext']['routeKey']
    connection_id = event['requestContext']['connectionId']

    if route_key == '$connect':
        return handle_connect(connection_id)
    elif route_key == '$disconnect':
        return handle_disconnect(connection_id)
    elif route_key == 'subscribe':
        return handle_subscribe(connection_id, event)

    return {'statusCode': 400, 'body': 'Unknown route'}

def handle_connect(connection_id):
    """Store connection in DynamoDB."""
    connections_table.put_item(
        Item={
            'connection_id': connection_id,
            'connected_at': int(time.time())
        }
    )
    return {'statusCode': 200, 'body': 'Connected'}

def handle_disconnect(connection_id):
    """Remove connection from DynamoDB."""
    connections_table.delete_item(
        Key={'connection_id': connection_id}
    )
    return {'statusCode': 200, 'body': 'Disconnected'}

def handle_subscribe(connection_id, event):
    """Subscribe to status updates for a session."""
    body = json.loads(event['body'])
    session_id = body['session_id']

    # Update connection with session_id
    connections_table.update_item(
        Key={'connection_id': connection_id},
        UpdateExpression='SET session_id = :sid',
        ExpressionAttributeValues={':sid': session_id}
    )

    return {'statusCode': 200, 'body': 'Subscribed'}
```

#### Step 3: Update Finalize Lambda to Push Updates

**File:** `opus-clip-cloud/src/finalize/lambda_function.py`

```python
import boto3

apigateway_management = boto3.client('apigatewaymanagementapi', endpoint_url='https://your-websocket-id.execute-api.us-east-1.amazonaws.com/prod')

def notify_websocket_clients(session_id, status_update):
    """Push status update to all connected WebSocket clients."""
    # Query DynamoDB for connections subscribed to this session
    response = connections_table.query(
        IndexName='session_id-index',
        KeyConditionExpression='session_id = :sid',
        ExpressionAttributeValues={':sid': session_id}
    )

    for item in response['Items']:
        connection_id = item['connection_id']
        try:
            # Push update to client
            apigateway_management.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(status_update).encode('utf-8')
            )
        except apigateway_management.exceptions.GoneException:
            # Client disconnected, remove from table
            connections_table.delete_item(Key={'connection_id': connection_id})

def lambda_handler(event, context):
    # ... existing finalize logic ...

    # Push real-time update
    notify_websocket_clients(session_id, {
        'event': 'processing_complete',
        'session_id': session_id,
        'status': 'completed',
        'clips': result['clips']
    })

    return result
```

#### Step 4: Update Frontend to Use WebSocket

**File:** `reframe-ai/src/lib/websocket.ts` (new file)

```typescript
export class VideoStatusWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(
    private url: string,
    private onMessage: (data: any) => void,
    private onError?: (error: Event) => void
  ) {}

  connect(sessionId: string) {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;

      // Subscribe to session updates
      this.ws?.send(JSON.stringify({
        action: 'subscribe',
        session_id: sessionId
      }));
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.onMessage(data);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.onError?.(error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket closed');
      this.reconnect(sessionId);
    };
  }

  private reconnect(sessionId: string) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000);
      setTimeout(() => this.connect(sessionId), delay);
    }
  }

  disconnect() {
    this.ws?.close();
    this.ws = null;
  }
}
```

**File:** `reframe-ai/src/pages/ProjectDetails.tsx`

**Replace polling logic with WebSocket:**

**Before (polling):**
```typescript
useEffect(() => {
  const interval = setInterval(() => {
    refetch(); // Poll every 5 seconds
  }, 5000);
  return () => clearInterval(interval);
}, []);
```

**After (WebSocket):**
```typescript
import { VideoStatusWebSocket } from '../lib/websocket';

const ws = useRef<VideoStatusWebSocket | null>(null);

useEffect(() => {
  ws.current = new VideoStatusWebSocket(
    'wss://your-websocket-id.execute-api.us-east-1.amazonaws.com/prod',
    (data) => {
      // Real-time update received
      if (data.event === 'processing_complete') {
        queryClient.invalidateQueries(['video', sessionId]);
        toast.success('Video processing complete!');
      }
    }
  );

  ws.current.connect(sessionId);

  return () => ws.current?.disconnect();
}, [sessionId]);
```

**Benefits:**
- Real-time updates (0 latency vs 2.5s average with polling)
- 90% reduction in API calls
- Better user experience (instant feedback)
- Lower costs (fewer Lambda invocations)

---

### 3.2 Add Pagination to Video Lists

**Problem:** `Dashboard.tsx` and `Projects.tsx` load all videos at once with `useVideos()` hook. As users accumulate 100s of videos, page becomes slow.

**Solution:** Implement cursor-based pagination.

#### Step 1: Update Backend API

**File:** `opus-clip-cloud/src/api-gateway/lambda_function.py`

```python
def handler_user_videos(event, context):
    """
    List user videos with pagination.

    Query params:
      - limit: Number of videos per page (default: 20, max: 100)
      - cursor: Pagination cursor (base64-encoded last video ID)
      - status: Filter by status (optional)
    """
    user_id = event['requestContext']['authorizer']['lambda']['userId']
    query_params = event.get('queryStringParameters', {}) or {}

    limit = min(int(query_params.get('limit', 20)), 100)
    cursor = query_params.get('cursor')
    status_filter = query_params.get('status')

    # Decode cursor to get last video ID
    start_after = None
    if cursor:
        start_after = base64.b64decode(cursor).decode('utf-8')

    # Query S3 or DynamoDB for user videos
    videos = query_user_videos(
        user_id=user_id,
        limit=limit + 1,  # Fetch one extra to check if there are more
        start_after=start_after,
        status=status_filter
    )

    # Check if there are more videos
    has_more = len(videos) > limit
    if has_more:
        videos = videos[:limit]

    # Generate next cursor
    next_cursor = None
    if has_more:
        last_video_id = videos[-1]['session_id']
        next_cursor = base64.b64encode(last_video_id.encode('utf-8')).decode('utf-8')

    return {
        'statusCode': 200,
        'body': json.dumps({
            'videos': videos,
            'pagination': {
                'has_more': has_more,
                'next_cursor': next_cursor,
                'limit': limit
            }
        })
    }
```

#### Step 2: Update Frontend Hook

**File:** `reframe-ai/src/hooks/useVideos.ts`

**Replace with paginated version:**

```typescript
import { useInfiniteQuery } from '@tanstack/react-query';

export function useVideosPaginated(limit = 20) {
  return useInfiniteQuery({
    queryKey: ['videos-paginated', limit],
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams({
        limit: limit.toString(),
        ...(pageParam && { cursor: pageParam })
      });

      const response = await apiClient.get(`/user/videos?${params}`);
      return response;
    },
    getNextPageParam: (lastPage) => {
      return lastPage.pagination.has_more
        ? lastPage.pagination.next_cursor
        : undefined;
    },
    initialPageParam: undefined,
    staleTime: 5 * 60 * 1000  // 5 minutes
  });
}
```

#### Step 3: Update Dashboard Component

**File:** `reframe-ai/src/pages/Dashboard.tsx`

```typescript
import { useVideosPaginated } from '../hooks/useVideos';

export default function Dashboard() {
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading
  } = useVideosPaginated(20);

  // Flatten pages into single array
  const videos = data?.pages.flatMap(page => page.videos) ?? [];

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {videos.map(video => (
          <VideoCard key={video.session_id} video={video} />
        ))}
      </div>

      {/* Infinite scroll trigger */}
      {hasNextPage && (
        <div className="mt-8 text-center">
          <Button
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? 'Loading...' : 'Load More'}
          </Button>
        </div>
      )}

      {/* Or use Intersection Observer for auto-load */}
      <div ref={observerTarget} className="h-10" />
    </div>
  );
}
```

**Benefits:**
- Fast initial page load (20 videos vs 100+)
- Smooth infinite scroll
- Reduced memory usage
- Better mobile performance

---

### 3.3 Optimize Cache Strategy in apiClient.ts

**Problem:** Aggressive sessionStorage caching with no invalidation can show stale data, especially for video status updates.

**Solution:** Implement smarter cache with TTL and invalidation.

**File:** `reframe-ai/src/lib/apiClient.ts`

**Current implementation (Lines ~50-100):**

```typescript
// Check sessionStorage first
const cachedData = sessionStorage.getItem(cacheKey);
if (cachedData && !skipCache) {
  return JSON.parse(cachedData);
}
```

**Replace with TTL-based caching:**

```typescript
interface CacheEntry {
  data: any;
  timestamp: number;
  ttl: number; // Time to live in milliseconds
}

class APIClient {
  // ... existing code ...

  private getCacheKey(url: string, options?: RequestInit): string {
    return `api_cache:${url}:${options?.method || 'GET'}`;
  }

  private getFromCache(cacheKey: string): any | null {
    try {
      const cachedEntry = sessionStorage.getItem(cacheKey);
      if (!cachedEntry) return null;

      const entry: CacheEntry = JSON.parse(cachedEntry);

      // Check if cache is still valid
      const age = Date.now() - entry.timestamp;
      if (age > entry.ttl) {
        sessionStorage.removeItem(cacheKey);
        return null;
      }

      console.log(`Cache HIT: ${cacheKey} (age: ${age}ms)`);
      return entry.data;
    } catch (error) {
      return null;
    }
  }

  private setCache(cacheKey: string, data: any, ttl: number) {
    try {
      const entry: CacheEntry = {
        data,
        timestamp: Date.now(),
        ttl
      };
      sessionStorage.setItem(cacheKey, JSON.stringify(entry));
    } catch (error) {
      console.warn('Failed to cache data:', error);
    }
  }

  async get(url: string, options?: RequestOptions) {
    const cacheKey = this.getCacheKey(url, options);

    // Check cache first
    if (!options?.skipCache) {
      const cached = this.getFromCache(cacheKey);
      if (cached) return cached;
    }

    // Fetch from API
    const data = await this.request(url, { ...options, method: 'GET' });

    // Cache with appropriate TTL
    const ttl = this.getTTLForEndpoint(url);
    this.setCache(cacheKey, data, ttl);

    return data;
  }

  private getTTLForEndpoint(url: string): number {
    // Different TTLs for different endpoints
    if (url.includes('/status/')) return 10 * 1000;      // 10 seconds (frequently changing)
    if (url.includes('/result/')) return 60 * 60 * 1000; // 1 hour (immutable)
    if (url.includes('/user/videos')) return 5 * 60 * 1000; // 5 minutes
    return 5 * 60 * 1000; // Default: 5 minutes
  }

  // Method to invalidate cache
  invalidateCache(pattern: string) {
    const keys = Object.keys(sessionStorage);
    keys.forEach(key => {
      if (key.includes(pattern)) {
        sessionStorage.removeItem(key);
      }
    });
  }
}
```

**Usage in components:**

```typescript
// Invalidate cache after video processing completes
apiClient.invalidateCache(`/user/${userId}/videos`);
apiClient.invalidateCache(`/result/${sessionId}`);
```

**Benefits:**
- No stale data (TTL-based expiration)
- Appropriate caching per endpoint
- Manual cache invalidation when needed
- Still fast (most requests hit cache)

---

### 3.4 Add Request Debouncing for Search/Filter

**Problem:** Every keystroke in search input triggers API call, wasting requests.

**Solution:** Debounce search input.

**File:** `reframe-ai/src/pages/Projects.tsx`

```typescript
import { useMemo, useState } from 'react';
import { debounce } from 'lodash';

export default function Projects() {
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Debounce search updates (wait 300ms after user stops typing)
  const debouncedSearch = useMemo(
    () =>
      debounce((query: string) => {
        setDebouncedQuery(query);
      }, 300),
    []
  );

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value); // Update UI immediately
    debouncedSearch(value); // Debounce API call
  };

  // Use debouncedQuery for API call
  const { data: videos } = useVideos({ search: debouncedQuery });

  return (
    <input
      type="text"
      value={searchQuery}
      onChange={handleSearchChange}
      placeholder="Search videos..."
    />
  );
}
```

**Benefits:**
- 90% fewer API calls during typing
- Better user experience (no lag)
- Lower costs

---

## 4. Database & Storage Improvements

### 4.1 Add DynamoDB for Fast Session Queries

**Problem:** Querying video sessions requires listing S3 objects or reading Firestore, both slow for large datasets.

**Solution:** Add DynamoDB table for fast queries with indexes.

#### Step 1: Create DynamoDB Table

**File:** `opus-clip-cloud/infrastructure/dynamodb.yml` (new file)

```yaml
Resources:
  VideoSessionsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: video-sessions
      BillingMode: PAY_PER_REQUEST  # Auto-scaling
      AttributeDefinitions:
        - AttributeName: user_id
          AttributeType: S
        - AttributeName: session_id
          AttributeType: S
        - AttributeName: created_at
          AttributeType: N
        - AttributeName: status
          AttributeType: S
      KeySchema:
        - AttributeName: user_id
          KeyType: HASH
        - AttributeName: session_id
          KeyType: RANGE
      GlobalSecondaryIndexes:
        # Query by status (admin dashboard)
        - IndexName: status-created_at-index
          KeySchema:
            - AttributeName: status
              KeyType: HASH
            - AttributeName: created_at
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        # Query by user + creation date
        - IndexName: user_id-created_at-index
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
            - AttributeName: created_at
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      TimeToLiveSpecification:
        Enabled: true
        AttributeName: expires_at  # Auto-delete after expiry
```

#### Step 2: Update Lambdas to Write to DynamoDB

**File:** `opus-clip-cloud/src/api-gateway/lambda_function.py`

```python
import boto3
import time

dynamodb = boto3.resource('dynamodb')
sessions_table = dynamodb.Table('video-sessions')

def handler_process(event, context):
    # ... existing validation ...

    # Create DynamoDB record
    sessions_table.put_item(
        Item={
            'user_id': user_id,
            'session_id': session_id,
            'status': 'queued',
            'created_at': int(time.time()),
            'youtube_url': youtube_url,
            'template_id': template_id,
            'project_name': project_name,
            'expires_at': int(time.time()) + (3 * 24 * 3600)  # 3 days TTL
        }
    )

    # Send to SQS (existing code)
    # ...

def handler_user_videos(event, context):
    """Query DynamoDB instead of S3 for fast results."""
    user_id = event['requestContext']['authorizer']['lambda']['userId']

    # Query DynamoDB with pagination
    response = sessions_table.query(
        KeyConditionExpression='user_id = :uid',
        ExpressionAttributeValues={':uid': user_id},
        ScanIndexForward=False,  # Sort by created_at DESC
        Limit=20
    )

    videos = response['Items']

    return {
        'statusCode': 200,
        'body': json.dumps({
            'videos': videos,
            'last_key': response.get('LastEvaluatedKey')
        })
    }
```

#### Step 3: Update Finalize Lambda

**File:** `opus-clip-cloud/src/finalize/lambda_function.py`

```python
def lambda_handler(event, context):
    # ... existing finalize logic ...

    # Update DynamoDB status
    sessions_table.update_item(
        Key={
            'user_id': user_id,
            'session_id': session_id
        },
        UpdateExpression='SET #status = :status, completed_at = :completed, clips_count = :count',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':status': 'completed',
            ':completed': int(time.time()),
            ':count': len(result['clips'])
        }
    )
```

**Benefits:**
- Query latency: 200ms → 10ms (20x faster)
- Efficient indexes for filtering/sorting
- Auto-scaling (pay per request)
- TTL for auto-cleanup

---

### 4.2 Implement S3 Lifecycle Policies

**Problem:** Videos and clips are stored indefinitely, wasting storage costs.

**Solution:** Auto-delete old files with S3 lifecycle policies.

**File:** `opus-clip-cloud/infrastructure/s3-lifecycle.yml` (new file)

```yaml
Resources:
  VideosBucketLifecyclePolicy:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: opus-clip-videos
      LifecycleConfiguration:
        Rules:
          # Delete clips after 3 days
          - Id: DeleteClipsAfter3Days
            Status: Enabled
            Prefix: users/
            ExpirationInDays: 3
            NoncurrentVersionExpirationInDays: 1

          # Move original videos to Glacier after 7 days
          - Id: ArchiveOriginalVideos
            Status: Enabled
            Prefix: users/
            Transitions:
              - TransitionInDays: 7
                StorageClass: GLACIER_IR  # Instant Retrieval

          # Delete everything after 30 days
          - Id: DeleteAfter30Days
            Status: Enabled
            Prefix: users/
            ExpirationInDays: 30
```

**Cost Savings:**
- Storage costs: -70% (Glacier is $0.004/GB vs S3 $0.023/GB)
- Auto-cleanup eliminates manual work

---

## 5. Monitoring & Observability

### 5.1 Add Structured Logging

**Problem:** Logs are unstructured, difficult to query and analyze.

**Solution:** Use structured JSON logging.

**File:** `opus-clip-cloud/src/shared/logger.py` (new file)

```python
import json
import logging
from datetime import datetime

class StructuredLogger:
    def __init__(self, service_name):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(logging.INFO)

    def log(self, level, message, **kwargs):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            'service': self.service_name,
            'message': message,
            **kwargs
        }
        print(json.dumps(log_entry))

    def info(self, message, **kwargs):
        self.log('INFO', message, **kwargs)

    def error(self, message, **kwargs):
        self.log('ERROR', message, **kwargs)

    def warning(self, message, **kwargs):
        self.log('WARNING', message, **kwargs)

# Usage in Lambda functions
logger = StructuredLogger('process-clip')

logger.info(
    'Processing clip',
    session_id=session_id,
    clip_index=clip_index,
    duration_ms=duration
)
```

---

### 5.2 Add Custom CloudWatch Metrics

**File:** `opus-clip-cloud/src/shared/metrics.py` (new file)

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def put_metric(metric_name, value, unit='Count', dimensions=None):
    """Publish custom metric to CloudWatch."""
    cloudwatch.put_metric_data(
        Namespace='VideoProcessing',
        MetricData=[{
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Dimensions': dimensions or [],
            'Timestamp': datetime.utcnow()
        }]
    )

# Usage
put_metric('VideoProcessingTime', duration_ms, unit='Milliseconds')
put_metric('ClipsGenerated', len(clips), dimensions=[
    {'Name': 'TemplateId', 'Value': template_id}
])
```

---

## 6. Implementation Priority

### Phase 1: Critical (Week 1-2)

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Request AWS Lambda concurrency increase to 5,000 | 1 hour | HIGH |
| 2 | Add SQS queue for video processing | 2 days | HIGH |
| 3 | Implement API rate limiting | 1 day | HIGH |
| 4 | Add S3 prefix sharding | 1 day | HIGH |
| 5 | Set up CloudWatch alarms | 4 hours | MEDIUM |

### Phase 2: High Impact (Week 3-4)

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 6 | Add Redis caching layer | 3 days | HIGH |
| 7 | Replace polling with WebSocket | 2 days | MEDIUM |
| 8 | Add pagination to video lists | 2 days | MEDIUM |
| 9 | Optimize apiClient caching | 1 day | MEDIUM |
| 10 | Add DynamoDB for session queries | 2 days | MEDIUM |

### Phase 3: Performance & UX (Week 5-6)

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 11 | Implement circuit breaker pattern | 1 day | MEDIUM |
| 12 | Add request debouncing | 4 hours | LOW |
| 13 | Optimize Lambda memory configurations | 1 day | MEDIUM |
| 14 | Implement S3 lifecycle policies | 2 hours | MEDIUM |
| 15 | Add structured logging | 1 day | LOW |

---

## 7. Cost Implications

### Current Costs (Estimated)

| Service | Usage | Cost/Month |
|---------|-------|------------|
| Lambda (compute) | 100 videos/day, 5 min/video | $150 |
| S3 (storage) | 1 TB stored, 10k PUTs/day | $30 |
| API Gateway | 100k requests/day | $3.50 |
| Step Functions | 100 executions/day | $2.50 |
| Firestore | 100k reads/day | $5 |
| **Total** | | **~$191** |

### After Optimizations (Projected)

| Service | Usage | Cost/Month | Change |
|---------|-------|------------|--------|
| Lambda (compute) | 500 videos/day, 4 min/video | $500 | +233% |
| S3 (storage) | 500 GB (lifecycle cleanup) | $12 | -60% |
| API Gateway | 50k requests/day (caching) | $1.75 | -50% |
| Step Functions | 500 executions/day | $12.50 | +400% |
| ElastiCache Redis | cache.t3.micro | $12 | NEW |
| SQS | 500k messages/day | $0.25 | NEW |
| DynamoDB | 1M reads/day | $1.25 | NEW |
| **Total** | | **~$540** | +183% |

**Cost Analysis:**
- Total cost increases 183% due to 5x more videos processed
- **Cost per video:** $191/100 = $1.91 → $540/500 = $1.08 (-43% per video)
- **ROI:** Better unit economics, supports higher scale

---

## Summary

### Key Changes Required

**Backend (opus-clip-cloud/):**
1. Add SQS queue for controlled processing
2. Increase Lambda concurrency (request AWS)
3. Add Redis caching for session state
4. Implement API rate limiting
5. Shard S3 prefix structure
6. Add circuit breaker for external APIs
7. Replace S3 queries with DynamoDB
8. Set up CloudWatch alarms

**Frontend (reframe-ai/):**
1. Replace polling with WebSocket
2. Add pagination to video lists
3. Optimize cache with TTL
4. Add request debouncing
5. Improve error handling

**Expected Results:**
- Support 100-500 concurrent users (vs 10-30 currently)
- Process 500-1000 videos/hour (vs 50-100)
- API response time < 200ms (vs 500ms)
- 43% lower cost per video
- Real-time updates (vs 2-5 second delay)

---

**Document Version:** 1.0
**Last Updated:** December 26, 2024
