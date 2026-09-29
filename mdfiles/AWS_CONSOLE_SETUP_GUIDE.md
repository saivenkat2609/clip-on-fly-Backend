# AWS Console Setup Guide

This guide walks you through all the manual AWS setup steps using the AWS Console (no CLI required).

## Prerequisites

- AWS Account with administrator access
- All CloudFormation templates in `opus-clip-cloud/infrastructure/`
- All Lambda function code ready to deploy

---

## Step 1: Request Lambda Concurrency Increase

**Goal:** Increase Lambda concurrent executions from 1,000 to 5,000

1. Go to **AWS Support Center** → https://console.aws.amazon.com/support/home
2. Click **Create case**
3. Select **Service limit increase**
4. Fill in:
   - **Limit type:** Lambda
   - **Region:** Your region (e.g., us-east-1)
   - **Limit:** Concurrent executions
   - **New limit value:** 5000
   - **Use case description:**
     ```
     We are running a video processing application that uses AWS Lambda for FFmpeg operations.
     We expect 100-200 concurrent users processing videos simultaneously.
     Each video processing takes ~5-10 minutes. We need 5,000 concurrent executions to handle peak load.
     ```
5. Click **Submit**
6. **Wait for approval** (usually 1-3 business days)

---

## Step 2: Create VPC for Redis and Lambda (Optional but Recommended)

**Goal:** Create VPC with private subnets for Redis cluster

### 2.1 Create VPC

1. Go to **VPC Console** → https://console.aws.amazon.com/vpc/
2. Click **Create VPC**
3. Select **VPC and more**
4. Configure:
   - **Name:** `video-processing-vpc`
   - **IPv4 CIDR:** `10.0.0.0/16`
   - **Number of AZs:** 2
   - **Number of public subnets:** 2
   - **Number of private subnets:** 2
   - **NAT gateways:** 1 per AZ (or 1 total to save cost)
   - **VPC endpoints:** S3 Gateway
5. Click **Create VPC**
6. **Note down:** VPC ID and Private Subnet IDs

### 2.2 Create Security Group for Lambda

1. In VPC Console, go to **Security Groups**
2. Click **Create security group**
3. Configure:
   - **Name:** `lambda-security-group`
   - **VPC:** Select the VPC you just created
   - **Description:** Security group for Lambda functions
   - **Outbound rules:** Keep default (allow all)
   - **Inbound rules:** None needed
4. Click **Create security group**
5. **Note down:** Security Group ID

### 2.3 Create Security Group for Redis

1. Click **Create security group**
2. Configure:
   - **Name:** `redis-security-group`
   - **VPC:** Same VPC as above
   - **Description:** Security group for Redis cluster
   - **Inbound rules:**
     - Type: Custom TCP
     - Port: 6379
     - Source: Select `lambda-security-group`
   - **Outbound rules:** Keep default
3. Click **Create security group**
4. **Note down:** Security Group ID

---

## Step 3: Deploy CloudFormation Stacks

**Order matters!** Deploy in this sequence:

### 3.1 Deploy DynamoDB Tables

1. Go to **CloudFormation Console** → https://console.aws.amazon.com/cloudformation/
2. Click **Create stack** → **With new resources**
3. **Template source:** Upload a template file
4. Click **Choose file** → Select `opus-clip-cloud/infrastructure/dynamodb.yml`
5. Click **Next**
6. **Stack name:** `video-processing-dynamodb-prod`
7. **Parameters:**
   - Environment: `prod`
8. Click **Next** → **Next**
9. Check **I acknowledge that AWS CloudFormation might create IAM resources**
10. Click **Submit**
11. **Wait for status:** `CREATE_COMPLETE` (takes ~2 minutes)

### 3.2 Deploy SQS Queues

1. Click **Create stack** → **With new resources**
2. Upload `opus-clip-cloud/infrastructure/sqs-queues.yml`
3. **Stack name:** `video-processing-sqs-prod`
4. **Parameters:**
   - Environment: `prod`
5. Complete creation
6. **Wait for:** `CREATE_COMPLETE`

### 3.3 Deploy Redis Cluster

1. Click **Create stack** → **With new resources**
2. Upload `opus-clip-cloud/infrastructure/redis.yml`
3. **Stack name:** `video-processing-redis-prod`
4. **Parameters:**
   - Environment: `prod`
   - VpcId: *Paste the VPC ID from Step 2*
   - PrivateSubnetIds: *Paste both private subnet IDs (comma-separated)*
   - LambdaSecurityGroupId: *Paste Lambda security group ID*
5. Complete creation
6. **Wait for:** `CREATE_COMPLETE` (takes ~10-15 minutes)
7. Go to **Outputs** tab → **Note down:** `RedisEndpoint`

### 3.4 Deploy S3 Lifecycle Policies

1. Click **Create stack** → **With new resources**
2. Upload `opus-clip-cloud/infrastructure/s3-lifecycle.yml`
3. **Stack name:** `video-processing-s3-lifecycle-prod`
4. **Parameters:**
   - Environment: `prod`
   - VideoBucketName: *Your existing S3 bucket name*
5. Complete creation
6. **Wait for:** `CREATE_COMPLETE`

### 3.5 Deploy CloudWatch Alarms

1. Click **Create stack** → **With new resources**
2. Upload `opus-clip-cloud/infrastructure/cloudwatch-alarms.yml`
3. **Stack name:** `video-processing-alarms-prod`
4. **Parameters:**
   - Environment: `prod`
   - AlertEmail: *Your email for alarm notifications*
   - VideoProcessingQueueName: `prod-video-processing-queue`
   - UploadProcessingQueueName: `prod-upload-processing-queue`
5. Complete creation
6. **Wait for:** `CREATE_COMPLETE`
7. **Important:** Go to your email and confirm the SNS subscription

### 3.6 Deploy WebSocket API

1. Click **Create stack** → **With new resources**
2. Upload `opus-clip-cloud/infrastructure/websocket-api.yml`
3. **Stack name:** `video-processing-websocket-prod`
4. **Parameters:**
   - Environment: `prod`
   - WebSocketHandlerLambdaArn: *Leave blank for now, we'll update later*
5. Complete creation
6. **Wait for:** `CREATE_COMPLETE`
7. Go to **Outputs** tab → **Note down:** `WebSocketURL` and `WebSocketManagementAPIEndpoint`

---

## Step 4: Update Lambda Function Environment Variables

For **each existing Lambda function**, add these environment variables:

1. Go to **Lambda Console** → https://console.aws.amazon.com/lambda/
2. Open each Lambda function
3. Click **Configuration** tab → **Environment variables** → **Edit**
4. Add the following variables:

### Common Variables for All Lambda Functions:

```
REDIS_ENDPOINT=<Redis endpoint from Step 3.3>
REDIS_PORT=6379
DYNAMODB_TABLE_SESSIONS=prod-video-sessions
DYNAMODB_TABLE_CONNECTIONS=prod-websocket-connections
WEBSOCKET_API_ENDPOINT=<WebSocket Management API Endpoint from Step 3.6>
SQS_VIDEO_QUEUE_URL=https://sqs.<region>.amazonaws.com/<account-id>/prod-video-processing-queue
SQS_UPLOAD_QUEUE_URL=https://sqs.<region>.amazonaws.com/<account-id>/prod-upload-processing-queue
ENABLE_S3_SHARDING=true
ENVIRONMENT=prod
```

### Get SQS Queue URLs:

1. Go to **SQS Console** → https://console.aws.amazon.com/sqs/
2. Click on `prod-video-processing-queue`
3. Copy the **URL** from the details
4. Repeat for `prod-upload-processing-queue`

### 4.1 Update VPC Configuration for Lambda Functions

For functions that need Redis access:

1. In Lambda function **Configuration** → **VPC**
2. Click **Edit**
3. Select:
   - **VPC:** The VPC you created
   - **Subnets:** Both private subnets
   - **Security groups:** `lambda-security-group`
4. Click **Save**

**Note:** This will cause Lambda to take ~5 minutes to update. The function will be unavailable during this time.

---

## Step 5: Deploy Queue Consumer Lambda

1. Go to **Lambda Console** → **Create function**
2. Configure:
   - **Function name:** `prod-queue-consumer`
   - **Runtime:** Python 3.11
   - **Architecture:** x86_64
3. Click **Create function**
4. **Upload code:**
   - Zip the contents of `opus-clip-cloud/src/queue-consumer/`
   - Click **Upload from** → **.zip file**
   - Upload the zip
5. **Configure:**
   - **Handler:** `lambda_function.lambda_handler`
   - **Timeout:** 5 minutes
   - **Memory:** 512 MB
6. **Add environment variables** (from Step 4)
7. **Add SQS trigger:**
   - Click **Add trigger**
   - Select **SQS**
   - SQS queue: `prod-video-processing-queue`
   - Batch size: 10
   - Click **Add**
8. **Update IAM role:**
   - Go to **Configuration** → **Permissions**
   - Click on the role name
   - **Attach policies:**
     - `AWSStepFunctionsFullAccess`
     - `AWSLambdaSQSQueueExecutionRole`

---

## Step 6: Deploy WebSocket Handler Lambda

1. **Create function:**
   - **Function name:** `prod-websocket-handler`
   - **Runtime:** Python 3.11
2. **Upload code:**
   - Zip `opus-clip-cloud/src/websocket-handler/`
   - Upload the zip
3. **Configure:**
   - **Handler:** `lambda_function.lambda_handler`
   - **Timeout:** 30 seconds
   - **Memory:** 256 MB
4. **Add environment variables** (from Step 4)
5. **Update IAM role:**
   - Attach policy: `AmazonDynamoDBFullAccess`
   - Add inline policy for API Gateway Management API:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Action": [
             "execute-api:ManageConnections"
           ],
           "Resource": "arn:aws:execute-api:*:*:*/@connections/*"
         }
       ]
     }
     ```
6. **Copy Lambda ARN** (from top right)

### 6.1 Update WebSocket API with Lambda ARN

1. Go back to **CloudFormation Console**
2. Select `video-processing-websocket-prod` stack
3. Click **Update** → **Use current template**
4. **Parameters:**
   - WebSocketHandlerLambdaArn: *Paste the Lambda ARN from above*
5. Complete update
6. **Wait for:** `UPDATE_COMPLETE`

---

## Step 7: Update IAM Roles for Existing Lambdas

For all Lambda functions, ensure they have these permissions:

1. Go to **Lambda function** → **Configuration** → **Permissions**
2. Click on the **Execution role**
3. **Attach these managed policies:**
   - `AmazonDynamoDBFullAccess`
   - `AmazonElastiCacheFullAccess` (or create custom with read/write to your cluster)
   - `AmazonSQSFullAccess`
   - `CloudWatchFullAccess`
4. **Add inline policy for WebSocket API:**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "execute-api:ManageConnections"
         ],
         "Resource": "arn:aws:execute-api:*:*:*/@connections/*"
       }
     ]
   }
   ```

---

## Step 8: Update Frontend Environment Variables

1. Open `reframe-ai/.env.local` (or `.env.production`)
2. Add:
   ```
   VITE_WEBSOCKET_URL=<WebSocketURL from Step 3.6>
   VITE_ENABLE_WEBSOCKET=true
   VITE_ENABLE_CACHE=true
   VITE_ENABLE_PAGINATION=true
   ```
3. Save and rebuild your frontend:
   ```
   npm run build
   ```

---

## Step 9: Testing

### 9.1 Test DynamoDB Tables

1. Go to **DynamoDB Console** → https://console.aws.amazon.com/dynamodb/
2. Check tables exist:
   - `prod-video-sessions`
   - `prod-websocket-connections`
3. Click on `prod-video-sessions` → **Explore table items**
4. Should be empty (ready for data)

### 9.2 Test SQS Queues

1. Go to **SQS Console**
2. Check queues exist:
   - `prod-video-processing-queue`
   - `prod-video-processing-dlq`
   - `prod-upload-processing-queue`
   - `prod-upload-processing-dlq`
3. Click on `prod-video-processing-queue`
4. Click **Send and receive messages**
5. Send a test message:
   ```json
   {
     "session_id": "test-123",
     "user_id": "test-user",
     "youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ"
   }
   ```
6. Check that Queue Consumer Lambda is triggered (CloudWatch Logs)

### 9.3 Test Redis Connection

1. Go to **Lambda Console**
2. Open any Lambda function with VPC access
3. Click **Test** tab
4. Create test event:
   ```json
   {
     "test": "redis"
   }
   ```
5. Add this test code to Lambda (temporarily):
   ```python
   import redis
   import os

   def lambda_handler(event, context):
       try:
           r = redis.Redis(
               host=os.environ['REDIS_ENDPOINT'],
               port=6379,
               decode_responses=True
           )
           r.set('test', 'hello')
           result = r.get('test')
           return {'statusCode': 200, 'body': f'Redis test: {result}'}
       except Exception as e:
           return {'statusCode': 500, 'body': str(e)}
   ```
6. Run test → Should return "Redis test: hello"

### 9.4 Test WebSocket Connection

1. Install `wscat` tool or use browser extension
2. Connect to WebSocket URL:
   ```
   wscat -c <WebSocketURL from Step 3.6>
   ```
3. Send subscribe message:
   ```json
   {"action": "subscribe", "session_id": "test-123"}
   ```
4. Should receive confirmation message

### 9.5 Test End-to-End Flow

1. Go to your application frontend
2. Upload a video or process from YouTube
3. Check:
   - ✅ Video appears in dashboard immediately
   - ✅ WebSocket connection established (check browser DevTools)
   - ✅ Real-time progress updates appear
   - ✅ No need to refresh page
   - ✅ Processing completes successfully
4. Check CloudWatch Logs for any errors

---

## Step 10: Monitor and Verify

### 10.1 Check CloudWatch Alarms

1. Go to **CloudWatch Console** → https://console.aws.amazon.com/cloudwatch/
2. Click **Alarms** → **All alarms**
3. Verify all alarms are in "OK" state
4. If any alarm is in "ALARM" state, investigate

### 10.2 Check CloudWatch Metrics

1. Go to **Metrics** → **All metrics**
2. Select **AWS/Lambda**
3. Check:
   - Concurrent executions (should be < 5000)
   - Error rate (should be < 1%)
   - Duration (should be reasonable)
4. Select **AWS/SQS**
5. Check:
   - Messages sent
   - Messages received
   - Queue depth (should stay low)

### 10.3 Check DynamoDB Usage

1. Go to **DynamoDB Console**
2. Click on `prod-video-sessions`
3. Click **Metrics** tab
4. Check:
   - Read/Write capacity (should be within limits)
   - Throttled requests (should be 0)

---

## Common Issues and Solutions

### Issue: Lambda timeout errors

**Solution:**
- Increase Lambda timeout to 15 minutes
- Check if Redis connection is slow (VPC NAT gateway issue)
- Enable VPC endpoint for DynamoDB to avoid NAT

### Issue: Redis connection errors

**Solution:**
- Verify Lambda is in same VPC as Redis
- Check security group allows inbound on port 6379
- Verify Redis cluster is "Available" status

### Issue: WebSocket disconnects immediately

**Solution:**
- Check Lambda function has correct IAM permissions
- Verify WebSocket API integration is configured
- Check CloudWatch Logs for Lambda errors

### Issue: High DynamoDB costs

**Solution:**
- Review TTL settings (items should auto-delete)
- Check if GSI indexes are being over-queried
- Consider switching to DynamoDB On-Demand billing

### Issue: SQS messages going to DLQ

**Solution:**
- Check Lambda logs for processing errors
- Verify Step Functions state machine ARN is correct
- Increase Lambda timeout if needed

---

## Next Steps

1. **Monitor for 24 hours** - Watch CloudWatch metrics and alarms
2. **Load testing** - Use tools like `artillery` or `locust` to simulate multiple users
3. **Cost optimization** - Review AWS Cost Explorer after 1 week
4. **Documentation** - Update team documentation with new architecture
5. **Backup strategy** - Set up DynamoDB backups (Console → DynamoDB → Backups)

---

## Cost Estimates (Monthly)

Based on 1,000 videos/month:

- **Lambda:** ~$50-100 (depending on concurrency)
- **ElastiCache (Redis):** ~$15 (t3.micro x2)
- **DynamoDB:** ~$5 (on-demand pricing)
- **SQS:** ~$1 (first 1M requests free)
- **CloudWatch:** ~$10 (logs + metrics)
- **NAT Gateway:** ~$35 (if using VPC)
- **API Gateway (WebSocket):** ~$3 (1M messages)

**Total:** ~$120-170/month

**Savings from optimizations:**
- Reduced Lambda invocations: -$30/month
- S3 lifecycle policies: -$20/month
- Redis caching: -$15/month

**Net cost:** ~$55-105/month

---

## Support

If you encounter issues:

1. Check **CloudWatch Logs** for detailed error messages
2. Review **CloudFormation Events** for stack creation issues
3. Check **Service Quotas** if hitting limits
4. Verify **IAM permissions** are correct

For production deployments, consider:
- AWS Support Plan (Developer or Business)
- AWS Well-Architected Review
- Third-party monitoring (Datadog, New Relic)

---

**Congratulations!** Your scalable video processing application is now ready to handle multiple concurrent users.
