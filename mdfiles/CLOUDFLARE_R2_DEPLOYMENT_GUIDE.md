# 🚀 Deployment Guide for Cloudflare R2 Storage

## IMPORTANT: Architecture Changes for R2

**You're using Cloudflare R2 (`opus-clip-videos`)** instead of AWS S3. This changes your deployment significantly!

---

## 🎯 Key Differences with R2

### What Changes:

| Component | With AWS S3 | With Cloudflare R2 |
|-----------|-------------|-------------------|
| **Storage Location** | AWS S3 (same region) | Cloudflare R2 (external) |
| **Lambda Access** | Direct via VPC Endpoint (FREE) | Internet access required |
| **VPC Architecture** | Optional, with VPC Endpoints | ❌ **Cannot use VPC** without NAT |
| **Redis Support** | ✅ Yes (with VPC) | ❌ **No** (requires NAT Gateway $32/mo) |
| **S3 Lifecycle Rules** | ✅ Yes (CloudFormation) | ❌ No (must use R2 dashboard) |
| **S3 VPC Endpoint** | ✅ FREE | ❌ Not applicable |
| **Cost** | Lower with VPC Endpoints | Same, but simpler |

### The Problem:

**Cloudflare R2 is accessed over the public internet**, not within AWS network.

- **Lambdas in VPC** cannot access internet (need NAT Gateway = $32/month)
- **Lambdas outside VPC** can access R2 but cannot access Redis (Redis is in VPC)
- **You can't have both R2 access AND Redis without NAT Gateway**

---

## 💰 Your Options:

### Option A: Deploy WITHOUT Redis or VPC (Recommended) ⭐⭐⭐

**Architecture:**
```
ALL Lambdas outside VPC
    ↓
    Internet (FREE access)
    ↓
    ├→ Cloudflare R2 (opus-clip-videos)
    ├→ DynamoDB (AWS SDK)
    ├→ External APIs (Groq, YouTube)
    └→ CloudWatch Logs (built-in)
```

**Benefits:**
- ✅ Simplest architecture
- ✅ Works perfectly with R2
- ✅ No VPC complexity
- ✅ Lowest cost: **$5-29/month (Year 1)** / **$67-122/month (After)**
- ✅ All features work

**Drawbacks:**
- ⚠️ No Redis caching (queries ~200ms instead of 10ms)
- ⚠️ No Groq API response caching

**Best for:** Your situation! Budget-conscious, Year 1, R2 storage

---

### Option B: Use NAT Gateway for Redis + R2 (Expensive)

**Architecture:**
```
Lambdas in VPC
    ↓
    NAT Gateway ($32/month!)
    ↓
    Internet Gateway
    ↓
    ├→ Cloudflare R2
    ├→ Redis (same VPC)
    └→ External APIs
```

**Benefits:**
- ✅ Can use Redis caching
- ✅ Fast queries (10ms)

**Drawbacks:**
- ❌ Costs **$32/month extra** for NAT Gateway
- ❌ More complex setup
- ❌ Total: **$52-76/month (Year 1)** / **$114-169/month (After)**

**Best for:** High-traffic production (1,000+ videos/day) where performance justifies cost

---

### Option C: Migrate to AWS S3 (Future Option)

You could migrate from R2 to AWS S3 later to enable:
- VPC Endpoints (FREE)
- Redis caching without NAT
- Lower costs

**Not recommended now** - R2 is working fine for you!

---

## 📋 Recommended Deployment Path (Option A)

**Follow this modified deployment guide:**

---

## Phase 1: Request Lambda Concurrency ✅

**Same as original guide** - No changes

1. Go to AWS Support Center
2. Request increase to 5,000 concurrent executions
3. Continue with other phases while waiting

---

## Phase 2: ~~VPC Setup~~ **SKIP THIS ENTIRELY!** ⭐

**Since you're using R2 and not using Redis:**

❌ **Skip VPC creation**
❌ **Skip VPC Endpoints**
❌ **Skip Security Groups**

**All Lambdas will stay outside VPC** to access R2 over internet.

**Time saved:** 30 minutes
**Cost saved:** No VPC complexity

---

## Phase 3: Deploy CloudFormation Stacks

Deploy these stacks only:

### 3.1 ✅ Deploy DynamoDB Stack

**No changes** - Follow original guide Phase 3.1

```
Stack name: video-processing-dynamodb-prod

Parameters:
Environment: prod
```

**Status:** ✅ You already have this deployed!

---

### 3.2 ✅ Deploy SQS Stack

**No changes** - Follow original guide Phase 3.2

```
Stack name: video-processing-sqs-prod

Parameters:
Environment: prod
```

**Status:** ✅ You already have this deployed!

---

### 3.3 ❌ **SKIP Redis Stack**

**Don't deploy Redis** - Can't use it with R2 without NAT Gateway

**Skip this stack entirely.**

---

### 3.4 ❌ **SKIP S3 Lifecycle Stack**

**Why skip:** R2 is not AWS S3, CloudFormation can't manage R2 lifecycle rules

**Instead: Configure lifecycle rules in Cloudflare R2 Dashboard**

#### Configure R2 Lifecycle Rules:

1. **Go to Cloudflare Dashboard:**
   - Login: https://dash.cloudflare.com
   - Navigate to: R2 → Buckets → `opus-clip-videos`

2. **Go to Settings or Lifecycle tab** (if available)

3. **Add lifecycle rules** (if supported):
   ```
   Rule 1: Delete processed videos after 30 days
   Prefix: users/
   Delete after: 30 days

   Rule 2: Delete temp files after 1 day
   Prefix: temp/
   Delete after: 1 day
   ```

**Note:** If R2 doesn't support lifecycle rules yet, you'll need to clean up manually or via scheduled Lambda.

---

### 3.5 ❌ **SKIP CloudWatch Alarms Stack**

**You already tried this and it has conflicts.** Skip it for now.

**You'll still get basic monitoring from:**
- CloudWatch Logs (automatic)
- CloudWatch Metrics (automatic)
- SQS queue alarms (already in SQS stack)

---

### 3.6 ✅ Deploy WebSocket API Stack

**No changes** - Follow original guide Phase 3.6

```
Stack name: video-processing-websocket-prod

Parameters:
Environment: prod
WebSocketHandlerLambdaArn: (will update later)
```

**Status:** ✅ You already have this deployed!

---

## Phase 4: Deploy New Lambda Functions

**Key change:** ALL Lambdas stay **OUTSIDE VPC**

### 4.1 ✅ Deploy Queue Consumer Lambda

**No changes** - Follow original guide Phase 4.1

**Important:**
- ✅ Leave VPC as "No VPC"
- ✅ Timeout: 5 minutes
- ✅ Memory: 512 MB

---

### 4.2 ✅ Deploy WebSocket Handler Lambda

**No changes** - Follow original guide Phase 4.2

**Important:**
- ✅ Leave VPC as "No VPC"
- ✅ Timeout: 30 seconds
- ✅ Memory: 256 MB

---

## Phase 5: Create Lambda Layer

**No changes** - Follow original guide Phase 5

```batch
cd C:\Projects\reframeAI\opus-clip-cloud
create-lambda-layer.bat
```

Upload to Lambda Layers as `shared-utilities`

---

## Phase 6: Environment Variables

**Modified for R2:**

### All Lambda Functions Need:

```bash
# Cloudflare R2 Configuration (your existing R2 credentials)
BUCKET_NAME=opus-clip-videos
AWS_ACCESS_KEY_ID=<your-R2-access-key-id>
AWS_SECRET_ACCESS_KEY=<your-R2-secret-key>
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
R2_PUBLIC_URL=https://pub-xxxxx.r2.dev  # If you have public URL

# DynamoDB Tables
DYNAMODB_TABLE_SESSIONS=prod-video-sessions
DYNAMODB_TABLE_CONNECTIONS=prod-websocket-connections

# WebSocket
WEBSOCKET_API_ENDPOINT=https://xxxxx.execute-api.us-east-1.amazonaws.com/prod

# SQS Queues
SQS_VIDEO_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/930115312558/prod-video-processing-queue
SQS_UPLOAD_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/930115312558/prod-upload-processing-queue

# Feature Flags
ENABLE_S3_SHARDING=true
ENVIRONMENT=prod

# NO REDIS VARIABLES (not using Redis)
```

### Important Notes:

1. **Keep your existing R2 credentials** - Don't change them!
2. **R2 uses S3-compatible API** - Your Lambda code should already work
3. **All Lambdas get same variables** - No VPC/non-VPC split

---

## Phase 7: Lambda Integration

**No changes to integration code** - Follow original guide Phase 7

**Key points:**
- ✅ Attach Lambda Layer to all functions
- ✅ All integration code works with R2 (S3-compatible)
- ✅ S3 sharding utilities work with R2
- ⚠️ Redis utilities will gracefully fallback to DynamoDB (automatic)

### Lambda Functions to Integrate:

- [ ] detect-clips (already done)
- [ ] transcribe-apis
- [ ] download
- [ ] process-clip
- [ ] finalize

**Follow the copy-paste code from Phase 7 in the original guide.**

---

## Phase 8: Update IAM Roles

**Modified for R2:**

### For ALL Lambda Functions:

1. **Open Lambda Function**
2. **Configuration → Permissions**
3. **Click Role name**
4. **Attach these policies:**
   - ✅ `AmazonDynamoDBFullAccess`
   - ✅ `CloudWatchFullAccess`
   - ✅ `AmazonSQSFullAccess`
   - ❌ **DO NOT attach** `AmazonS3FullAccess` (you're using R2, not S3)

5. **Create WebSocket policy** (same as original guide)

6. **Verify VPC Configuration:**
   - ✅ **ALL Lambdas must show "No VPC"**
   - ❌ Do NOT configure VPC for any Lambda

---

## Phase 9: Frontend Setup

**No changes** - Follow original guide Phase 9

```env
# reframe-ai/.env.local
VITE_WEBSOCKET_URL=wss://xxxxx.execute-api.us-east-1.amazonaws.com/prod
VITE_ENABLE_WEBSOCKET=true
VITE_ENABLE_CACHE=true

# Your existing R2 configuration (keep as-is)
```

---

## Phase 10: Testing

**No changes** - Follow original guide Phase 10

Test that:
- ✅ Videos upload to R2
- ✅ Processing works end-to-end
- ✅ Clips saved to R2
- ✅ WebSocket updates work
- ✅ No errors in CloudWatch Logs

---

## Phase 11: Monitoring

**Simplified without alarms stack:**

1. **CloudWatch Logs:**
   - Check Lambda logs for errors
   - Look for "Scalability utilities loaded successfully"

2. **CloudWatch Metrics:**
   - Lambda concurrent executions
   - Lambda errors
   - Lambda duration

3. **SQS Monitoring:**
   - Queue depth (already has alarms from SQS stack)
   - Messages processed

4. **Cost Explorer:**
   - Set budget alert for $50/month (Year 1)
   - Monitor R2 costs in Cloudflare dashboard

---

## 📊 Your Final Architecture

```
┌─────────────────────────────────────────────────┐
│         ALL LAMBDAS (Outside VPC)               │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │transcribe│  │ download │  │ detect-  │     │
│  │  -apis   │  │          │  │  clips   │     │
│  └──────────┘  └──────────┘  └──────────┘     │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ process- │  │ finalize │  │websocket │     │
│  │   clip   │  │          │  │ handler  │     │
│  └──────────┘  └──────────┘  └──────────┘     │
└─────────────────────────────────────────────────┘
                    ↓
        ┌───────────┴───────────┐
        ↓                       ↓
  ┌─────────────┐      ┌─────────────┐
  │ Cloudflare  │      │  AWS Servic│
  │     R2      │      │   DynamoDB  │
  │ opus-clip-  │      │     SQS     │
  │   videos    │      │  CloudWatch │
  └─────────────┘      │  WebSocket  │
                       └─────────────┘
```

**Benefits:**
- ✅ Simple architecture
- ✅ No VPC complexity
- ✅ All Lambdas can access R2 (internet)
- ✅ All Lambdas can access DynamoDB (AWS SDK)
- ✅ Lowest cost

**Trade-offs:**
- ⚠️ No Redis caching (queries 200ms vs 10ms)
- ⚠️ No Groq API caching

---

## 💰 Cost Breakdown (R2 + No Redis)

### Monthly Costs:

| Service | Year 1 (Free Tier) | After Year 1 |
|---------|-------------------|--------------|
| **Lambda** | $0-20 | $50-100 |
| **DynamoDB** | $0 (free tier) | $5 |
| **SQS** | $0-0.50 | $1 |
| **CloudWatch** | $2-5 | $7-11 |
| **WebSocket** | $3 | $3 |
| **Data Transfer OUT** | $0 (100GB free) | $1-2 |
| **Redis** | **$0 (skipped)** | **$0** |
| **VPC/NAT** | **$0 (skipped)** | **$0** |
| **Cloudflare R2** | See R2 dashboard | See R2 dashboard |
| **TOTAL AWS** | **$5-29/month** | **$67-122/month** |

**Plus R2 costs from Cloudflare** (separate billing)

### R2 Costs (Cloudflare):

- Storage: $0.015/GB/month (10GB = $0.15/month)
- Operations: Very cheap (millions of operations included)
- Egress: **FREE!** (R2's biggest benefit)

**Total Combined: ~$10-35/month (Year 1) / ~$70-130/month (After)**

---

## 🎯 Summary of Changes from Original Guide

| Phase | Original Guide | With R2 |
|-------|---------------|---------|
| **Phase 1** | Request concurrency | ✅ Same |
| **Phase 2** | Create VPC + Endpoints | ❌ **SKIP** |
| **Phase 3.1** | DynamoDB | ✅ Same |
| **Phase 3.2** | SQS | ✅ Same |
| **Phase 3.3** | Redis | ❌ **SKIP** |
| **Phase 3.4** | S3 Lifecycle | ❌ **SKIP (use R2 dashboard)** |
| **Phase 3.5** | CloudWatch Alarms | ❌ **SKIP (conflicts)** |
| **Phase 3.6** | WebSocket | ✅ Same |
| **Phase 4** | Deploy Lambdas | ✅ Same (all outside VPC) |
| **Phase 5** | Lambda Layer | ✅ Same |
| **Phase 6** | Env Variables | ⚠️ **Modified (no Redis, keep R2 creds)** |
| **Phase 7** | Code Integration | ✅ Same |
| **Phase 8** | IAM Roles | ⚠️ **Modified (no VPC config)** |
| **Phase 9** | Frontend | ✅ Same |
| **Phase 10** | Testing | ✅ Same |
| **Phase 11** | Monitoring | ⚠️ **Simplified** |

---

## ✅ Your Deployment Checklist

### Already Complete:
- [x] DynamoDB stack deployed
- [x] SQS stack deployed
- [x] Redis stack deployed (but won't be used)
- [x] WebSocket stack deployed

### Still To Do:

#### Infrastructure:
- [ ] ~~VPC Setup~~ (SKIP)
- [ ] ~~S3 Lifecycle~~ (Use R2 dashboard)
- [ ] ~~CloudWatch Alarms~~ (SKIP)

#### Lambda Functions:
- [ ] Create Lambda Layer
- [ ] Deploy queue-consumer Lambda
- [ ] Deploy websocket-handler Lambda (already created!)
- [ ] Add environment variables to ALL Lambdas
- [ ] Attach IAM policies to ALL Lambdas
- [ ] **Verify ALL Lambdas are "No VPC"**
- [ ] Attach Lambda Layer to ALL Lambdas
- [ ] Integrate code in 4 core Lambdas (transcribe-apis, download, process-clip, finalize)

#### Testing:
- [ ] Test video upload to R2
- [ ] Test end-to-end processing
- [ ] Check CloudWatch Logs
- [ ] Verify WebSocket updates

---

## 🚨 Critical Reminders

1. **ALL Lambdas MUST stay outside VPC** - They need internet for R2
2. **Keep your existing R2 credentials** - Don't change them
3. **No Redis variables needed** - Redis stack won't be used
4. **S3 sharding still works** - It's just prefix naming
5. **Code works with R2** - S3-compatible API

---

## 🎉 Benefits of Your Setup

**With R2 + No Redis:**

✅ **Simplest possible architecture**
✅ **Lowest AWS cost** ($5-29/mo Year 1)
✅ **FREE R2 egress** (huge savings vs S3)
✅ **No VPC complexity**
✅ **All features work**
✅ **256x S3 sharding** (same performance)
✅ **Real-time WebSocket updates**
✅ **1,000+ concurrent users supported**

⚠️ **Slightly slower queries** (200ms vs 10ms - barely noticeable)

---

## 📖 Next Steps

**Continue from Phase 5** of this guide:

1. Create Lambda Layer
2. Add environment variables (use the R2-specific template above)
3. Update IAM roles (no S3 policy, verify No VPC)
4. Integrate Lambda code
5. Test everything

**You're using the most cost-effective setup possible!** 🚀💰

---

## Questions?

**Common Questions:**

### Q: Can I add Redis later?
**A:** Yes, but you'll need NAT Gateway ($32/month) or migrate to AWS S3 with VPC Endpoints (free).

### Q: Will performance be bad without Redis?
**A:** No! DynamoDB queries are ~200ms, which is perfectly fast for most users. Redis makes it 10ms, but 200ms is unnoticeable to humans.

### Q: Does S3 sharding work with R2?
**A:** Yes! S3 sharding is just prefix naming (`users/a1/user123/` instead of `users/user123/`). Works identically with R2.

### Q: Should I migrate to AWS S3?
**A:** Not necessarily. R2 has **FREE egress** which can save you a lot vs S3. Stick with R2 unless you really need Redis caching.

---

**You're all set! Follow this guide instead of the original.** 🎯
