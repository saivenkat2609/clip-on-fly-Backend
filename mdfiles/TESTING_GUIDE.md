# Testing Guide - Critical & High Priority Issues

**Date:** December 31, 2025
**Issues Covered:** #6, #16-27

---

## 🔴 Critical Issue #6: YouTube URL Validation

**How to Test:**

1. **Valid URL (should PASS):**
   - Upload: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
   - Expected: Video downloads successfully

2. **Invalid URL (should FAIL):**
   - Upload: `https://evil.com/watch?v=dQw4w9WgXcQ`
   - Expected: Error - "Invalid YouTube URL format"

3. **Command Injection Attempt (should FAIL):**
   - Upload: `https://youtube.com/watch?v=test; rm -rf /`
   - Expected: Error - "Invalid YouTube URL format"

4. **Check Logs:**
   - Open CloudWatch Logs for `opus-clip-node-download`
   - Look for: `[Download] CRITICAL FIX #6: Validating YouTube URL...`

**✅ Pass Criteria:** Valid URLs work, invalid URLs are rejected

---

## 🟢 Issue #16: Lambda Authorizer Package Size

**How to Test:**

1. Go to AWS Lambda Console
2. Open `opus-clip-authorizer` function
3. Check "Code" tab for package size

**✅ Pass Criteria:** Package size < 2 MB (previously ~3-4 MB)

---

## ⚠️ Issue #17: Lambda Reserved Concurrency

**How to Test:**

1. Go to AWS Lambda Console
2. Check these functions have "Reserved concurrency" set:
   - `opus-clip-node-download` → 50
   - `opus-clip-detect-clips` → 20
   - `opus-clip-process-clip` → 100

**✅ Pass Criteria:** All three functions show reserved concurrency values

---

## 🟢 Issue #18: User Profile Cache TTL

**How to Test:**

1. Open your production site
2. Open browser DevTools → Network tab
3. Navigate to profile page
4. Wait 5 minutes
5. Refresh page

**✅ Pass Criteria:** New API request for profile after 5 minutes (not using stale cache)

---

## 🟢 Issue #19: YouTube Download Retry Logic

**How to Test:**

1. Temporarily disable internet or block YouTube
2. Try to upload a video
3. Check CloudWatch Logs for `opus-clip-node-download`
4. Look for retry messages:
   ```
   [Download] HIGH PRIORITY FIX #19: Attempting yt-dlp download (attempt 1/3)...
   [Download] ✗ yt-dlp download failed on attempt 1
   [Download] Waiting 1s before retry...
   [Download] HIGH PRIORITY FIX #19: Attempting yt-dlp download (attempt 2/3)...
   ```

**✅ Pass Criteria:** See 3 retry attempts with exponential backoff (1s, 2s, 4s)

---

## 🟢 Issue #20: Firestore Optimization

**How to Test:**

1. Upload a video and let it process completely
2. Check CloudWatch Logs for `opus-clip-process-clip`
3. Look for: `[Process] HIGH PRIORITY FIX #20: REMOVED individual Firestore write`
4. Check Firestore usage in Firebase Console (should be significantly lower)

**✅ Pass Criteria:** No individual Firestore writes per clip, batch writes only

---

## 🟢 Issue #21: WebSocket Logging Removed

**How to Test:**

1. **Production Test:**
   - Open production site
   - Open browser Console
   - Connect WebSocket
   - Expected: NO debug logs (only errors if any)

2. **Dev Test:**
   - Open development site (localhost)
   - Open browser Console
   - Connect WebSocket
   - Expected: Debug logs SHOULD appear

**✅ Pass Criteria:** No WebSocket debug logs in production, present in development

---

## ⚠️ Issue #22: Dead Letter Queue

**How to Test:**

1. Go to AWS SQS Console
2. Check these queues exist:
   - `opus-clip-dlq-prod`
   - `opus-clip-dlq-prod-deadletter`

3. Go to AWS CloudWatch Alarms
4. Check alarm exists: `opus-clip-dlq-prod-messages`

5. **Force a Failure:**
   - Upload invalid video that will fail processing
   - Check DLQ for failed message

**✅ Pass Criteria:** Queues exist, alarm configured, failed jobs appear in DLQ

---

## 🟢 Issue #23: Re-authentication for Sensitive Actions

**How to Test:**

1. Log into production site
2. Try to delete account or change sensitive settings
3. Should prompt for password re-authentication
4. Enter correct password → action should succeed
5. Enter wrong password → action should fail

**✅ Pass Criteria:** Re-auth modal appears for sensitive actions

---

## 🟢 Issue #24: Error Message Sanitization

**How to Test:**

1. **Trigger API Error:**
   - Open browser DevTools → Network tab
   - Upload video with invalid parameters
   - Check error response

2. **Check User-Facing Error:**
   - Should show: "Request failed" or generic message
   - Should NOT show: Stack traces, file paths, AWS internals

3. **Check Backend Logs:**
   - CloudWatch Logs SHOULD have full error details
   - User response should NOT have full details

**✅ Pass Criteria:** Generic errors to user, detailed logs in CloudWatch

---

## 🟢 Issue #25: APIClient Retry Logic

**How to Test:**

1. **Test Rate Limiting:**
   - Upload multiple videos rapidly (10+ in quick succession)
   - Some may get 429 errors initially
   - Should automatically retry and succeed

2. **Check Browser Console:**
   - Should NOT see "429 Too Many Requests" errors
   - Requests should eventually succeed after retries

3. **Check Network Tab:**
   - Failed requests followed by successful retries
   - Delays between retries: 1s, 2s, 4s

**✅ Pass Criteria:** Automatic retries on 429/503 errors with exponential backoff

---

## 🟢 Issue #26: Video File Validation

**How to Test:**

1. **Valid Video (should PASS):**
   - Upload normal YouTube video (30s - 1hr duration)
   - Expected: Success

2. **Audio-Only (should FAIL):**
   - Upload YouTube music/podcast (audio-only)
   - Expected: Error - "no video stream found"

3. **Too Short (should FAIL):**
   - Upload video < 30 seconds
   - Expected: Error - "Video too short"

4. **Too Long (should FAIL):**
   - Upload video > 1 hour
   - Expected: Error - "Video too long"

5. **Check Logs:**
   - Look for: `[Download] HIGH PRIORITY FIX #26: Validating downloaded video file...`
   - Should show: Duration, size, codec, format

**✅ Pass Criteria:** Only valid videos pass, invalid ones rejected with specific errors

---

## 🟢 Issue #27: Parameter Validation

**How to Test:**

1. **Normal Request (should PASS):**
   ```bash
   curl -X POST https://your-api/process \
     -H "Authorization: Bearer YOUR_JWT" \
     -d '{"youtube_url": "...", "num_clips": 5, "timeframe": "30"}'
   ```

2. **DoS Attempt - Excessive num_clips (should cap at 20):**
   ```bash
   curl -X POST https://your-api/process \
     -H "Authorization: Bearer YOUR_JWT" \
     -d '{"youtube_url": "...", "num_clips": 10000}'
   ```
   - Expected: Process with num_clips=20 (capped)

3. **Invalid timeframe (should default to 'auto'):**
   ```bash
   curl -X POST https://your-api/process \
     -H "Authorization: Bearer YOUR_JWT" \
     -d '{"youtube_url": "...", "timeframe": "invalid"}'
   ```
   - Expected: Process with timeframe='auto'

4. **Check Logs:**
   - Look for: `[Detect] HIGH PRIORITY FIX #27: Parameter validation passed`
   - Should show validated values

**✅ Pass Criteria:** Invalid parameters are sanitized/capped, not rejected

---

## 🎯 Quick Test Checklist

Run these quick tests to verify everything works:

- [ ] Upload valid YouTube video → Success
- [ ] Try invalid URL → Rejected
- [ ] Check Lambda concurrency settings
- [ ] Check DLQ queues exist
- [ ] Check no WebSocket logs in production console
- [ ] Try re-auth for sensitive action
- [ ] Upload 10 videos rapidly → All succeed (with retries)
- [ ] Check CloudWatch Logs for fix messages

---

## 🚨 Critical Tests (Must Pass)

**Before going to production, these MUST pass:**

1. ✅ **Issue #6:** Invalid URLs are rejected (security)
2. ✅ **Issue #26:** Audio-only files are rejected (prevents bad clips)
3. ✅ **Issue #27:** num_clips=10000 is capped to 20 (prevents DoS)

If any of these fail, DO NOT deploy to production!
