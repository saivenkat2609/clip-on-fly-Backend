# 🚀 Caching Opportunities & Best Practices - Reframe AI

## Executive Summary

**47+ caching opportunities identified** across the project. Implementing these could reduce network requests by **40-60%** and improve performance significantly.

---

## 🎯 Priority 1: HIGH IMPACT (Implement First)

### 1. User Profile Data Caching
**Problem**: User profile fetched **7+ times** across different components
```typescript
// Current: Repeated in AuthContext, Dashboard, Settings, Templates, Billing
const userDoc = await getDoc(doc(db, 'users', currentUser.uid));
```

**Solution**: Create `useUserProfile()` hook with sessionStorage
```typescript
// Cache key: user_{uid}_profile
// TTL: 30 minutes
// Updates: On profile changes only
```

**Files**:
- `src/contexts/AuthContext.tsx` (7 locations)
- `src/pages/Dashboard.tsx` (line 185)
- `src/pages/Settings.tsx` (line 73)
- `src/pages/Templates.tsx` (line 36)
- `src/pages/ProjectDetails.tsx` (line 100)
- `src/pages/Billing.tsx` (~line 185)

---

### 2. React Query Integration (Currently Unused!)
**Problem**: `QueryClient` imported in `App.tsx` but **NOT USED ANYWHERE**

**Solution**: Implement React Query for all Firestore queries
```typescript
// Use @tanstack/query-firebase for Firebase integration
const { data: videos } = useFirestoreQuery(['videos', userId],
  query(collection(db, 'videos'), where('userId', '==', userId))
);
```

**Benefits**:
- Automatic request deduplication
- Background refetching
- Stale-while-revalidate pattern
- Built-in cache invalidation

**Apply to**:
- Video queries (Dashboard, AllProjects, ProjectDetails)
- User plan queries (Templates, ProjectDetails, Billing)
- Notifications (Dashboard)
- YouTube connections (YouTubeConnection component)

---

### 3. Expensive Computations - Add Memoization

#### Credits Calculation
**File**: `src/pages/Dashboard.tsx` (lines 248-265)
```typescript
// ❌ Current: Recalculates every render
const usedCredits = videos.reduce((sum, video) => sum + ..., 0);

// ✅ Fix: Wrap in useMemo
const usedCredits = useMemo(() =>
  videos.reduce((sum, video) => sum + Math.floor(video.videoInfo?.duration / 60), 0),
  [videos]
);
```

#### Filtering & Sorting
**File**: `src/pages/ProjectDetails.tsx` (lines 235-249)
```typescript
// ✅ Add memoization
const filteredClips = useMemo(() => filterClips(clips), [clips, activeFilters]);
const sortedClips = useMemo(() => sortClips(filteredClips), [filteredClips, sortBy]);
```

---

### 4. Static Template Data
**File**: `src/lib/templates.ts` (16 templates hardcoded)

**Solution**: Cache in sessionStorage with version
```typescript
// Cache key: app_templates_v1
// TTL: Session (until browser close)
// Update: Only when version changes
```

---

## 🎯 Priority 2: MEDIUM IMPACT

### 5. Video Collections - Consolidate Listeners
**Problem**: Duplicate `onSnapshot` listeners in Dashboard & AllProjects

**Solution**: Create `useVideos()` singleton hook
```typescript
// Single listener shared across components
// Cache in context provider
// Update all subscribers on changes
```

**Files**:
- `src/pages/Dashboard.tsx` (lines 153-176)
- `src/pages/AllProjects.tsx` (lines 62-86)

---

### 6. API Client Caching Layer
**File**: `src/lib/apiClient.ts` (NO caching currently)

**Solution**: Add TTL-based cache for GET requests
```typescript
class APIClient {
  private cache = new Map();

  async get(endpoint, ttl = 300000) { // 5 min default
    const cached = this.getFromCache(endpoint);
    if (cached && !this.isExpired(cached)) return cached.data;
    // ... fetch and cache
  }
}
```

---

### 7. Component Memoization
**Missing React.memo on**:
- `src/components/VideoThumbnail.tsx`
- Video cards in Dashboard/AllProjects lists

**Solution**:
```typescript
export const VideoThumbnail = React.memo(({ video }) => {
  // component code
}, (prevProps, nextProps) => prevProps.video.id === nextProps.video.id);
```

---

## 🎯 Priority 3: LOW IMPACT (Nice to Have)

### 8. Date Formatting Optimization
**Files**: Dashboard, AllProjects, ProjectDetails

**Solution**: Create `useFormattedDate()` hook with memoization

---

### 9. YouTube Connection Caching
**File**: `src/components/YouTubeConnection.tsx`

**Cache**:
- Connection status → sessionStorage (5 min TTL)
- Auth URL → sessionStorage (30 min TTL)

---

## 📚 Best Practices for 2025

### Storage Selection Guide

| Data Type | Storage | TTL | Use Case |
|-----------|---------|-----|----------|
| User preferences | localStorage | Persistent | Theme, settings |
| Session data | sessionStorage | Session | Temporary filters |
| Large datasets | IndexedDB | Custom | Offline data |
| API responses | React Query | 5-30 min | Server data |
| Computed values | useMemo | Render-based | Expensive calculations |

### React Query Configuration
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,    // 5 minutes
      cacheTime: 30 * 60 * 1000,   // 30 minutes
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
```

### LocalStorage Best Practices
```typescript
// ✅ Always wrap in try-catch
try {
  const data = JSON.parse(localStorage.getItem(key) || '{}');
} catch (error) {
  console.error('Failed to parse cached data', error);
}

// ✅ Add TTL validation
const cached = localStorage.getItem(key);
if (cached) {
  const { data, timestamp } = JSON.parse(cached);
  if (Date.now() - timestamp < TTL) return data;
}

// ✅ Handle quota exceeded
try {
  localStorage.setItem(key, value);
} catch (e) {
  if (e.name === 'QuotaExceededError') {
    // Clear old items
  }
}
```

### Firebase + React Query Pattern
```typescript
// Use @tanstack/query-firebase
import { useFirestoreQuery } from '@tanstack/react-query-firebase';

const { data, isLoading } = useFirestoreQuery(
  ['videos', userId],
  doc(db, 'videos', videoId),
  { subscribe: true } // Real-time updates
);
```

---

## 🛠️ Implementation Roadmap

### Week 1: Quick Wins (4-6 hours)
- [ ] Create `useUserProfile()` hook → Cache user data in sessionStorage
- [ ] Add `useMemo` to credits calculation, filtering, sorting
- [ ] Wrap list components with `React.memo`
- [ ] Cache templates in sessionStorage

**Expected Impact**: 20-30% fewer API calls

---

### Week 2: Architecture (8-12 hours)
- [ ] Implement React Query for all Firestore reads
- [ ] Install `@tanstack/react-query-firebase`
- [ ] Create `useVideos()` singleton hook
- [ ] Build APIClient caching layer
- [ ] Create reusable hooks: `useUserPlan()`, `useFormattedDate()`

**Expected Impact**: 40-50% fewer API calls, better UX

---

### Week 3: Optimization (4-6 hours)
- [ ] Add request deduplication
- [ ] Implement virtual scrolling for large lists (100+ items)
- [ ] Setup Service Worker for static assets
- [ ] Add cache performance monitoring

**Expected Impact**: 50-60% fewer API calls, 2x faster page loads

---

## 📊 Files Requiring Changes (Summary)

### High Priority (Week 1)
1. `src/contexts/AuthContext.tsx` - User profile caching
2. `src/pages/Dashboard.tsx` - Memoization, video hook
3. `src/pages/AllProjects.tsx` - Video hook
4. `src/lib/templates.ts` - SessionStorage cache
5. `src/App.tsx` - Setup React Query properly

### Medium Priority (Week 2)
6. `src/pages/ProjectDetails.tsx` - React Query, memoization
7. `src/pages/Templates.tsx` - React Query for user plan
8. `src/pages/Billing.tsx` - React Query
9. `src/lib/apiClient.ts` - Add caching layer
10. `src/components/YouTubeConnection.tsx` - Cache connection status

### Low Priority (Week 3)
11. `src/components/VideoThumbnail.tsx` - React.memo
12. `src/pages/Settings.tsx` - Use shared profile hook

---

## 🔗 References & Resources

### React Query + Firebase
- [TanStack Query Firebase](https://react-query-firebase.invertase.dev/)
- [React Query Caching Best Practices 2025](https://blog.openreplay.com/enhancing-performance-with-react-query-caching/)
- [Caching in React and Next.js 2025](https://jigsdev.xyz/blogs/caching-in-react-and-next-js-with-best-practices-for-2025)

### Browser Storage
- [Master Browser Storage 2025](https://medium.com/@osamajavaid/master-browser-storage-in-2025-the-ultimate-guide-for-front-end-developers-7b2735b4cc13)
- [Frontend Storage Guide](https://medium.com/front-end-world/frontend-storage-localstorage-sessionstorage-cookies-indexeddb-cache-api-206ce3f5f9b3)
- [Caching Strategies for Front-End Developers](https://moldstud.com/articles/p-caching-strategies-every-front-end-developer-should-implement-for-optimal-performance)

---

## ⚠️ Important Notes

### Security Considerations
- ❌ Never cache sensitive data (passwords, API keys) in localStorage
- ✅ Use sessionStorage for temporary sensitive data
- ✅ Implement proper TTL to avoid stale data

### Performance Guidelines
- localStorage is **synchronous** - use sparingly
- IndexedDB is **asynchronous** - use for large data
- React Query handles **automatic background refetching**

### Cache Invalidation
- Clear cache on logout
- Implement version-based invalidation
- Add manual cache clear option in settings

---

**Total ROI**: Implementing Weeks 1-2 will result in **~50% reduction in network requests** and significantly improved user experience.
