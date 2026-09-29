# AWS Console Setup Guide (NO NAT Gateway - Cost Optimized)

This guide shows how to set up everything **WITHOUT NAT Gateway** using **VPC Endpoints** instead.

**Cost Savings: ~$32-45/month** 💰

---

## VPC Endpoints vs NAT Gateway

### ❌ With NAT Gateway (Original Guide)
- **Cost:** $32/month for NAT + $0.045/GB data transfer
- **Total:** ~$45/month
- **Pros:** Simple, internet access
- **Cons:** Expensive

### ✅ With VPC Endpoints (This Guide)
- **Cost:** $0 (DynamoDB and S3 Gateway Endpoints are FREE!)
- **Total:** $0/month
- **Pros:** FREE, secure, fast
- **Cons:** Slightly more setup

**We'll use VPC Endpoints!** ⭐

---

## Step 2: Create VPC for Redis and Lambda (NO NAT Gateway)

### 2.1 Create VPC

1. Go to **VPC Console** → https://console.aws.amazon.com/vpc/
2. Click **Create VPC**
3. Select **VPC and more**
4. Configure:
   - **Name:** `video-processing-vpc`
   - **IPv4 CIDR:** `10.0.0.0/16`
   - **Number of AZs:** 2
   - **Number of public subnets:** 0 (we don't need public subnets!)
   - **Number of private subnets:** 2
   - **NAT gateways:** **None** ⭐ (This saves $32/month!)
   - **VPC endpoints:** **S3 Gateway** (check this box)
5. Click **Create VPC**
6. **Note down:** VPC ID and Private Subnet IDs

### 2.2 Create DynamoDB VPC Endpoint (FREE!)

1. In VPC Console, go to **Endpoints** in left sidebar
2. Click **Create endpoint**
3. Configure:
   - **Name:** `dynamodb-endpoint`
   - **Service category:** AWS services
   - **Service name:** Search for `dynamodb` → Select `com.amazonaws.<region>.dynamodb` (Type: Gateway)
   - **VPC:** Select `video-processing-vpc`
   - **Route tables:** Select ALL route tables for your private subnets
   - **Policy:** Full access (default)
4. Click **Create endpoint**

**Cost:** FREE! Gateway endpoints have no hourly charge.

### 2.3 Verify S3 Endpoint (Already Created)

1. Go to **Endpoints** in VPC Console
2. You should see an S3 endpoint already created (from step 2.1)
3. If not:
   - Click **Create endpoint**
   - Service name: `com.amazonaws.<region>.s3` (Type: Gateway)
   - VPC: `video-processing-vpc`
   - Route tables: Select all
   - Create

**Cost:** FREE! Gateway endpoints have no hourly charge.

### 2.4 Create Security Group for Lambda

1. In VPC Console, go to **Security Groups**
2. Click **Create security group**
3. Configure:
   - **Name:** `lambda-security-group`
   - **VPC:** Select `video-processing-vpc`
   - **Description:** Security group for Lambda functions
   - **Inbound rules:** None needed
   - **Outbound rules:**
     - Type: All traffic
     - Destination: 0.0.0.0/0 (or specific CIDR for Redis)
4. Click **Create security group**
5. **Note down:** Security Group ID

### 2.5 Create Security Group for Redis

1. Click **Create security group**
2. Configure:
   - **Name:** `redis-security-group`
   - **VPC:** Same VPC as above
   - **Description:** Security group for Redis cluster
   - **Inbound rules:**
     - Type: Custom TCP
     - Port: 6379
     - Source: Select `lambda-security-group`
   - **Outbound rules:** Keep default (allow all)
3. Click **Create security group**
4. **Note down:** Security Group ID

---

## How This Works (No Internet Required!)

```
┌─────────────────────────────────────────┐
│           VPC (10.0.0.0/16)            │
│                                         │
│  ┌─────────────┐      ┌──────────────┐│
│  │   Lambda    │─────→│    Redis     ││
│  │  (Private)  │      │  (Private)   ││
│  └──────┬──────┘      └──────────────┘│
│         │                              │
│         ├────→ VPC Endpoint (DynamoDB) │ FREE!
│         ├────→ VPC Endpoint (S3)       │ FREE!
│         └────→ Security Groups         │
│                                         │
│  NO NAT Gateway = $32/month saved! 💰  │
└─────────────────────────────────────────┘
```

**Lambda can access:**
- ✅ DynamoDB (via VPC Endpoint)
- ✅ S3 (via VPC Endpoint)
- ✅ Redis (same VPC)
- ✅ CloudWatch Logs (built-in)
- ✅ Step Functions (same region)
- ✅ SQS (same region)

**Lambda CANNOT access:**
- ❌ Internet (public websites)
- ❌ External APIs that require internet

**Solution for External APIs:** See below!

---

## Handling External API Calls (Groq, AssemblyAI, etc.)

Your Lambda functions call external APIs like:
- Groq API (transcription)
- AssemblyAI API
- Deepgram API
- YouTube (download)

### Option 1: Keep Those Lambdas Outside VPC (Recommended) ⭐

**Best approach:** Only put Lambdas that need Redis in VPC. Others stay outside.

**Lambdas that NEED VPC (use Redis/DynamoDB directly):**
- detect-clips (uses Redis cache)
- finalize (uses DynamoDB)
- websocket-handler (uses DynamoDB)
- queue-consumer (optional)

**Lambdas that DON'T need VPC (call external APIs):**
- transcribe (calls Groq/AssemblyAI/Deepgram)
- download (calls YouTube)
- process-clip (only uses S3/FFmpeg)

**Setup:**
1. Deploy VPC with Redis
2. Attach VPC to: detect-clips, finalize, websocket-handler
3. Leave others WITHOUT VPC (they can access internet for free!)

**Result:** No NAT Gateway needed, external APIs work, Redis works!

### Option 2: Use NAT Gateway (Not Recommended - Costs Money)

If you REALLY want all Lambdas in VPC:
- Add NAT Gateway (costs $32/month)
- All Lambdas can access internet

### Option 3: Use VPC Endpoints for External APIs (Complex)

Some APIs support AWS PrivateLink. Most don't.

---

## Updated Redis Stack Configuration

When deploying `redis.yml`:

**Parameters:**
- VpcId: Your VPC ID
- PrivateSubnetIds: Your private subnet IDs (comma-separated)
- LambdaSecurityGroupId: Your Lambda security group ID

**Important:** No NAT Gateway needed since Redis and Lambda are in same VPC!

---

## Updated Lambda Configuration

### For Lambdas that NEED Redis (detect-clips, finalize, websocket-handler):

1. Go to Lambda function → **Configuration** → **VPC**
2. Click **Edit**
3. Configure:
   - **VPC:** `video-processing-vpc`
   - **Subnets:** Select BOTH private subnets
   - **Security groups:** `lambda-security-group`
4. Click **Save**

**Note:** Lambda will take ~5 minutes to update.

### For Lambdas that DON'T need Redis (transcribe, download, process-clip):

**Leave them WITHOUT VPC!** They need internet access for external APIs.

1. Go to Lambda function → **Configuration** → **VPC**
2. Should show: "No VPC"
3. Don't change it!

---

## Cost Comparison

### Original Setup (With NAT Gateway)
| Item | Monthly Cost |
|------|--------------|
| Lambda | $50-100 |
| Redis (t3.micro x2) | $15 |
| DynamoDB | $5 |
| SQS | $1 |
| CloudWatch | $10 |
| **NAT Gateway** | **$32** |
| Data transfer | $10 |
| **TOTAL** | **$123-173/month** |

### Optimized Setup (VPC Endpoints, No NAT)
| Item | Monthly Cost |
|------|--------------|
| Lambda | $50-100 |
| Redis (t3.micro x2) | $15 |
| DynamoDB | $5 |
| SQS | $1 |
| CloudWatch | $10 |
| VPC Endpoints (DynamoDB, S3) | **$0 (FREE!)** |
| Data transfer | $5 |
| **TOTAL** | **$86-136/month** |

**💰 Savings: $37/month = $444/year!**

---

## Testing VPC Endpoint Access

### Test DynamoDB Access from Lambda:

1. Create test Lambda function in VPC
2. Add test code:
```python
import boto3

def lambda_handler(event, context):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('prod-video-sessions')

    # Try to describe table
    response = table.table_status
    return {'statusCode': 200, 'body': f'DynamoDB access works! Status: {response}'}
```
3. Test - Should return success

### Test S3 Access from Lambda:

```python
import boto3

def lambda_handler(event, context):
    s3 = boto3.client('s3')

    # List buckets
    response = s3.list_buckets()
    return {'statusCode': 200, 'body': f'S3 access works! Buckets: {len(response["Buckets"])}'}
```

### Test Redis Access from Lambda (in VPC):

```python
import redis
import os

def lambda_handler(event, context):
    r = redis.Redis(
        host=os.environ['REDIS_ENDPOINT'],
        port=6379,
        decode_responses=True
    )
    r.set('test', 'hello')
    result = r.get('test')
    return {'statusCode': 200, 'body': f'Redis access works! Value: {result}'}
```

All should work WITHOUT NAT Gateway!

---

## Updated Deployment Summary

### Step 1: Create VPC (NO NAT Gateway)
- Private subnets only
- S3 Gateway Endpoint (free)
- DynamoDB Gateway Endpoint (free)
- **Cost:** $0/month

### Step 2: Deploy Redis in VPC
- Redis in private subnets
- **Cost:** $15/month

### Step 3: Configure Lambda Functions

**In VPC (need Redis):**
- detect-clips
- finalize
- websocket-handler
- queue-consumer (optional)

**Outside VPC (need internet):**
- transcribe
- download
- process-clip
- api-gateway
- upload-api-gateway

### Step 4: Add Environment Variables to ALL Lambdas

Even Lambdas outside VPC need these (they can access DynamoDB/S3 without VPC):
```
REDIS_ENDPOINT=<only for Lambdas in VPC>
DYNAMODB_TABLE_SESSIONS=prod-video-sessions
ENABLE_S3_SHARDING=true
WEBSOCKET_API_ENDPOINT=<from CloudFormation>
```

---

## Troubleshooting

### Lambda can't connect to Redis
- ✅ Check Lambda is in same VPC as Redis
- ✅ Check Lambda uses `lambda-security-group`
- ✅ Check Redis security group allows inbound from Lambda SG
- ✅ Check both Lambda and Redis in private subnets

### Lambda can't access DynamoDB/S3
- ✅ Check VPC Endpoints are created (DynamoDB + S3)
- ✅ Check VPC Endpoints use correct route tables
- ✅ Check Lambda IAM role has DynamoDB/S3 permissions

### Lambda can't call external APIs (Groq, YouTube)
- ✅ **Remove Lambda from VPC!** It needs internet access
- ✅ Or add NAT Gateway (costs $32/month)

### "No space left on device" in Lambda
- ✅ Increase Lambda storage to 1024 MB (Configuration → Storage)

---

## Summary: How to Save $37/month

**Old way (with NAT):**
- All Lambdas in VPC
- NAT Gateway for internet access
- Cost: $32/month for NAT + $10 data transfer

**New way (VPC Endpoints):**
- Only Redis-using Lambdas in VPC
- VPC Endpoints for AWS services (FREE!)
- External API Lambdas outside VPC (free internet)
- Cost: $0 for networking!

**Simple rule:**
- 🔴 Lambda uses Redis → Put in VPC
- 🟢 Lambda calls external API → Keep outside VPC
- ✅ Everyone can access DynamoDB/S3 via endpoints or default

**Your total cost: $86-136/month (vs $123-173 with NAT)**

---

## Quick Reference

### Lambdas IN VPC (need Redis):
```
detect-clips        ✅ In VPC
finalize           ✅ In VPC
websocket-handler  ✅ In VPC
queue-consumer     ✅ In VPC (optional)
```

### Lambdas OUTSIDE VPC (need internet):
```
transcribe         ❌ No VPC (calls Groq/AssemblyAI)
download           ❌ No VPC (calls YouTube)
process-clip       ❌ No VPC (only S3, no Redis)
api-gateway        ❌ No VPC
upload-api-gateway ❌ No VPC
```

### VPC Endpoints (FREE!):
```
DynamoDB Gateway Endpoint  ✅ $0/month
S3 Gateway Endpoint        ✅ $0/month
```

---

## Next Steps

1. Follow this guide instead of the original for VPC setup
2. Create VPC with NO NAT Gateway
3. Add DynamoDB + S3 VPC Endpoints (free!)
4. Only attach VPC to Lambdas that need Redis
5. Save $37/month! 💰

Everything else remains the same - CloudFormation stacks, environment variables, integration code all work exactly the same!
