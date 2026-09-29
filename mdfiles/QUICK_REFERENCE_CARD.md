# 📋 Quick Reference Card - Keep This Open While Deploying

## 🎯 Main Goal
Make your app support **1,000+ concurrent users** with **256x faster** S3 operations

---

## 📚 3 Files You Need

1. **`FINAL_COMPLETE_SUMMARY.md`** - Overview (read first!)
2. **`COMPLETE_DEPLOYMENT_CHECKLIST.md`** - Step-by-step guide ⭐
3. **`QUICK_LAMBDA_INTEGRATION.md`** - Copy-paste code ⭐

---

## 💰 Redis Decision First!

**ElastiCache costs $15/month even idle. You can skip it!**

- **Skip Redis (Year 1):** $5-29/month → Save $180/year ⭐
- **Use Redis (Production):** $20-44/month → 20x faster queries

**Guide:** `SKIP_REDIS_GUIDE.md` for detailed comparison

---

## ⚡ Super Quick Summary

### Part 1: AWS Setup (3-4 hours)
**Guide:** `COMPLETE_SCALABILITY_DEPLOYMENT_GUIDE.md`

1. Request Lambda concurrency → 5,000 (wait 1-3 days)
2. ~~Create VPC (30 min)~~ **[Skip if no Redis!]**
3. Deploy 5-6 CloudFormation stacks (45-60 min)
4. Set environment variables (20 min)
5. Deploy 2 new Lambdas (15 min)
6. Update IAM roles (15 min)

### Part 2: Lambda Integration (15 min) ⭐
**Guide:** `QUICK_LAMBDA_INTEGRATION.md`

```bash
# Step 1: Create Layer (5 min)
cd opus-clip-cloud
create-lambda-layer.bat  # Upload to AWS

# Step 2: Integrate 4 Lambdas (10 min)
# Open each Lambda file, copy-paste from guide:
# - transcribe (5 min)
# - download (5 min) - optional if Node.js
# - process-clip (3 min)
# - finalize (3 min)
```

### Part 3: Frontend (5 min) - OPTIONAL
**Guide:** `reframe-ai/FRONTEND_INTEGRATION_GUIDE.md`

Add to `.env.local`:
```env
VITE_WEBSOCKET_URL=wss://xxxxx.execute-api.us-east-1.amazonaws.com/prod
VITE_ENABLE_WEBSOCKET=true
```

### Part 4: Test (30 min)
Upload video → Watch it process → Check logs → Done!

---

## 📁 CloudFormation Stack Order

Deploy in this exact order:

1. **dynamodb.yml** → prod-video-sessions table ✅ Required
2. **sqs-queues.yml** → Processing queues ✅ Required
3. **redis.yml** → Cache cluster ⚠️ **[Optional - Skip to save $15/month!]**
4. **s3-lifecycle.yml** → Auto-cleanup ✅ Required
5. **cloudwatch-alarms.yml** → Monitoring (confirm email!) ✅ Required
6. **websocket-api.yml** → Real-time API ✅ Required

**Note down these outputs:**
- Redis Endpoint (if using Redis)
- WebSocket URL
- SQS Queue URLs

---

## 🔧 Environment Variables (Copy-Paste)

### If Using Redis:
Add to ALL Lambda functions:
```
REDIS_ENDPOINT=<from CloudFormation>  [VPC Lambdas only]
REDIS_PORT=6379                       [VPC Lambdas only]
DYNAMODB_TABLE_SESSIONS=prod-video-sessions
DYNAMODB_TABLE_CONNECTIONS=prod-websocket-connections
WEBSOCKET_API_ENDPOINT=<from CloudFormation>
SQS_VIDEO_QUEUE_URL=<from CloudFormation>
SQS_UPLOAD_QUEUE_URL=<from CloudFormation>
ENABLE_S3_SHARDING=true
ENVIRONMENT=prod
```

### If NOT Using Redis (Simpler!):
Add to ALL Lambda functions:
```
DYNAMODB_TABLE_SESSIONS=prod-video-sessions
DYNAMODB_TABLE_CONNECTIONS=prod-websocket-connections
WEBSOCKET_API_ENDPOINT=<from CloudFormation>
SQS_VIDEO_QUEUE_URL=<from CloudFormation>
SQS_UPLOAD_QUEUE_URL=<from CloudFormation>
ENABLE_S3_SHARDING=true
ENVIRONMENT=prod
```

---

## 🔍 Lambda Integration Status

| Lambda | Status | Action | Time |
|--------|--------|--------|------|
| detect-clips | ✅ Done | None | 0 min |
| transcribe | ⚠️ Needs | Copy-paste | 5 min |
| download | ⚠️ Needs | Copy-paste | 5 min |
| process-clip | ⚠️ Needs | Copy-paste | 3 min |
| finalize | ⚠️ Needs | Copy-paste | 3 min |
| queue-consumer | ✅ Done | Deploy ZIP | 0 min |
| websocket-handler | ✅ Done | Deploy ZIP | 0 min |

---

## ✅ Testing Checklist

After deployment, verify:

- [ ] CloudFormation stacks all show CREATE_COMPLETE
- [ ] Lambda Layer attached to all functions
- [ ] Environment variables set
- [ ] Test video processes end-to-end
- [ ] CloudWatch Logs show "utilities loaded successfully"
- [ ] CloudWatch Metrics show custom metrics
- [ ] CloudWatch Alarms in OK state
- [ ] DynamoDB tables have records
- [ ] WebSocket connects in browser DevTools
- [ ] No polling in Network tab

---

## 🆘 Common Issues - Quick Fixes

| Issue | Solution |
|-------|----------|
| Module not found | Attach Lambda Layer |
| UTILITIES_AVAILABLE=False | OK! Code has fallback |
| Redis timeout | Check VPC + security groups |
| WebSocket not connecting | Verify URL in .env |
| High costs | NAT gateway ($35/mo) - use VPC endpoints |
| Lambda errors | Check CloudWatch Logs |

---

## 📊 Expected Results

### Performance:
- S3: 3,500 → **896,000 PUT/sec** (256x)
- Queries: 200ms → **10ms with Redis** (20x faster) or 200ms without Redis
- Users: 30-100 → **1,000+** (10x more)

### Cost:
| Setup | Year 1 | After Year 1 | 3-Year Total |
|-------|--------|--------------|--------------|
| **Without Redis** ⭐ | $5-29/mo | $67-122/mo | $1,668-3,516 |
| **With Redis** | $20-44/mo | $82-137/mo | $2,208-4,164 |
| **Old (with NAT)** ❌ | $57-89/mo | $122-177/mo | $3,888-5,604 |

**Savings:**
- Skip Redis: Save $180/year vs with Redis
- Skip NAT Gateway: Save $444/year
- **Combined savings: $624-1,116/year!** 💰

**Guides:**
- `SKIP_REDIS_GUIDE.md` - How to skip Redis
- `COST_OPTIMIZATION_GUIDE.md` - VPC Endpoints explanation

---

## 🎯 What To Do RIGHT NOW

1. Open **`COMPLETE_DEPLOYMENT_CHECKLIST.md`**
2. Start with **PART 1** (AWS Infrastructure)
3. Check off boxes as you complete each step
4. When you reach Lambda integration, use **`QUICK_LAMBDA_INTEGRATION.md`**

---

## ⏱️ Time Breakdown

| Task | Time |
|------|------|
| Lambda concurrency request | 15 min + 1-3 days wait |
| VPC creation | 30 min |
| CloudFormation deployment | 60 min |
| Environment variables | 20 min |
| New Lambda deployment | 15 min |
| IAM role updates | 15 min |
| **Lambda Layer creation** | 5 min |
| **Lambda integration** | 15 min |
| Frontend .env update | 5 min |
| Testing | 30 min |
| **TOTAL ACTIVE TIME** | **~4-5 hours** |

---

## 💡 Pro Tips

1. **Deploy infrastructure while waiting for Lambda concurrency approval**
2. **Test after each CloudFormation stack** - don't deploy all at once
3. **Start with detect-clips** - it's already integrated!
4. **Lambda integration is copy-paste** - don't write code from scratch
5. **Frontend already works** - WebSocket is optional

---

## 📞 Files Quick Access

**Start Here:**
- `FINAL_COMPLETE_SUMMARY.md` - Overview

**Deployment:**
- `COMPLETE_DEPLOYMENT_CHECKLIST.md` - Main guide
- `AWS_CONSOLE_SETUP_GUIDE.md` - AWS Console steps

**Integration:**
- `QUICK_LAMBDA_INTEGRATION.md` - Copy-paste code
- `LAMBDA_FUNCTIONS_STATUS.md` - Lambda status
- `reframe-ai/FRONTEND_INTEGRATION_GUIDE.md` - Frontend

**Scripts:**
- `create-lambda-layer.bat` - Run this (Windows)
- `create-lambda-layer.sh` - Run this (Mac/Linux)

**Templates:**
- `opus-clip-cloud/infrastructure/*.yml` - 6 templates

---

## 🎉 You're Ready!

Everything is prepared. Just follow the checklist step by step.

**Total work needed from you:** ~4-5 hours

**Result:** Fully scalable app supporting 1,000+ concurrent users!

**Good luck! 🚀**
