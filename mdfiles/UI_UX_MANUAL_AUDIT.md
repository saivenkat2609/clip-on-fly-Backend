# UI/UX Manual Audit Checklist

**Date:** December 31, 2025
**Issues to Audit:** #83, #89, #92, #93, #94

---

## ✅ Issue #83: Color Contrast Audit

**What to Check:** Verify that text colors meet WCAG AA accessibility standards (4.5:1 contrast ratio for normal text, 3:1 for large text)

### Manual Steps:

1. **Install Browser Extension:**
   - Chrome: [WAVE Web Accessibility Evaluation Tool](https://chromewebstore.google.com/detail/wave-evaluation-tool/jbbplnpkjmmeebjpijfedlgcdilocofh)
   - OR use online tool: https://webaim.org/resources/contrastchecker/

2. **Test These Color Combinations:**
   ```
   ✓ Check: text-muted-foreground on light backgrounds
   ✓ Check: text-muted-foreground on dark backgrounds (dark mode)
   ✓ Check: All button text colors on their backgrounds
   ✓ Check: Link colors (hover and normal states)
   ✓ Check: Badge/tag text colors
   ✓ Check: Form input placeholders
   ```

3. **Test Pages:**
   - `/login` (both light and dark mode)
   - `/dashboard` (both light and dark mode)
   - `/upload` (both light and dark mode)
   - `/project/:id` (both light and dark mode)

4. **How to Fix (if needed):**
   - Open `reframe-ai/src/index.css`
   - Adjust `--muted-foreground` CSS variable values
   - Test again until contrast passes

**Pass Criteria:** All text-muted-foreground colors have 4.5:1 contrast ratio minimum

---

## ✅ Issue #89: Missing Loading States Audit

**What to Check:** Verify all async operations show loading indicators

### Manual Steps:

1. **Test These User Actions** (look for loading spinners/skeletons):

   **Dashboard Page:**
   - ✓ Initial page load - videos should show skeleton
   - ✓ Refresh action - should show loading state
   - ✓ Filter/sort changes - should show visual feedback

   **Upload Page:**
   - ✓ URL input - metadata fetching should show loading
   - ✓ Upload button click - should disable button and show loading
   - ✓ File upload progress - should show progress bar

   **Project Details Page:**
   - ✓ Initial load - clips should show skeletons
   - ✓ Template selection - should show loading during processing
   - ✓ Download clip - should show loading state on button
   - ✓ Reprocess clip - should show loading state

   **Settings Page:**
   - ✓ Profile save - should disable button and show loading
   - ✓ Password change - should show loading state
   - ✓ Theme toggle - should show immediate feedback

2. **How to Test:**
   - Open browser DevTools → Network tab
   - Throttle network to "Slow 3G"
   - Perform each action above
   - Verify loading indicator appears

3. **If Missing Loading States:**
   - Note which action lacks loading indicator
   - File issue with specific component/page name
   - I can add loading states where needed

**Pass Criteria:** All async actions show visual loading feedback

---

## ✅ Issue #92: Inconsistent Button Variants Audit

**What to Check:** Button styling should be consistent across all pages

### Manual Steps:

1. **Document Button Usage:**
   Create a spreadsheet or list:
   ```
   Page | Button Type | Variant Used | Should Be
   -----|-------------|--------------|----------
   Login | Primary CTA | gradient-primary | gradient-primary ✓
   Login | Secondary | outline | outline ✓
   Dashboard | Create Video | ??? | ???
   ```

2. **Check These Button Types:**
   - Primary action buttons (CTAs)
   - Secondary action buttons
   - Destructive buttons (delete, remove)
   - Ghost/icon buttons
   - Link-style buttons

3. **Expected Pattern:**
   ```
   Primary CTA: gradient-primary or variant="default"
   Secondary: variant="outline"
   Destructive: variant="destructive"
   Tertiary: variant="ghost"
   Link style: variant="link"
   ```

4. **Pages to Review:**
   - All pages in `reframe-ai/src/pages/*.tsx`
   - All modals in `reframe-ai/src/components/*Modal.tsx`

5. **How to Fix:**
   - Document inconsistencies
   - Send me the list
   - I'll standardize button variants

**Pass Criteria:** Same button types use same variants across all pages

---

## ✅ Issue #93: Modal Styling Inconsistencies Audit

**What to Check:** All modals should have consistent styling, padding, and behavior

### Manual Steps:

1. **Test All Modals:**
   ```
   ✓ VideoPreviewModal
   ✓ YouTubePostModal
   ✓ PaymentModal
   ✓ TemplateSelectionModal
   ✓ KeyboardShortcutsModal
   ✓ TutorialModal
   ✓ VideoEditorModal
   ✓ ExportModal
   ✓ ReauthModal
   ```

2. **Check Consistency:**
   - [ ] All modals have same border-radius
   - [ ] All modals have same padding (p-6)
   - [ ] All modals have close button in same position (top-right)
   - [ ] All modals have same header styling
   - [ ] All modals have same footer button alignment
   - [ ] All modals have consistent z-index
   - [ ] All modals blur background consistently

3. **Visual Test:**
   - Open each modal
   - Take screenshots
   - Compare side-by-side
   - Look for differences in:
     - Header font size/weight
     - Spacing between elements
     - Button positioning
     - Close button styling

4. **How to Fix:**
   - Document which modals differ
   - Send me the list
   - I'll create base modal component to standardize

**Pass Criteria:** All modals look visually consistent

---

## ✅ Issue #94: Hardcoded Colors Audit

**What to Check:** No components should use hardcoded colors (e.g., `#FF0000`, `rgb(255,0,0)`)

### Manual Steps:

1. **Search for Hardcoded Colors:**
   ```bash
   cd C:\Projects\reframeAI\reframe-ai\src

   # Search for hex colors
   grep -r "#[0-9a-fA-F]\{6\}" --include="*.tsx" --include="*.ts"

   # Search for rgb/rgba
   grep -r "rgb\|rgba" --include="*.tsx" --include="*.ts"
   ```

2. **Exceptions (Allowed):**
   - Theme definition in `index.css` (CSS variables)
   - Tailwind config colors
   - External library styles

3. **Not Allowed:**
   - Component files with `className="text-[#FF0000]"`
   - Inline styles with `style={{ color: '#FF0000' }}`
   - RGB values like `rgb(255, 0, 0)`

4. **How to Fix:**
   - List all hardcoded colors found
   - Map each to equivalent theme variable:
     ```
     #000000 → text-foreground
     #FFFFFF → text-background
     #6B7280 → text-muted-foreground
     ```
   - Send me the list
   - I'll replace with theme variables

**Pass Criteria:** No hardcoded colors in component files

---

## 📊 Summary

**Total Issues:** 5
**Automated Fixes:** 3 (#84, #88, #91 - already done!)
**Manual Audits:** 5 (#83, #89, #92, #93, #94)

### After Completing Audits:

Send me results in this format:
```
Issue #83: PASS / FAIL
- If FAIL: List color combinations that fail contrast check

Issue #89: PASS / FAIL
- If FAIL: List pages/actions missing loading states

Issue #92: PASS / FAIL
- If FAIL: List button inconsistencies found

Issue #93: PASS / FAIL
- If FAIL: List modals with styling differences

Issue #94: PASS / FAIL
- If FAIL: List files with hardcoded colors
```

I'll fix any failures immediately!

---

**Estimated Time:** 30-45 minutes for all 5 audits
**Tools Needed:** Browser with DevTools, WAVE extension (optional), VS Code
