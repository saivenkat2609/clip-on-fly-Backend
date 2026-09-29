# Level 2 Architecture: Parallel Pipeline with Step Functions

## Overview

**Target Scale**: 500 concurrent users, 10,000-50,000 videos/day
**Complexity**: Medium
**Setup Time**: 3-5 days
**Monthly Cost**: ~$86 for 1,000 videos/day

### Key Features
- Parallel feature extraction (3x faster)
- Step Functions orchestration
- Independent Lambda scaling per stage
- Better fault isolation
- Parallel clip processing

---

## Architecture Diagram

```
User Request → API Gateway → Step Functions Execution
                                    ↓
         ┌──────────────────────────┼──────────────────────────┐
         ↓                          ↓                          ↓
   Transcript                   Visual                     Audio
   Extractor                 Extractor                  Extractor
    Lambda                    Lambda                     Lambda
         └──────────────────────────┼──────────────────────────┘
                                    ↓
                             Classify Lambda
                                    ↓
                         ┌──────────┼──────────┐
                         ↓          ↓          ↓
                      Clip 1     Clip 2     Clip 3
                      Lambda     Lambda     Lambda
                         └──────────┼──────────┘
                                    ↓
                             Aggregate Lambda
                                    ↓
                                DynamoDB + S3
```

---

## Components

### 1. **Step Functions State Machine**

Orchestrates the entire pipeline:

```json
{
  "StartAt": "ExtractFeatures",
  "States": {
    "ExtractFeatures": {
      "Type": "Parallel",
      "Branches": [
        {"StartAt": "TranscriptExtraction"},
        {"StartAt": "VisualExtraction"},
        {"StartAt": "AudioExtraction"}
      ],
      "Next": "ClassifyVideo"
    },
    "ClassifyVideo": {
      "Type": "Task",
      "Resource": "classify-lambda",
      "Next": "ProcessClips"
    },
    "ProcessClips": {
      "Type": "Map",
      "ItemsPath": "$.clips",
      "MaxConcurrency": 10,
      "Iterator": {
        "StartAt": "ProcessSingleClip"
      },
      "Next": "AggregateResults"
    },
    "AggregateResults": {
      "Type": "Task",
      "Resource": "aggregate-lambda",
      "End": true
    }
  }
}
```

---

### 2. **Feature Extraction Lambdas (Parallel)**

#### A. Transcript Extractor
- Extracts speech density, patterns, keywords
- Memory: 512MB, Timeout: 60s
- Cost: ~$0.0001 per execution

#### B. Visual Extractor
- Face detection, movement analysis, scene changes
- Memory: 2GB, Timeout: 120s
- Cost: ~$0.0005 per execution

#### C. Audio Extractor
- Music detection, audio classification
- Memory: 1GB, Timeout: 90s
- Cost: ~$0.0003 per execution

**Benefit**: All run simultaneously → 3x faster than sequential

---

### 3. **Classification Lambda**
- Receives combined features
- Runs plugin-based classifiers
- Returns category + processing strategy
- Memory: 1GB, Timeout: 60s

---

### 4. **Clip Processing Lambdas (Parallel)**
- Process multiple clips simultaneously
- Each clip processed independently
- Max concurrency: 10 (configurable)
- Memory: 3GB, Timeout: 600s

---

### 5. **Aggregation Lambda**
- Combines all clip results
- Generates final output
- Updates DynamoDB
- Sends notifications
- Memory: 512MB, Timeout: 60s

---

## Data Flow

### 1. Submit Request
```
Client → API Gateway → Start Step Functions execution
API Gateway → Return {execution_id, status_url}
Time: ~100ms
```

### 2. Feature Extraction (Parallel)
```
Step Functions:
  ├→ Transcript Extractor (1-2s)
  ├→ Visual Extractor (2-3s)
  └→ Audio Extractor (1-2s)

Wait for all three (max of all = 2-3s)
```

### 3. Classification
```
Classify Lambda receives:
  - Transcript features
  - Visual features
  - Audio features

Returns:
  - Category (e.g., "talking_head")
  - Strategy (smart_framing, karaoke, etc.)

Time: 0.5-2s
```

### 4. Clip Processing (Parallel)
```
For each detected clip (1-5 clips):
  Process-Clip Lambda:
    - Download video
    - Apply strategy
    - Process with FFmpeg
    - Upload result

All clips processed simultaneously
Time: 10-30s (same for all clips, not cumulative!)
```

### 5. Aggregation
```
Aggregate Lambda:
  - Combine all clip URLs
  - Update DynamoDB with complete results
  - Send webhook notification (if configured)

Time: 0.5s
```

**Total Pipeline Time**: 15-40 seconds (vs 35-60s in Level 1)

---

## Comparison: Level 1 vs Level 2

| Aspect | Level 1 | Level 2 | Improvement |
|--------|---------|---------|-------------|
| **Feature Extraction** | Sequential (3s) | Parallel (3s max) | Same time, better isolation |
| **Clip Processing** | Sequential per clip | Parallel all clips | 3x faster for 3 clips |
| **Total Time** | 35-60s | 15-40s | ~2x faster |
| **Fault Tolerance** | Medium | High | Per-stage failures isolated |
| **Scalability** | Good | Excellent | Independent scaling |
| **Cost per Video** | $0.00176 | $0.00200 | +14% |
| **Complexity** | Low | Medium | More moving parts |

---

## Scaling Capabilities

### Concurrency

```
Each Lambda stage scales independently:
- Transcript Extractors: Up to 500 concurrent
- Visual Extractors: Up to 500 concurrent
- Audio Extractors: Up to 500 concurrent
- Classifiers: Up to 500 concurrent
- Clip Processors: Up to 1000 concurrent

Total system capacity: 500 videos in pipeline simultaneously
```

### Throughput

```
500 concurrent videos × (3600s / 25s avg) = 72,000 videos/hour
= 1.7 million videos/day
```

---

## Cost Analysis

### Per-Video Breakdown

```
Step Functions: 5 state transitions × $0.025/1000 = $0.000125
Transcript Extractor: $0.0001
Visual Extractor: $0.0005
Audio Extractor: $0.0003
Classification: $0.0002
Clip Processing (3 clips): 3 × $0.00175 = $0.00525
Aggregation: $0.0001
────────────────────────────────────
TOTAL: ~$0.00200 per video
```

### Monthly Cost (1,000 videos/day)

```
Lambda executions: $60
Step Functions: $4
DynamoDB: $0.12
S3: $2.30
API Gateway: $0.002
SQS: $0.012
────────────────────────────────────
TOTAL: ~$66/month
```

### Cost at Scale

| Videos/Day | Monthly Cost | Cost per Video |
|------------|--------------|----------------|
| 1,000      | $66          | $0.00200       |
| 10,000     | $660         | $0.00200       |
| 100,000    | $6,600       | $0.00200       |

---

## Error Handling

### Stage-Level Failures

```json
{
  "Catch": [{
    "ErrorEquals": ["States.ALL"],
    "ResultPath": "$.error",
    "Next": "HandleFailure"
  }]
}
```

**Example**: If Audio Extractor fails:
- Transcript and Visual still succeed
- Classification continues with partial features
- Processing continues with graceful degradation

### Retry Strategy

```json
{
  "Retry": [{
    "ErrorEquals": ["States.TaskFailed"],
    "IntervalSeconds": 2,
    "MaxAttempts": 3,
    "BackoffRate": 2.0
  }]
}
```

---

## Monitoring

### Step Functions Metrics

- **ExecutionsStarted**: Videos entering pipeline
- **ExecutionsSucceeded**: Successfully processed
- **ExecutionsFailed**: Failed videos
- **ExecutionTime**: End-to-end duration

### Lambda Metrics (Per Stage)

- **Invocations**: Calls per stage
- **Errors**: Failures per stage
- **Duration**: Performance per stage
- **ConcurrentExecutions**: Load per stage

### Custom Metrics

```python
# In each Lambda
cloudwatch.put_metric_data(
    Namespace='VideoProcessing',
    MetricData=[{
        'MetricName': 'FeatureExtractionTime',
        'Value': duration_ms,
        'Unit': 'Milliseconds'
    }]
)
```

---

## Deployment

### Infrastructure as Code

**Terraform**:
```bash
cd deployment/level-2/terraform
terraform init
terraform plan
terraform apply
```

**Serverless Framework**:
```bash
cd deployment/level-2/serverless
serverless deploy
```

### Step Functions Definition

```bash
aws stepfunctions create-state-machine \
  --name video-processing-pipeline \
  --definition file://state-machine.json \
  --role-arn arn:aws:iam::ACCOUNT:role/StepFunctionsRole
```

---

## Migration from Level 1

### Migration Path

```
1. Deploy new Level 2 infrastructure (parallel to Level 1)
2. Update API Gateway to route 10% traffic to Level 2
3. Monitor for 1 week
4. Gradually increase to 50% → 100%
5. Deprecate Level 1 after full migration
```

### Zero-Downtime Migration

```
API Gateway → Route based on header
  If header "x-pipeline-version: 2":
    → Route to Step Functions (Level 2)
  Else:
    → Route to SQS Queue (Level 1)
```

---

## When to Upgrade to Level 3

Upgrade when:
- ✅ Concurrent users > 500
- ✅ Videos/day > 50,000
- ✅ Need real-time processing (< 10s)
- ✅ Need multi-region deployment
- ✅ Need event-driven architecture

See: [Level 3 Architecture](level-3-architecture.md)

---

## Pros and Cons

### Pros ✅
- 2x faster processing
- Better fault isolation
- Independent scaling
- Easier debugging (per-stage logs)
- Parallel clip processing

### Cons ❌
- More complex infrastructure
- More Lambda functions to manage
- Higher cost per video (+14%)
- Requires Step Functions knowledge
- More monitoring overhead

---

## Best Practices

### 1. Right-Size Lambda Memory

```python
# Test and optimize per Lambda
Transcript Extractor: 512MB (CPU-bound)
Visual Extractor: 2GB (memory-bound, cv2)
Audio Extractor: 1GB (balanced)
Classifier: 1GB (balanced)
Clip Processor: 3GB (FFmpeg memory-intensive)
```

### 2. Use Lambda Layers

```
Share common code across Lambdas:
- Plugin system
- Helper functions
- Dependencies

Layer size: < 50MB for faster cold starts
```

### 3. Optimize Cold Starts

```
- Use provisioned concurrency for critical paths
- Keep packages minimal
- Lazy load heavy imports
```

### 4. Error Budget

```
Set SLOs per stage:
- Feature Extraction: 99.9% success
- Classification: 99.5% success
- Clip Processing: 99.0% success (can retry)
```

---

## Summary

**Level 2 is ideal when**:
- Growing beyond 100 concurrent users
- Need faster processing
- Want better fault isolation
- Have budget for slight cost increase
- Team comfortable with Step Functions

**Migration effort**: 3-5 days
**Complexity**: Medium
**ROI**: High (2x faster, better reliability)

---

**Document Version**: 1.0
**Last Updated**: 2024-12-24
