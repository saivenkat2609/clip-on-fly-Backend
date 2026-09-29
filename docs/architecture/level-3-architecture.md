# Level 3 Architecture: Event-Driven Distributed System

## Overview

**Target Scale**: 10,000+ concurrent users, 1M+ videos/day
**Complexity**: High
**Setup Time**: 1-2 weeks
**Monthly Cost**: ~$90 base + variable

### Key Features
- Fully event-driven architecture
- Unlimited horizontal scaling
- Multi-region deployment
- Real-time WebSocket updates
- Microservices pattern
- Advanced monitoring & tracing

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GLOBAL LAYER                                 │
│  CloudFront (CDN) → API Gateway (Multi-Region) → Route 53           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      EVENT BUS (EventBridge)                         │
│  Decouples all services - pub/sub pattern                           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────┼────────────────────┐
         ↓                    ↓                    ↓
    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │ Feature │         │Classify │         │  Clip   │
    │Extract  │         │Service  │         │ Process │
    │Service  │         │         │         │ Service │
    └─────────┘         └─────────┘         └─────────┘
         ↓                    ↓                    ↓
    [SQS Queue]         [SQS Queue]         [SQS Queue]
         ↓                    ↓                    ↓
    [Lambda/ECS]        [Lambda/ECS]        [Fargate]
         ↓                    ↓                    ↓
         └────────────────────┼────────────────────┘
                              ↓
                     [EventBridge Events]
                              ↓
                         ┌────┴────┐
                         ↓         ↓
                   [DynamoDB]  [WebSocket API]
                         ↓         ↓
                     [Results]  [Real-time Updates]
```

---

## Core Concepts

### 1. Event-Driven Architecture

**Every state change = Event**

```
Events:
- VideoUploaded
- FeaturesExtracted
- VideoClassified
- ClipProcessed
- ProcessingComplete
- ProcessingFailed
```

**Benefits**:
- Loose coupling (services don't know about each other)
- Easy to add new features (just subscribe to events)
- Replay capability (reprocess by replaying events)
- Audit trail (all events logged)

---

### 2. Pub/Sub Pattern

```
Publisher → EventBridge → Subscribers

Example:
  VideoClassified event
    ├→ Clip Processing Service (processes video)
    ├→ Analytics Service (logs classification)
    ├→ Notification Service (notifies user)
    └→ Recommendation Service (updates recommendations)
```

---

## Services (Microservices)

### 1. **Upload Service**

**Responsibility**: Handle video uploads

**API Endpoints**:
- `POST /upload/generate-url` - Generate pre-signed URL
- `POST /upload/complete` - Confirm upload

**Events Published**:
- `VideoUploaded`

**Implementation**: Lambda (Node.js)

---

### 2. **Feature Extraction Service**

**Responsibility**: Extract all features from video

**Subscribes to**: `VideoUploaded`

**Publishes**: `FeaturesExtracted`

**Sub-Services**:
```
Feature Extraction Coordinator (Lambda)
  ├→ Transcript Worker (Lambda)
  ├→ Visual Worker (Lambda + ECS for heavy lifting)
  └→ Audio Worker (Lambda)
```

**Implementation**:
- Coordinator: Lambda
- Workers: Lambda (light) + ECS Fargate (heavy)

---

### 3. **Classification Service**

**Responsibility**: Classify videos

**Subscribes to**: `FeaturesExtracted`

**Publishes**: `VideoClassified`

**Implementation**:
```python
# Uses our plugin system!
class ClassificationService:
    def handle_features_extracted(self, event):
        features = event['detail']['features']

        # Use plugin orchestrator
        classification = self.orchestrator.classify(features)

        # Publish result
        self.publish_event('VideoClassified', {
            'video_id': event['video_id'],
            'classification': classification
        })
```

**Deployment**: Lambda with plugin system

---

### 4. **Clip Processing Service**

**Responsibility**: Process clips based on classification

**Subscribes to**: `VideoClassified`

**Publishes**: `ClipProcessed` (per clip), `ProcessingComplete`

**Implementation**: ECS Fargate (long-running tasks > 15 min)

**Why Fargate?**
- Lambda limit: 15 minutes
- Some videos need more time
- Fargate: Can run hours if needed

---

### 5. **Notification Service**

**Responsibility**: Notify users about processing status

**Subscribes to**: All events

**Notification Methods**:
- WebSocket (real-time)
- Webhook (HTTP callback)
- Email (SES)
- SMS (SNS)

**Implementation**: Lambda + WebSocket API

---

### 6. **Analytics Service**

**Responsibility**: Track metrics and analytics

**Subscribes to**: All events

**Storage**:
- DynamoDB (operational data)
- S3 + Athena (analytics queries)
- CloudWatch (metrics)

**Implementation**: Lambda + Kinesis Firehose

---

## Event Flow

### Complete Processing Flow

```
1. User uploads video
   ↓
   Event: VideoUploaded
   {
     video_id: "abc123",
     s3_key: "uploads/video.mp4",
     user_id: "user789",
     size_mb: 50
   }

2. Feature Extraction Service (subscribes to VideoUploaded)
   ├→ Extract transcript (2s)
   ├→ Extract visual (3s)
   └→ Extract audio (2s)
   ↓
   Event: FeaturesExtracted
   {
     video_id: "abc123",
     features: {...}
   }

3. Classification Service (subscribes to FeaturesExtracted)
   ├→ Run plugin classifiers
   └→ Determine category + strategy
   ↓
   Event: VideoClassified
   {
     video_id: "abc123",
     category: "talking_head",
     strategy: {...}
   }

4. Clip Processing Service (subscribes to VideoClassified)
   ├→ Spawn Fargate task per clip
   ├→ Process clip 1 (30s)
   ├→ Process clip 2 (30s)
   └→ Process clip 3 (30s)
   ↓
   Events: ClipProcessed (3 events, one per clip)
   {
     video_id: "abc123",
     clip_index: 0,
     s3_key: "clips/clip_0.mp4"
   }
   ↓
   Event: ProcessingComplete
   {
     video_id: "abc123",
     clips: [...]
   }

5. Notification Service (subscribes to all events)
   ├→ Send WebSocket message (real-time)
   ├→ Send webhook to user's endpoint
   └→ Store in DynamoDB

6. Analytics Service (subscribes to all events)
   ├→ Track processing time
   ├→ Track classification distribution
   └→ Log to data warehouse
```

---

## Real-Time Updates (WebSocket)

### Architecture

```
User's Browser
  ↓ (WebSocket connection)
API Gateway (WebSocket API)
  ↓ (connection stored)
DynamoDB (Connections Table)

When event occurs:
  EventBridge → Lambda → API Gateway (WebSocket) → User
```

### Implementation

```python
# Connection Handler
def on_connect(event, context):
    connection_id = event['requestContext']['connectionId']
    user_id = event['queryStringParameters']['user_id']

    # Store connection
    connections_table.put_item(Item={
        'connection_id': connection_id,
        'user_id': user_id,
        'connected_at': int(time.time())
    })

    return {'statusCode': 200}

# Event Handler
def on_video_event(event, context):
    video_id = event['detail']['video_id']
    user_id = event['detail']['user_id']

    # Get user's connections
    connections = connections_table.query(
        IndexName='user_id-index',
        KeyConditionExpression='user_id = :uid',
        ExpressionAttributeValues={':uid': user_id}
    )

    # Send to all user's connections
    for conn in connections['Items']:
        try:
            api_gateway.post_to_connection(
                ConnectionId=conn['connection_id'],
                Data=json.dumps({
                    'type': event['detail-type'],
                    'data': event['detail']
                })
            )
        except:
            # Connection closed, delete
            connections_table.delete_item(
                Key={'connection_id': conn['connection_id']}
            )
```

---

## Multi-Region Deployment

### Global Architecture

```
User (Asia) → CloudFront → Route 53
                              ↓
                         (Geo-routing)
                              ↓
                    ┌─────────┼─────────┐
                    ↓                   ↓
             us-east-1              ap-southeast-1
            [Full Stack]           [Full Stack]
                    ↓                   ↓
              S3 (Primary)        S3 (Replica)
                    ↓ (Cross-region replication)
              DynamoDB Global Tables
```

### Benefits
- **Low latency**: Process in closest region
- **High availability**: Failover to other regions
- **Compliance**: Data residency requirements

### Implementation

```terraform
# Primary Region (us-east-1)
resource "aws_eventbridge_bus" "primary" {
  provider = aws.us_east_1
  name     = "video-processing"
}

# Secondary Region (ap-southeast-1)
resource "aws_eventbridge_bus" "secondary" {
  provider = aws.ap_southeast_1
  name     = "video-processing"
}

# Cross-region event forwarding
resource "aws_eventbridge_rule" "cross_region" {
  name           = "forward-to-secondary"
  event_bus_name = aws_eventbridge_bus.primary.name

  event_pattern = jsonencode({
    source = ["video.processing"]
  })
}

resource "aws_eventbridge_target" "secondary_bus" {
  rule           = aws_eventbridge_rule.cross_region.name
  arn            = aws_eventbridge_bus.secondary.arn
  role_arn       = aws_iam_role.eventbridge_cross_region.arn
}
```

---

## Scaling

### Automatic Scaling

```
Each service scales independently:

Feature Extraction:
  Lambda: Auto-scales to 1000s
  ECS: Scales based on SQS queue depth

Classification:
  Lambda: Auto-scales to 1000s

Clip Processing:
  Fargate: Scales to 10,000 tasks
  Each task processes 1 clip

Notification:
  Lambda: Auto-scales
  WebSocket: Handles 100k connections

Analytics:
  Kinesis: Scales automatically
```

### Scaling Triggers

```python
# ECS Auto Scaling based on SQS
resource "aws_appautoscaling_policy" "ecs_policy" {
  name               = "scale-on-queue-depth"
  service_namespace  = "ecs"
  resource_id        = "service/video-processing/clip-processor"
  scalable_dimension = "ecs:service:DesiredCount"

  target_tracking_scaling_policy_configuration {
    target_value = 100  # Keep queue at ~100 messages

    customized_metric_specification {
      metric_name = "ApproximateNumberOfMessagesVisible"
      namespace   = "AWS/SQS"
      statistic   = "Average"
      unit        = "Count"

      dimensions {
        name  = "QueueName"
        value = "clip-processing-queue"
      }
    }
  }
}
```

---

## Cost Analysis

### Per-Video Cost

```
EventBridge: 10 events × $1/million = $0.00001
Feature Extraction: $0.00090
Classification: $0.00020
Clip Processing (Fargate): 3 clips × $0.00200 = $0.00600
Notification: $0.00005
Analytics: $0.00010
DynamoDB: $0.00015
S3: $0.00020
───────────────────────────────────────
TOTAL: ~$0.00761 per video (if using Fargate)

With Lambda (< 15 min videos):
TOTAL: ~$0.00300 per video
```

### Monthly Cost at Scale

| Videos/Day | Monthly Cost | Notes |
|------------|--------------|-------|
| 10,000     | $900-2,300   | Mix of Lambda/Fargate |
| 100,000    | $9,000-23,000| Mostly Fargate |
| 1,000,000  | $90,000-230,000| Full Fargate |

**Cost Optimization**:
- Use Lambda for videos < 15 min (cheaper)
- Use Fargate for long videos
- Use Spot instances for Fargate (70% discount)

---

## Monitoring & Observability

### Distributed Tracing (AWS X-Ray)

```
Request ID: abc123

Upload Service (10ms)
  ↓
Feature Extraction (2500ms)
  ├→ Transcript Worker (1000ms)
  ├→ Visual Worker (2500ms) ← BOTTLENECK
  └→ Audio Worker (1500ms)
  ↓
Classification (800ms)
  ↓
Clip Processing (30000ms)
  ↓
Notification (50ms)

Total: 33360ms
Bottleneck: Visual Worker
```

### Service Map

```
                    ┌──────────────┐
                    │    Upload    │
                    │   Service    │
                    └──────┬───────┘
                           ↓
                  ┌────────┴────────┐
                  ↓                 ↓
         ┌────────────────┐  ┌─────────────┐
         │   Feature      │  │   Classify  │
         │   Extraction   │→ │   Service   │
         └────────────────┘  └──────┬──────┘
                                    ↓
                           ┌────────┴────────┐
                           │  Clip Process   │
                           │    Service      │
                           └─────────────────┘
```

### Custom Metrics

```python
# In each service
from aws_xray_sdk.core import xray_recorder

@xray_recorder.capture('extract_features')
def extract_features(video_path):
    with xray_recorder.capture_subsegment('download'):
        video = download(video_path)

    with xray_recorder.capture_subsegment('analyze'):
        features = analyze(video)

    return features
```

---

## Deployment

### Infrastructure as Code

```bash
# Terraform
cd deployment/level-3/terraform
terraform workspace new production
terraform apply

# Includes:
# - EventBridge buses (multi-region)
# - Lambda functions (all services)
# - ECS clusters + Fargate services
# - SQS queues (per service)
# - DynamoDB tables (global)
# - API Gateway (HTTP + WebSocket)
# - CloudFront distribution
# - Route 53 (geo-routing)
# - CloudWatch dashboards
# - X-Ray configuration
```

### CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml

name: Deploy Level 3 Services

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v2

      # Build Docker images for ECS
      - name: Build Images
        run: |
          docker build -t clip-processor:${{ github.sha }} \
            -f services/clip-processor/Dockerfile .

      # Deploy to ECR
      - name: Push to ECR
        run: |
          aws ecr get-login-password | docker login --username AWS \
            --password-stdin $ECR_REGISTRY
          docker push clip-processor:${{ github.sha }}

      # Deploy infrastructure
      - name: Terraform Apply
        run: |
          cd terraform
          terraform apply -auto-approve

      # Deploy Lambda functions
      - name: Deploy Lambdas
        run: |
          for service in upload feature-extraction classification; do
            cd services/$service
            zip -r function.zip .
            aws lambda update-function-code \
              --function-name $service \
              --zip-file fileb://function.zip
          done

      # Update ECS services
      - name: Update ECS
        run: |
          aws ecs update-service \
            --cluster video-processing \
            --service clip-processor \
            --force-new-deployment
```

---

## Disaster Recovery

### Backup Strategy

```
DynamoDB:
  - Point-in-time recovery (enabled)
  - Daily backups to S3
  - Cross-region replication

S3:
  - Versioning enabled
  - Cross-region replication
  - Lifecycle policies (archive old videos)

EventBridge:
  - All events logged to S3
  - Can replay events for reprocessing
```

### Recovery Procedures

```
Scenario: Primary region (us-east-1) down

1. Route 53 health check fails
2. Auto-route traffic to ap-southeast-1
3. Secondary region takes over
4. Time to failover: < 1 minute
5. Data loss: 0 (global tables + replication)
```

---

## Security

### Network Security

```
VPC Design:
  Public Subnet: ALB only
  Private Subnet: ECS tasks, Lambda
  Data Subnet: DynamoDB, ElastiCache

Security Groups:
  - ALB: 443 (HTTPS only)
  - ECS: 8080 (from ALB only)
  - Lambda: Outbound only
```

### Encryption

```
At Rest:
  - S3: AES-256
  - DynamoDB: AWS KMS
  - EBS volumes: Encrypted

In Transit:
  - TLS 1.3 everywhere
  - Certificate: AWS Certificate Manager
```

### IAM Roles

```
Principle of Least Privilege:

Upload Service:
  - s3:PutObject (uploads/ prefix only)
  - events:PutEvents

Feature Extraction:
  - s3:GetObject (uploads/ prefix)
  - s3:PutObject (features/ prefix)
  - events:PutEvents

Clip Processing:
  - s3:GetObject (uploads/, features/)
  - s3:PutObject (clips/ prefix)
  - events:PutEvents
```

---

## When to Use Level 3

✅ **Use Level 3 when**:
- Processing > 50,000 videos/day
- Need < 10 second total latency
- Need multi-region for compliance/latency
- Need real-time user updates
- Have dedicated DevOps team
- Budget > $1000/month

❌ **Don't use Level 3 if**:
- Processing < 10,000 videos/day (overkill)
- Small team (< 5 engineers)
- Don't need real-time updates
- Budget constrained

---

## Migration from Level 2

### Phase 1: Deploy Parallel (1 week)
```
- Deploy Level 3 infrastructure
- Don't route traffic yet
- Test with synthetic data
```

### Phase 2: Shadow Mode (1 week)
```
- Duplicate traffic to both Level 2 and 3
- Compare results
- Level 2 is authoritative
- Fix discrepancies
```

### Phase 3: Gradual Rollout (2 weeks)
```
Week 1: Route 10% → 25% → 50%
Week 2: Route 75% → 100%
```

### Phase 4: Deprecate Level 2 (1 week)
```
- Remove Level 2 infrastructure
- Keep as backup for 1 month
```

---

## Best Practices

### 1. Event Versioning

```json
{
  "version": "1.0",
  "event_type": "VideoClassified",
  "data": {...}
}
```

When schema changes, increment version. Old services continue working.

### 2. Idempotency

```python
# Every handler must be idempotent
def handle_event(event):
    event_id = event['id']

    # Check if already processed
    if already_processed(event_id):
        return  # Skip

    # Process
    process(event)

    # Mark as processed
    mark_processed(event_id)
```

### 3. Circuit Breakers

```python
@circuit_breaker(failure_threshold=5, timeout=60)
def call_external_service():
    # Call might fail
    return external_api.call()
```

### 4. Chaos Engineering

```bash
# Randomly kill services to test resilience
aws ecs update-service \
  --cluster video-processing \
  --service feature-extraction \
  --desired-count 0

# System should continue working with degraded performance
```

---

## Summary

**Level 3 provides**:
- ✅ Unlimited scale (millions of videos/day)
- ✅ Real-time updates (WebSocket)
- ✅ Multi-region (global coverage)
- ✅ Event-driven (loose coupling)
- ✅ Microservices (independent deployment)
- ✅ Advanced monitoring (X-Ray, distributed tracing)
- ✅ Disaster recovery (cross-region failover)

**But requires**:
- ⚠️ High complexity
- ⚠️ Dedicated DevOps team
- ⚠️ Higher cost
- ⚠️ Longer setup time

**Only use if you truly need this scale.**

---

**Document Version**: 1.0
**Last Updated**: 2024-12-24
