# 🧪 Caching Testing Guide - Verify All Optimizations Work

## Prerequisites

1. Open browser DevTools (F12)
2. Keep Network tab and Console tab visible
3. Have Firebase Console open in another tab

---

## Test 1: React Query Setup ✅

### What to Test:
React Query is configured and working

### Steps:
1. Start dev server: `npm run dev`
2. Open browser console
3. Type: `window.__REACT_QUERY_DEVTOOLS__`
4. You should see React Query is loaded

### Expected Result:
- ✅ No console errors about QueryClient
- ✅ App loads successfully
- ✅ React Query context is available

### How to Verify:
```javascript
// In browser console
console.log(typeof window.__REACT_QUERY_DEVTOOLS__)
// Should output: "object" or "undefined" (both OK - means React Query is working)
```

---

## Test 2: User Profile Caching 🎯

### What to Test:
User profile fetched once and cached

### Steps:
1. **Clear all caches first**:
   - Open DevTools → Application tab
   - Clear sessionStorage
   - Clear localStorage

2. **Login to app**

3. **Check Network tab**:
   - Filter by "firestore"
   - You should see ONE request for user profile

4. **Navigate between pages**:
   - Go to Dashboard
   - Go to Settings
   - Go to Templates
   - Go back to Dashboard

5. **Check Network tab again**:
   - You should see NO additional user profile requests!

### Expected Result:
- ✅ User profile fetched ONCE on first page load
- ✅ Zero additional fetches when navigating
- ✅ Data loads instantly from cache

### How to Verify:
```javascript
// In browser console
// Check sessionStorage cache
const userId = 'your-user-id'; // Replace with actual
const cached = sessionStorage.getItem(`user_profile_${userId}`);
console.log('Cached profile:', JSON.parse(cached));

// Check timestamp
const cache = JSON.parse(cached);
const age = (Date.now() - cache.timestamp) / 1000;
console.log(`Cache age: ${age} seconds`);
// Should be recent (< 60 seconds if just loaded)
```

### Visual Indicators:
- Pages load instantly (no loading spinners for user data)
- Network tab shows 0 Firestore requests after initial load

---

## Test 3: Videos Singleton Hook 🎯

### What to Test:
Single Firestore listener for videos, shared across components

### Steps:
1. **Login and go to Dashboard**

2. **Open Network tab** → Filter "firestore"

3. **Count video query requests**:
   - Should see ONE `runQuery` for videos

4. **Navigate to "All Projects" page**

5. **Check Network tab**:
   - Should see ZERO new video queries
   - Videos load instantly

6. **Go back to Dashboard**:
   - Still ZERO new queries
   - Instant load

### Expected Result:
- ✅ ONE Firestore listener created on first video page
- ✅ Same listener reused across Dashboard/AllProjects
- ✅ Zero duplicate queries

### How to Verify:
```javascript
// In browser console - check React Query cache
// (This requires you to expose queryClient in window for testing)

// Look at Network tab WS (WebSocket) connections
// Should see ONE active Firestore listener, not multiple
```

### Visual Comparison:

**Before Optimization**:
```
Dashboard loads    → Firestore query #1
AllProjects loads  → Firestore query #2  ❌ Duplicate!
Back to Dashboard  → Firestore query #3  ❌ Duplicate!
```

**After Optimization**:
```
Dashboard loads    → Firestore query #1
AllProjects loads  → Uses cache          ✅ No query!
Back to Dashboard  → Uses cache          ✅ No query!
```

---

## Test 4: Template Caching 🎯

### What to Test:
Templates cached in sessionStorage

### Steps:
1. **Clear sessionStorage**:
   - DevTools → Application → Session Storage → Clear

2. **Navigate to Templates page**

3. **Check sessionStorage**:
   - DevTools → Application → Session Storage
   - Look for key: `app_templates_v1`

4. **Refresh the page**

5. **Templates load instantly** (no delay)

### Expected Result:
- ✅ sessionStorage contains `app_templates_v1`
- ✅ Templates load instantly on refresh
- ✅ No network requests for template data

### How to Verify:
```javascript
// In browser console
const cached = sessionStorage.getItem('app_templates_v1');
const templates = JSON.parse(cached);

console.log('Cached templates count:', templates.templates.length);
console.log('Cache version:', templates.version);
console.log('Timestamp:', new Date(templates.timestamp));

// Should show:
// Cached templates count: 16
// Cache version: "1.0.0"
// Timestamp: [current date]
```

---

## Test 5: API Client Caching 🎯

### What to Test:
GET requests cached for 5 minutes

### Steps:
1. **Trigger an API GET request** (if you have any backend APIs)

2. **Check Network tab**:
   - Note the request to your API

3. **Trigger the SAME request again** (within 5 minutes):
   - Navigate away and back
   - Or manually call the API

4. **Check Network tab**:
   - Should see NO new request
   - Data served from cache

### Expected Result:
- ✅ First request hits network
- ✅ Subsequent requests (within 5 min) use cache
- ✅ After 5 minutes, cache expires and refetches

### How to Verify (if applicable):
```javascript
// In browser console
import { apiClient } from './src/lib/apiClient';

// Make a request
const data1 = await apiClient.get('/test-endpoint');
console.log('First request - from network');

// Make same request immediately
const data2 = await apiClient.get('/test-endpoint');
console.log('Second request - from cache');

// Check if same object reference (cached)
console.log('From cache?', data1 === data2); // Should be true
```

---

## Test 6: VideoThumbnail Memoization 🎯

### What to Test:
VideoThumbnail only re-renders when props change

### Steps:
1. **Go to Dashboard** (shows video list)

2. **Open React DevTools**:
   - Install React DevTools extension
   - Go to "Profiler" tab
   - Click "Record"

3. **Interact with page** (NOT videos):
   - Change filter
   - Sort videos
   - Scroll

4. **Stop profiling**

5. **Check flamegraph**:
   - VideoThumbnail components should NOT appear
   - Only components that actually changed should render

### Expected Result:
- ✅ VideoThumbnail doesn't re-render on parent updates
- ✅ Only re-renders when video data changes
- ✅ Improved scroll performance

### Visual Indicators:
- Smooth scrolling through video list
- No unnecessary thumbnail regeneration
- Lower CPU usage in DevTools Performance tab

---

## Test 7: Date Formatting Memoization 🎯

### What to Test:
Date formats computed once and cached

### Steps:
1. **Go to Dashboard** (shows dates)

2. **Open React DevTools Profiler**

3. **Hover over videos** (triggers re-renders)

4. **Check if date formatting is cached**:
   - Dates should display instantly
   - No re-computation visible

### Expected Result:
- ✅ Dates format once per unique date
- ✅ Cached format reused on re-renders
- ✅ No performance impact from date formatting

---

## 🔬 Advanced Testing: Memory & Performance

### Test 8: Memory Usage

**Check sessionStorage Size**:
```javascript
// In browser console
let totalSize = 0;
for (let key in sessionStorage) {
  if (sessionStorage.hasOwnProperty(key)) {
    totalSize += sessionStorage[key].length + key.length;
  }
}
console.log(`sessionStorage size: ${(totalSize / 1024).toFixed(2)} KB`);

// Should be < 100 KB
```

### Test 9: Cache Cleanup

**Verify automatic cleanup**:
```javascript
// In browser console - check API client cleanup
import { apiClient } from './src/lib/apiClient';

// Check cache size before
console.log('Cache size:', apiClient['cache'].size);

// Wait 5+ minutes (or manually trigger cleanup)
// Cache should auto-cleanup expired entries

// Check cache size after
console.log('Cache size after cleanup:', apiClient['cache'].size);
```

### Test 10: Network Reduction

**Measure network requests**:

1. **Clear all caches**

2. **Open Network tab** → Check "Disable cache" UNCHECKED

3. **Record baseline**:
   - Login
   - Navigate: Dashboard → Projects → Templates → Settings → Dashboard
   - Count total requests

4. **Clear browser cache but keep sessionStorage**

5. **Repeat navigation**:
   - Navigate same route again
   - Count requests

**Expected Results**:

| Test Run | Firestore Requests | Expected |
|----------|-------------------|----------|
| First (cold cache) | ~10-15 | Baseline |
| Second (warm cache) | ~2-5 | 50-70% reduction ✅ |

---

## 📊 Performance Benchmarks

### Before Optimization (Baseline):

Run these tests BEFORE applying optimizations to compare:

```javascript
// Measure page load time
performance.mark('start');
// Navigate to Dashboard
performance.mark('end');
performance.measure('pageLoad', 'start', 'end');
console.log(performance.getEntriesByName('pageLoad')[0].duration);

// Typical before: 800-1200ms
```

### After Optimization (Target):

```javascript
// Same test after optimization
// Typical after: 300-500ms (60% faster!)
```

---

## ✅ Success Criteria Checklist

### Core Caching:
- [ ] User profile fetched once per session
- [ ] Videos use single shared listener
- [ ] Templates cached in sessionStorage
- [ ] API GET requests cached for 5 minutes
- [ ] Date formatting memoized

### Performance:
- [ ] 40-60% reduction in network requests
- [ ] Page navigation feels instant
- [ ] No loading spinners for cached data
- [ ] Smooth scrolling in video lists

### Memory:
- [ ] sessionStorage < 500 KB
- [ ] No memory leaks (check DevTools Memory tab)
- [ ] Cache auto-cleanup working

### User Experience:
- [ ] Data loads instantly on navigation
- [ ] Real-time updates still work
- [ ] No stale data shown
- [ ] Logout clears all caches

---

## 🐛 Troubleshooting

### Issue: Stale Data Shown

**Fix**:
```javascript
// Manually clear React Query cache
import { useQueryClient } from '@tanstack/react-query';

const queryClient = useQueryClient();
queryClient.invalidateQueries(['userProfile']);
queryClient.invalidateQueries(['videos']);
```

### Issue: sessionStorage Full

**Fix**:
```javascript
// Clear old caches
sessionStorage.clear();
// Or selectively clear
sessionStorage.removeItem('user_profile_' + userId);
```

### Issue: API Cache Not Working

**Check**:
```javascript
// Verify API client instance
import { apiClient } from '@/lib/apiClient';
console.log('API client cache size:', apiClient['cache'].size);
console.log('In-flight requests:', apiClient['inFlightRequests'].size);
```

---

## 📈 Monitoring in Production

### Add Performance Logging:

```typescript
// In App.tsx or main entry point
if (import.meta.env.PROD) {
  // Log cache hit rates
  setInterval(() => {
    const queryClient = useQueryClient();
    const cache = queryClient.getQueryCache();
    const queries = cache.getAll();

    const cacheHits = queries.filter(q => q.state.dataUpdatedAt > 0).length;
    const totalQueries = queries.length;

    console.log(`Cache hit rate: ${(cacheHits / totalQueries * 100).toFixed(1)}%`);
  }, 60000); // Every minute
}
```

---

## 🎯 Quick Test Script

Run this in browser console to test all at once:

```javascript
// Quick verification script
async function testCaching() {
  console.log('🧪 Testing Caching Implementation...\n');

  // Test 1: sessionStorage
  const userId = 'test-user-id'; // Replace with actual
  const profileCache = sessionStorage.getItem(`user_profile_${userId}`);
  console.log('✅ Profile cache:', profileCache ? 'EXISTS' : '❌ MISSING');

  // Test 2: Templates
  const templateCache = sessionStorage.getItem('app_templates_v1');
  console.log('✅ Template cache:', templateCache ? 'EXISTS' : '❌ MISSING');

  // Test 3: Memory usage
  let totalSize = 0;
  for (let key in sessionStorage) {
    if (sessionStorage.hasOwnProperty(key)) {
      totalSize += sessionStorage[key].length;
    }
  }
  console.log('✅ sessionStorage size:', (totalSize / 1024).toFixed(2), 'KB');

  console.log('\n✅ All tests passed!');
}

testCaching();
```

---

## 📝 Test Results Template

Copy this and fill in your results:

```
# Caching Test Results

Date: [DATE]
Environment: Development / Production

## Test Results:

1. React Query Setup: ✅ / ❌
2. User Profile Caching: ✅ / ❌
   - First load: ___ ms
   - Cached load: ___ ms
   - Reduction: ___%

3. Videos Singleton: ✅ / ❌
   - Firestore queries: ___ (Expected: 1)

4. Template Caching: ✅ / ❌
   - Cache size: ___ KB

5. API Caching: ✅ / ❌
   - Cache hit rate: ___%

6. VideoThumbnail Memo: ✅ / ❌
   - Unnecessary renders: ___ (Expected: 0)

7. Date Formatting: ✅ / ❌

## Performance Metrics:

- Total network requests (before): ___
- Total network requests (after): ___
- Reduction: ___%

- Page load time (before): ___ ms
- Page load time (after): ___ ms
- Improvement: ___%

## Issues Found:

- [List any issues]

## Overall Status: ✅ PASS / ❌ FAIL
```

---

**Ready to test!** Start with Test 1 and work through each test systematically. 🚀
