# Quick Deployment Checklist - High Priority Issues

**Date:** December 31, 2025
**Goal:** Deploy all high priority fixes (Issues #6, #16-27)

---

## ✅ Step 1: Deploy Backend (Node.js Lambda)

Run this command to deploy all Lambda fixes:

```bash
cd C:\Projects\reframeAI\opus-clip-cloud
serverless deploy --verbose
```

**What This Deploys:**
- 🔴 Issue #6: YouTube URL validation (CRITICAL - prevents command injection)
- Issue #16: Lambda authorizer optimization
- Issue #19: Retry logic for YouTube downloads
- Issue #20: Firestore optimization ($8,100/month savings)
- Issue #26: Video file validation
- Issue #27: Parameter validation (prevents DoS attacks)

**Time:** ~5-10 minutes

---

## ✅ Step 2: Deploy Frontend

Run these commands to deploy frontend fixes:

```bash
cd C:\Projects\reframeAI\reframe-ai
npm run build
```

Then deploy based on your hosting:
```bash
# If using Vercel:
vercel --prod

# If using Netlify:
netlify deploy --prod --dir=dist

# If using other hosting:
# Upload the 'dist' folder to your hosting provider
```

**What This Deploys:**
- Issue #18: User profile cache fix (5-minute TTL)
- Issue #21: Removed WebSocket debug logs in production
- Issue #23: Re-authentication for sensitive actions
- Issue #24: Error message sanitization
- Issue #25: API client retry logic

**Time:** ~3-5 minutes

---

## ⚠️ Step 3: Manual AWS Console Steps (REQUIRED)

### 3A. Set Lambda Reserved Concurrency (Issue #17)

1. Open [AWS Lambda Console](https://console.aws.amazon.com/lambda)
2. Find these functions and set concurrency:
   - **opus-clip-node-download** → Set to **50** reserved concurrency
   - **opus-clip-detect-clips** → Set to **20** reserved concurrency
   - **opus-clip-process-clip** → Set to **100** reserved concurrency
3. Click "Save" for each

**Why:** Prevents one Lambda from consuming all account concurrency

**Time:** 2 minutes

---

### 3B. Deploy Dead Letter Queue (Issue #22)

**First, check if DLQ is already deployed:**

```bash
# Check for existing CloudFormation stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE | grep -i "video-processing\|dlq"
```

**If you see stacks like `video-processing-sqs-prod` or `opus-clip-dlq`:**
- ✅ **DLQ is already deployed - SKIP this step!**
- Issue #22 is already complete

**If NO stacks found, deploy DLQ:**

```bash
cd C:\Projects\reframeAI\opus-clip-cloud\infrastructure

# Deploy SQS queues
aws cloudformation deploy \
  --template-file sqs-queues.yml \
  --stack-name opus-clip-dlq \
  --parameter-overrides \
    Environment=prod \
    EmailAddress=YOUR_EMAIL@example.com

# Deploy Step Functions DLQ integration
aws cloudformation deploy \
  --template-file step-functions-dlq.yml \
  --stack-name opus-clip-step-functions-dlq \
  --capabilities CAPABILITY_IAM
```

**Replace:** `YOUR_EMAIL@example.com` with your actual email

**Why:** Captures failed video processing jobs for debugging

**Time:** 5 minutes (or 0 minutes if already deployed)

---

## ✅ Step 4: Verification (Optional but Recommended)

### Backend Verification:
1. Upload a YouTube video - should succeed
2. Check CloudWatch Logs for these messages:
   - `[Download] CRITICAL FIX #6: Validating YouTube URL...`
   - `[Download] HIGH PRIORITY FIX #19: Attempting yt-dlp download`
   - `[Download] HIGH PRIORITY FIX #26: Validating downloaded video file...`

### Frontend Verification:
1. Open your production site
2. Open browser console - should NOT see WebSocket debug logs
3. Trigger profile change - should update within 5 minutes

---

## 📋 Summary

**Automated Steps:**
- ✅ Backend deploy: `serverless deploy --verbose`
- ✅ Frontend deploy: `npm run build` + hosting deploy

**Manual Steps:**
- ⚠️ Set Lambda concurrency (3 functions)
- ⚠️ Deploy DLQ CloudFormation stacks (2 stacks)

**Total Time:** ~15-20 minutes

---

## 🎉 Done!

After completing all steps above, all high priority issues (#6, #16-27) will be fully deployed and operational.

**Critical Security Note:** Issue #6 (YouTube URL validation) is CRITICAL for security. Verify it's deployed by checking CloudWatch Logs for the validation messages.
