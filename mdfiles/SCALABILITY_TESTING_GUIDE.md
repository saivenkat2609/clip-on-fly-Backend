# 🧪 SCALABILITY TESTING GUIDE

**Complete checklist to verify your application can handle multiple users without errors.**

**Time required**: 45-60 minutes
**Goal**: Confirm application is production-ready and scalable

---

## 📋 Pre-Test Checklist

Before starting tests, verify these are deployed:

- [ ] Lambda Layer `shared-utilities` attached to all Lambdas
- [ ] DynamoDB tables created (`prod-video-sessions`, `prod-websocket-connections`)
- [ ] WebSocket API deployed and URL in `.env` file
- [ ] All Lambda functions updated with correct imports (`from shared.xxx`)
- [ ] CloudWatch custom namespace `VideoProcessing` exists
- [ ] Cloudflare R2 bucket `opus-clip-videos` configured

**If any missing**: See `FIX_IMPORTS_DEPLOY_NOW.md` and `COMPLETE_SCALABILITY_DEPLOYMENT_GUIDE.md`

---

## 🎯 Test Categories

1. **Basic Functionality** - Single user, end-to-end workflow
2. **Concurrent Users** - Multiple uploads simultaneously
3. **Error Handling** - API failures, timeouts, invalid inputs
4. **Monitoring** - CloudWatch metrics, logs, alarms
5. **Real-time Updates** - WebSocket live updates
6. **Performance** - Throughput, latency, resource usage
7. **Data Integrity** - File storage, DynamoDB consistency

---

## ✅ TEST 1: Basic End-to-End Workflow (5 minutes)

**Goal**: Verify complete video processing pipeline works

### Steps:
1. **Upload a short video** (1-2 minutes, YouTube URL or file)
2. **Wait for processing** to complete (2-5 minutes)
3. **Check dashboard** shows clips

### Expected Results:
- ✅ Video status: `Pending` → `Processing` → `Completed`
- ✅ 2-5 clips generated with viral titles
- ✅ Clips playable in dashboard
- ✅ No errors in dashboard console

### Verification:
**DynamoDB** (`prod-video-sessions`):
- [ ] Session exists with your `session_id`
- [ ] Status = `completed`
- [ ] `clips_count` = 2-5
- [ ] `updated_at` timestamp recent

**S3/R2** (CloudFlare R2 or S3):
- [ ] Original video: `{shard}/{user_id}/{session_id}/original_video.mp4`
- [ ] Transcript: `{shard}/{user_id}/{session_id}/transcript.json`
- [ ] Clips: `{shard}/{user_id}/{session_id}/clips/clip_0_9x16.mp4`

**CloudWatch Metrics**:
- [ ] At least 2 metrics visible (AIAPICall, AIAPILatency)

### Pass/Fail:
- ✅ **PASS**: All clips generated, no errors
- ❌ **FAIL**: Processing stuck, errors in logs, no clips

---

## 🚀 TEST 2: Concurrent Users (15 minutes)

**Goal**: Verify application handles multiple simultaneous uploads

### Setup:
Prepare **3 different test videos** (1-2 minutes each):
- Video 1: YouTube URL
- Video 2: Local file upload
- Video 3: Another YouTube URL

### Steps:
1. **Open 3 browser tabs** (or use 3 different browsers/incognito)
2. **Login as same user** (or 3 different users)
3. **Upload all 3 videos simultaneously** (within 10 seconds)
4. **Watch all 3 process** in parallel

### Expected Results:
- ✅ All 3 videos show in dashboard immediately
- ✅ All 3 process simultaneously (not queued)
- ✅ All 3 complete successfully (2-5 min each)
- ✅ No session ID conflicts
- ✅ No S3 upload conflicts

### Verification:
**DynamoDB**:
- [ ] 3 separate sessions with unique `session_id`
- [ ] All 3 have status `completed`
- [ ] Timestamps show parallel processing (started within 1 minute of each other)

**CloudWatch Logs**:
- [ ] 3 separate Lambda execution streams
- [ ] No "ResourceConflictException" errors
- [ ] No "TooManyRequestsException" errors

**S3/R2**:
- [ ] All 3 videos in separate folders
- [ ] No overwritten files
- [ ] All clips accessible

### Pass/Fail:
- ✅ **PASS**: All 3 videos process successfully in parallel
- ⚠️ **PARTIAL**: 1-2 videos fail but others succeed (check logs)
- ❌ **FAIL**: All videos fail or get stuck

---

## 🔥 TEST 3: Stress Test - 10 Concurrent Uploads (20 minutes)

**Goal**: Test true scalability with high concurrency

### Setup:
You'll need a script to automate uploads. Use this Python script:

```python
import requests
import time
from concurrent.futures import ThreadPoolExecutor

# Your API endpoint (replace with your actual API Gateway URL)
API_URL = "https://your-api-gateway-url.amazonaws.com/prod/upload"
AUTH_TOKEN = "your-firebase-auth-token"

test_videos = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    # Add 9 more YouTube URLs
]

def upload_video(index, url):
    try:
        response = requests.post(
            API_URL,
            json={"youtube_url": url},
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        )
        print(f"[{index}] Uploaded: {response.status_code}")
        return response.json()
    except Exception as e:
        print(f"[{index}] Error: {e}")
        return None

# Upload 10 videos simultaneously
with ThreadPoolExecutor(max_workers=10) as executor:
    results = executor.map(lambda i: upload_video(i, test_videos[i]), range(10))

print(f"Completed: {sum(1 for r in results if r)}/10")
```

### Steps:
1. **Run script** to upload 10 videos simultaneously
2. **Monitor CloudWatch** Lambda metrics (Invocations, Concurrent Executions)
3. **Check all 10 videos** process successfully
4. **Wait 10 minutes** for all to complete

### Expected Results:
- ✅ All 10 videos accepted (HTTP 200)
- ✅ All 10 appear in dashboard
- ✅ 8-10 complete successfully (80%+ success rate acceptable)
- ✅ Lambda concurrent executions peak at 10+
- ✅ No throttling errors

### Verification:
**CloudWatch → Lambda → Metrics**:
- [ ] **Invocations**: 50+ (10 videos × 5 Lambdas)
- [ ] **Concurrent Executions**: Peak 10-15
- [ ] **Errors**: < 5%
- [ ] **Throttles**: 0

**DynamoDB → Metrics**:
- [ ] **UserErrors**: 0
- [ ] **SystemErrors**: 0
- [ ] **ConsumedReadCapacityUnits**: Normal (no spikes)
- [ ] **ConsumedWriteCapacityUnits**: Normal

**S3/R2**:
- [ ] 10 separate video folders
- [ ] All original videos uploaded
- [ ] Most clips generated (some may fail if stress too high)

### Pass/Fail:
- ✅ **PASS**: 80%+ success rate, no throttling
- ⚠️ **ACCEPTABLE**: 60-79% success, some throttling (scale up Lambda concurrency)
- ❌ **FAIL**: <60% success, heavy throttling, DB errors

---

## 🛡️ TEST 4: Error Handling & Fault Tolerance (10 minutes)

**Goal**: Verify graceful degradation when APIs fail

### Test 4.1: Invalid YouTube URL
**Steps**:
1. Upload invalid URL: `https://www.youtube.com/watch?v=INVALID123`
2. Check error handling

**Expected**:
- ✅ User sees clear error message
- ✅ Session marked as `failed` in DynamoDB
- ✅ No partial files in S3
- ✅ Error logged in CloudWatch

### Test 4.2: Simulate API Failure (Groq)
**Steps**:
1. Lambda Console → `opus-detect` → Configuration → Environment variables
2. Change `GROQ_API_KEY` to `invalid-key-test`
3. Upload a video
4. Check logs and result

**Expected**:
- ✅ Logs show: "Circuit breaker open or API failed"
- ✅ Falls back to non-AI clip detection (2 clips generated)
- ✅ Video still processes successfully
- ✅ No complete pipeline failure

**Restore**: Change `GROQ_API_KEY` back to correct value!

### Test 4.3: Large Video (Timeout Test)
**Steps**:
1. Upload a 15-20 minute video
2. Monitor Lambda timeouts

**Expected**:
- ✅ Download completes within 10 min (or Lambda timeout adjusted)
- ✅ Processing completes within State Machine timeout
- ✅ If timeout occurs, clear error message to user

### Pass/Fail:
- ✅ **PASS**: Errors handled gracefully, no crashes
- ❌ **FAIL**: Unhandled exceptions, incomplete cleanup

---

## 📊 TEST 5: CloudWatch Metrics (5 minutes)

**Goal**: Verify all 7 custom metrics are publishing

### Steps:
1. **Upload and process 1 video**
2. **Wait 3 minutes** after completion
3. **CloudWatch Console** → **Metrics** → **VideoProcessing**

### Expected Metrics:
- [ ] **AIAPICall** - Count (should be 2-3)
- [ ] **AIAPILatency** - Milliseconds (200-2000ms)
- [ ] **TranscriptionTime** - Milliseconds (5000-30000ms)
- [ ] **ClipDetectionTime** - Milliseconds (1000-5000ms)
- [ ] **ClipProcessingTime** - Milliseconds (10000-60000ms per clip)
- [ ] **ClipsGenerated** - Count (2-5)
- [ ] **VideoProcessingComplete** - Count (1)

### Verification:
**For each metric**:
- [ ] Has data points (not empty graph)
- [ ] Values are reasonable (not 0 or extremely high)
- [ ] Timestamp is recent (within last 5 minutes)

### Pass/Fail:
- ✅ **PASS**: All 7 metrics present with reasonable values
- ⚠️ **PARTIAL**: 4-6 metrics present (check missing Lambda logs)
- ❌ **FAIL**: 0-3 metrics (imports broken, Layer not attached)

---

## 🌐 TEST 6: WebSocket Real-time Updates (5 minutes)

**Goal**: Verify Live badge and instant dashboard updates

### Steps:
1. **Open dashboard** in browser
2. **Open Browser DevTools** → **Console** tab (F12)
3. **Upload a video**
4. **Watch console logs** while processing

### Expected Console Output:
```
[useWebSocket] Creating WebSocket client...
[useWebSocket] Connecting to session: abc123...
[useWebSocket] Connection opened
📡 Processing progress: { event: 'processing_progress', status: 'transcribing', data: { progress: 20 } }
📡 Processing progress: { event: 'processing_progress', status: 'detecting_clips', data: { progress: 40 } }
📡 Processing progress: { event: 'processing_progress', status: 'processing', data: { progress: 60 } }
✅ Processing complete: { event: 'processing_complete', status: 'completed' }
```

### Expected Dashboard Behavior:
- [ ] **🟢 Live badge** appears when processing starts
- [ ] **Progress updates** without page refresh
- [ ] **Status changes** from Pending → Processing → Completed
- [ ] **Live badge disappears** when processing complete
- [ ] **Clips appear** automatically (no refresh needed)

### Verification:
**WebSocket Connection**:
- [ ] `isConnected = true` in console
- [ ] No connection errors
- [ ] Messages received within 1 second of Lambda execution

**DynamoDB** (`prod-websocket-connections`):
- [ ] Connection record exists while connected
- [ ] Cleaned up after disconnect (within TTL period)

### Pass/Fail:
- ✅ **PASS**: Live updates work, badge shows, no refresh needed
- ⚠️ **PARTIAL**: WebSocket connects but some messages missing
- ❌ **FAIL**: No WebSocket connection, must refresh to see updates

---

## 🔍 TEST 7: Structured Logging (5 minutes)

**Goal**: Verify JSON logs are queryable in CloudWatch Logs Insights

### Steps:
1. **Upload and process 1 video**
2. **CloudWatch Console** → **Logs Insights**
3. **Select log groups**:
   - `/aws/lambda/opus-detect`
   - `/aws/lambda/opus-transcribe`
   - `/aws/lambda/opus-finalize`
4. **Run query**:

```
fields @timestamp, level, service, message, session_id, clip_count
| filter level = "INFO"
| sort @timestamp desc
| limit 20
```

### Expected Results:
- ✅ Logs returned in table format
- ✅ All fields populated (timestamp, level, service, message)
- ✅ JSON structure preserved
- ✅ Easy to filter by session_id

### Additional Queries:

**Find errors**:
```
fields @timestamp, level, message, session_id
| filter level = "ERROR"
| sort @timestamp desc
```

**Track specific session**:
```
fields @timestamp, service, message, current_step
| filter session_id = "your-session-id-here"
| sort @timestamp asc
```

**Performance analysis**:
```
fields @timestamp, service, duration
| filter service = "transcribe-apis"
| stats avg(duration), max(duration), min(duration)
```

### Pass/Fail:
- ✅ **PASS**: All queries return results, logs structured correctly
- ⚠️ **PARTIAL**: Some logs not in JSON format
- ❌ **FAIL**: Queries fail, logs unstructured

---

## 📦 TEST 8: S3 Sharding (Optional - 5 minutes)

**Goal**: Verify files distributed across hash prefixes

### Steps:
1. **Upload 5 videos** from **different users** (if possible)
2. **Check S3/R2 structure**

### Expected Structure:
```
opus-clip-videos/
  └── users/
      ├── 7a/user123/session1/...
      ├── b2/user456/session2/...
      ├── 1f/user789/session3/...
      ├── c5/user012/session4/...
      └── 9e/user345/session5/...
```

### Verification:
- [ ] Videos in different hash prefixes (7a, b2, 1f, etc.)
- [ ] Hash derived from user_id (same user → same prefix)
- [ ] Structure: `users/{hash}/{user_id}/{session_id}/`

### If NOT using sharding:
```
opus-clip-videos/
  └── users/
      ├── user123/session1/...
      ├── user456/session2/...
      └── user789/session3/...
```

### Pass/Fail:
- ✅ **PASS**: Files sharded across prefixes
- ⚠️ **NEUTRAL**: Sharding disabled (check `ENABLE_S3_SHARDING` env var)
- ❌ **FAIL**: Files in wrong structure or conflicting

---

## 🎯 TEST 9: Performance Benchmarks (10 minutes)

**Goal**: Measure key performance indicators

### Metrics to Collect:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Download Time** | < 2 min (for 5 min video) | CloudWatch Logs → opus-download → Search "Download complete" |
| **Transcription Time** | < 30 sec (for 5 min video) | CloudWatch Metrics → TranscriptionTime |
| **Clip Detection** | < 5 sec | CloudWatch Metrics → ClipDetectionTime |
| **Clip Processing** | < 60 sec per clip | CloudWatch Metrics → ClipProcessingTime |
| **Total Pipeline** | < 5 min (for 5 min video) | Dashboard timestamp: Upload → Completed |
| **API Latency (Groq)** | < 2 sec | CloudWatch Metrics → AIAPILatency |
| **WebSocket Latency** | < 1 sec | Browser DevTools → Network → WS messages |

### Steps:
1. **Upload a 5-minute video**
2. **Record timestamps** at each stage
3. **Check CloudWatch Metrics** after completion
4. **Calculate total duration**

### Expected Performance (5 min video):
- ✅ Download: 1-2 min
- ✅ Transcription: 10-30 sec
- ✅ Clip Detection: 2-5 sec
- ✅ Clip Processing: 30-60 sec × 3 clips = 1.5-3 min
- ✅ **Total**: 3-5 minutes

### Pass/Fail:
- ✅ **PASS**: Total < 6 minutes for 5 min video
- ⚠️ **ACCEPTABLE**: 6-10 minutes (optimization needed)
- ❌ **FAIL**: >10 minutes or timeouts

---

## 💰 TEST 10: Cost Validation (5 minutes)

**Goal**: Ensure you're not overpaying for unused services

### Checks:

**1. Lambda VPC Configuration**:
- [ ] All Lambdas show **"No VPC"** (not in VPC)
- **Check**: Lambda Console → Any function → Configuration → VPC

**2. NAT Gateway**:
- [ ] **None created** (saves $32/month)
- **Check**: VPC Console → NAT Gateways → Should be empty

**3. ElastiCache Redis**:
- [ ] **Not deployed** (saves $50/month)
- **Check**: ElastiCache Console → Redis clusters → Should be empty

**4. VPC Endpoints**:
- [ ] **None created** (saves $20/month)
- **Check**: VPC Console → Endpoints → Should be empty or minimal

**5. Lambda Concurrency Limits**:
- [ ] **Reserved concurrency**: Not set (use on-demand)
- **Check**: Lambda → Any function → Configuration → Concurrency

### Expected Monthly Costs (Year 1):

| Service | Cost |
|---------|------|
| Lambda (100 videos/month) | $3-8 |
| DynamoDB (1000 sessions) | $0.30 |
| CloudWatch (7 metrics) | $0.30 |
| S3/R2 Storage (50GB) | $1-2 |
| WebSocket API (10K messages) | $0.01 |
| API Gateway | $1-3 |
| **TOTAL** | **$5-15/month** |

**After Free Tier**: $67-122/month (still cost-effective)

### Pass/Fail:
- ✅ **PASS**: No VPC, No Redis, No NAT Gateway
- ❌ **FAIL**: Expensive services running unnecessarily

---

## 📋 Final Validation Checklist

**Test all these scenarios, then mark complete:**

### Functionality:
- [ ] Single video processes end-to-end successfully
- [ ] 3 concurrent videos process in parallel
- [ ] 10 concurrent uploads (stress test) - 80%+ success rate
- [ ] Invalid input handled gracefully
- [ ] API failure triggers fallback (circuit breaker works)

### Monitoring:
- [ ] All 7 CloudWatch metrics publishing
- [ ] Structured JSON logs searchable in Logs Insights
- [ ] No errors in CloudWatch Alarms
- [ ] DynamoDB tables populated correctly

### Real-time:
- [ ] WebSocket connection stable
- [ ] Live badge shows during processing
- [ ] Dashboard updates without refresh
- [ ] Messages delivered within 1 second

### Performance:
- [ ] 5 min video processes in < 6 minutes
- [ ] API latency < 2 seconds
- [ ] No Lambda timeouts
- [ ] No throttling under 10 concurrent uploads

### Cost:
- [ ] No VPC/NAT Gateway
- [ ] No Redis
- [ ] Expected monthly cost < $30 (Year 1)

### Data Integrity:
- [ ] S3/R2 files not corrupted
- [ ] DynamoDB sessions consistent
- [ ] No session ID conflicts
- [ ] Clips playable in dashboard

---

## 🎉 Success Criteria

**Your application is FULLY SCALABLE when:**

✅ **All 10 tests pass**
✅ **95%+ success rate** on concurrent uploads
✅ **All 7 metrics** visible in CloudWatch
✅ **WebSocket live updates** work flawlessly
✅ **No critical errors** in logs
✅ **Cost under $30/month** (Year 1)

---

## 🚨 Common Issues & Fixes

### Issue: Concurrent uploads fail
**Fix**: Increase Lambda concurrency limit (default: 1000)

### Issue: Metrics not appearing
**Fix**: Check Lambda Layer attached, verify imports (`from shared.xxx`)

### Issue: WebSocket disconnects
**Fix**: Check WebSocket API endpoint URL in `.env`, verify connections in DynamoDB

### Issue: S3 upload conflicts
**Fix**: Enable S3 sharding (`ENABLE_S3_SHARDING=true`)

### Issue: Lambda timeouts
**Fix**: Increase timeout (10 min for download, 5 min for others), increase memory (2048 MB)

---

## 📊 Test Results Template

Use this to record your results:

```
TEST RESULTS - [Date]
===================

✅ Test 1: End-to-End              [ PASS / FAIL ]
✅ Test 2: 3 Concurrent Users      [ PASS / FAIL ]
✅ Test 3: 10 Concurrent (Stress)  [ PASS / FAIL ] - Success Rate: ___%
✅ Test 4: Error Handling          [ PASS / FAIL ]
✅ Test 5: CloudWatch Metrics      [ PASS / FAIL ] - Metrics: __/7
✅ Test 6: WebSocket Updates       [ PASS / FAIL ]
✅ Test 7: Structured Logging      [ PASS / FAIL ]
✅ Test 8: S3 Sharding             [ PASS / NEUTRAL ]
✅ Test 9: Performance             [ PASS / FAIL ] - Avg time: __ min
✅ Test 10: Cost Validation        [ PASS / FAIL ]

OVERALL: [ PRODUCTION READY / NEEDS FIXES ]

Issues found:
-
-

Next steps:
-
-
```

---

## 🎯 Next Steps After Testing

**If all tests pass**:
- ✅ Deploy to production
- ✅ Monitor CloudWatch for 24 hours
- ✅ Set up CloudWatch Alarms for critical metrics
- ✅ Create dashboard for monitoring

**If tests fail**:
- ❌ Check `FIX_IMPORTS_DEPLOY_NOW.md` for deployment fixes
- ❌ Review CloudWatch Logs for error details
- ❌ Verify Lambda Layer attached to all functions
- ❌ Confirm all environment variables set correctly

---

**Good luck with testing! 🚀**
