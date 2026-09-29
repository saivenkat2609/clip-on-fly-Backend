# 🧪 Authentication Features - Complete Testing Guide

## Overview

This guide provides step-by-step instructions to test all authentication features implemented in the Reframe AI application, including password strength, breach detection, session management, and account linking.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Testing Environment Setup](#testing-environment-setup)
3. [Feature-by-Feature Testing](#feature-by-feature-testing)
4. [Integration Testing](#integration-testing)
5. [Security Testing](#security-testing)
6. [Performance Testing](#performance-testing)
7. [Regression Testing](#regression-testing)
8. [Test Data](#test-data)
9. [Troubleshooting](#troubleshooting)
10. [Test Report Template](#test-report-template)

---

## Prerequisites

### Required Tools
- ✅ Modern web browser (Chrome, Firefox, Edge, Safari)
- ✅ Browser DevTools (F12)
- ✅ Network throttling capability
- ✅ Multiple browser profiles (for session testing)
- ✅ Incognito/Private browsing mode

### Test Accounts
Create these test accounts for comprehensive testing:
- `testuser1@gmail.com` - Email/password account
- `testuser2@gmail.com` - Google OAuth account
- `testuser3@gmail.com` - Account with weak password (for testing)
- Your personal Gmail - For real-world testing

---

## Testing Environment Setup

### Step 1: Start Development Server

```bash
cd /path/to/reframe-ai
npm run dev
```

Expected output:
```
VITE v5.x.x ready in XXX ms

➜  Local:   http://localhost:8080/
➜  Network: use --host to expose
```

### Step 2: Open Browser DevTools

1. Open http://localhost:8080
2. Press F12 to open DevTools
3. Open Console tab
4. Open Network tab (keep it open for monitoring API calls)

### Step 3: Clear Browser Data (Fresh Start)

1. Open DevTools → Application tab
2. Clear Storage → Clear site data
3. Reload page

---

## Feature-by-Feature Testing

### 1. Password Strength Meter

**Location**: Signup form

#### Test Cases

**Test 1.1: Very Weak Password**
```
Input: password123
Expected:
- Strength bar: Red (1/5 bars filled)
- Label: "Weak"
- Warning: "This is a commonly used password"
- Feedback: "Choose a unique password"
- Crack time: "Instant"
```

**Test 1.2: Weak Password**
```
Input: Password1
Expected:
- Strength bar: Orange (1-2/5 bars filled)
- Label: "Fair"
- Feedback: "Add symbols (!@#$%^&*)"
- Crack time: "Seconds"
```

**Test 1.3: Fair Password**
```
Input: MyPassword!
Expected:
- Strength bar: Yellow (2-3/5 bars filled)
- Label: "Good"
- Feedback: "Add more characters"
- Crack time: "Minutes to Hours"
```

**Test 1.4: Good Password**
```
Input: MyStr0ng!Pass
Expected:
- Strength bar: Light Green (3-4/5 bars filled)
- Label: "Strong"
- Feedback: Minimal or none
- Crack time: "Days"
```

**Test 1.5: Excellent Password**
```
Input: aB3$xK9#mL2@qR7!pN4%
Expected:
- Strength bar: Green (5/5 bars filled)
- Label: "Excellent"
- Feedback: None
- Crack time: "Centuries"
```

#### How to Test

1. Navigate to http://localhost:8080/login
2. Click "Create an account"
3. Enter email: test@gmail.com
4. Click password field
5. Type each password slowly and observe:
   - Bars filling up
   - Color changes
   - Label updates
   - Feedback messages appearing
6. Screenshot each state

**Screenshot Checklist**:
- [ ] Very weak password state
- [ ] Weak password state
- [ ] Fair password state
- [ ] Good password state
- [ ] Excellent password state

---

### 2. Password Breach Detection

**Location**: Signup form (appears after 1 second of typing)

#### Test Cases

**Test 2.1: Known Breached Password**
```
Input: password123
Expected:
- Yellow warning box appears
- Icon: AlertTriangle
- Title: "Password found in data breach"
- Message: "This password has been exposed in a data breach..."
- Action: Must choose different password
- Signup button: Should be disabled
```

**Test 2.2: Not Breached Password**
```
Input: MyUniqu3$P@ssw0rd2024!
Expected:
- No warning box
- Normal strength meter shows
- Signup button: Enabled (if other fields valid)
```

**Test 2.3: Checking State**
```
Input: (type any 8+ char password slowly)
Expected:
- While typing: "Checking for data breaches..." with spinner
- After 1 second: Result appears
```

#### How to Test

1. Navigate to signup form
2. Enter valid email
3. Type "password123" in password field
4. Wait 1-2 seconds
5. Observe yellow warning box
6. Take screenshot
7. Clear password field
8. Type "MyUniqu3$P@ssw0rd2024!"
9. Wait 1-2 seconds
10. Confirm no warning appears

**Test More Breached Passwords**:
- `123456`
- `qwerty`
- `letmein`
- `welcome`
- `monkey`

**Network Tab Verification**:
- [ ] Check Network tab for request to `api.pwnedpasswords.com`
- [ ] Verify only hash prefix is sent (5 characters)
- [ ] Verify request has `Add-Padding: true` header

---

### 3. "Remember Me" Functionality

**Location**: Login form

#### Test Cases

**Test 3.1: Remember Me Checked (Default)**
```
Steps:
1. Login with "Remember Me" checked
2. Close all browser windows
3. Open new browser window
4. Navigate to app

Expected:
- Still logged in
- Redirected to dashboard
- User info displayed
```

**Test 3.2: Remember Me Unchecked**
```
Steps:
1. Logout
2. Login with "Remember Me" UNchecked
3. Close all browser windows
4. Open new browser window
5. Navigate to app

Expected:
- Logged out
- Redirected to /login
- Must login again
```

**Test 3.3: Session Duration**
```
With Remember Me checked:
- Session should persist for 30 days

Without Remember Me:
- Session should clear on browser close
```

#### How to Test

**For "Remember Me" Checked**:
1. Open http://localhost:8080/login
2. Enter credentials
3. Verify "Remember Me" is checked (default)
4. Click "Sign In"
5. Wait for redirect to dashboard
6. Open DevTools → Application → IndexedDB
7. Verify Firebase auth data exists
8. Close all browser windows (completely quit browser)
9. Open browser again
10. Navigate to http://localhost:8080
11. Should automatically go to dashboard (still logged in)

**For "Remember Me" Unchecked**:
1. If logged in, logout first
2. Open http://localhost:8080/login
3. Enter credentials
4. **Uncheck "Remember Me"**
5. Click "Sign In"
6. Wait for redirect
7. Close all browser windows
8. Open browser again
9. Navigate to http://localhost:8080
10. Should be redirected to /login (logged out)

**DevTools Verification**:
- Open DevTools → Application → IndexedDB
- Find firebase auth database
- Check persistence mode:
  - Remember Me ON: `browserLocalPersistence`
  - Remember Me OFF: `browserSessionPersistence`

---

### 4. Failed Login Attempts Counter

**Location**: Login form

#### Test Cases

**Test 4.1: First Failed Attempt**
```
Steps:
1. Enter correct email
2. Enter wrong password
3. Click Sign In

Expected:
- Error message: "Incorrect password. Please try again."
- No attempt counter shown
```

**Test 4.2: Third Failed Attempt**
```
Steps:
1. Enter wrong password (attempt 3)
2. Click Sign In

Expected:
- Error message shows
- Toast notification appears:
  - Title: "Multiple failed attempts"
  - Description: "2 attempts remaining before lockout"
  - Variant: Warning (yellow)
```

**Test 4.3: Fifth Failed Attempt**
```
Steps:
1. Enter wrong password (attempt 5)
2. Click Sign In

Expected:
- Firebase rate limiting kicks in
- Error: "Too many failed attempts. Please try again later."
- Account temporarily locked (15-30 minutes)
```

**Test 4.4: Successful Login Resets Counter**
```
Steps:
1. Fail 2 attempts
2. Enter correct password
3. Login successfully

Expected:
- Counter resets to 0
- Next failed attempt won't show warning
```

#### How to Test

1. Go to login page
2. Enter valid email (test@gmail.com)
3. Enter wrong password: "wrongpassword"
4. Click "Sign In"
5. Observe error message (no counter yet)
6. Try again with wrong password (2nd attempt)
7. Observe error message (no counter yet)
8. Try again with wrong password (3rd attempt)
9. **Look for toast notification** showing "2 attempts remaining"
10. Try again (4th attempt) - should show "1 attempt remaining"
11. Try again (5th attempt) - should show Firebase lockout
12. Wait or reset by using correct password
13. With correct password, verify counter resets

**Console Logging**:
Add this to watch attempts:
```javascript
// Open browser console and paste:
let attempts = 0;
window.trackAttempts = (success) => {
  if (success) {
    console.log('✅ Login successful, counter reset');
    attempts = 0;
  } else {
    attempts++;
    console.log(`❌ Failed attempt #${attempts}`);
    if (attempts >= 3) {
      console.warn(`⚠️ ${5 - attempts} attempts remaining`);
    }
  }
};
```

---

### 5. Inactivity Timeout

**Location**: Global (after login)

#### Test Cases

**Test 5.1: Warning After 25 Minutes**
```
Steps:
1. Login to app
2. Don't touch mouse/keyboard for 25 minutes
3. Observe

Expected:
- Warning dialog appears:
  - Title: "Are you still there?"
  - Message: "You'll be logged out in 5 minutes due to inactivity"
  - Actions: "Stay Logged In" button
```

**Test 5.2: Auto-Logout After 30 Minutes**
```
Steps:
1. Login to app
2. Don't interact for 30 minutes
3. Don't dismiss warning

Expected:
- Automatic logout
- Redirect to /login
- Toast: "Logged out due to inactivity"
```

**Test 5.3: Activity Resets Timer**
```
Steps:
1. Login to app
2. Wait 20 minutes
3. Move mouse or click
4. Wait another 20 minutes

Expected:
- Timer resets on activity
- No logout after 30 minutes total
- Logout after 30 minutes from last activity
```

#### How to Test (Quick Mode)

For faster testing, temporarily reduce timeout:

1. Open `src/lib/sessionManager.ts`
2. Change:
```typescript
// FROM:
export const INACTIVITY_TIMEOUT = 30 * 60 * 1000; // 30 min

// TO (for testing only):
export const INACTIVITY_TIMEOUT = 2 * 60 * 1000; // 2 min
export const INACTIVITY_WARNING_TIME = 30 * 1000; // 30 sec
```

3. Restart dev server
4. Login
5. Don't touch anything for 1.5 minutes
6. Warning should appear
7. Don't touch anything for another 30 seconds
8. Should auto-logout

**Activity Events Tracked**:
- Mouse movement
- Keyboard input
- Scrolling
- Touch events
- Clicks

**Test Each Event**:
```javascript
// Open console and monitor activity
window.addEventListener('mousedown', () => console.log('🖱️ Mouse activity'));
window.addEventListener('keydown', () => console.log('⌨️ Keyboard activity'));
window.addEventListener('scroll', () => console.log('📜 Scroll activity'));
window.addEventListener('touchstart', () => console.log('👆 Touch activity'));
```

---

### 6. Show/Hide Password Toggle

**Location**: All password inputs

#### Test Cases

**Test 6.1: Toggle Password Visibility**
```
Steps:
1. Enter password in field
2. Click eye icon

Expected:
- Password becomes visible (plain text)
- Icon changes to EyeOff
- Click again → password hidden
- Icon changes back to Eye
```

**Test 6.2: Keyboard Accessibility**
```
Steps:
1. Tab to password field
2. Type password
3. Tab to eye icon button
4. Press Enter or Space

Expected:
- Password visibility toggles
- Focus remains on button
```

#### How to Test

1. Go to login or signup form
2. Type password: "MyPassword123"
3. Verify shows as dots: •••••••••••••
4. Click eye icon on the right
5. Verify shows as text: MyPassword123
6. Click eye icon again
7. Verify back to dots
8. Use keyboard (Tab to icon, press Space)
9. Verify toggle works with keyboard

---

### 7. Google OAuth Integration

**Location**: Login and Signup pages

#### Test Cases

**Test 7.1: New User Signup with Google**
```
Steps:
1. Click "Continue with Google"
2. Select Google account
3. Grant permissions

Expected:
- Account created automatically
- User logged in
- Redirected to dashboard
- Firestore doc created with provider: 'google'
- Email verified automatically
```

**Test 7.2: Existing User Login with Google**
```
Steps:
1. User already has Google account
2. Click "Continue with Google"
3. Select same Google account

Expected:
- Logged in successfully
- lastLogin timestamp updated
- Redirected to dashboard
```

**Test 7.3: Google Account with Existing Email (Password)**
```
Steps:
1. Create account with email/password (test@gmail.com)
2. Logout
3. Click "Continue with Google"
4. Select same Google account (test@gmail.com)

Expected:
- Error message appears
- Alert: "This email is already registered with a password..."
- Suggestion: "Sign in with your password"
- Account NOT auto-linked (for security)
```

#### How to Test

**First Time Google Signup**:
1. Clear all browser data
2. Go to http://localhost:8080/login
3. Click "Continue with Google"
4. Select Google account in popup
5. Grant permissions if asked
6. Verify redirected to /dashboard
7. Check Firestore:
   ```javascript
   // In browser console:
   firebase.auth().currentUser
   // Verify providerData includes 'google.com'
   ```

**Provider Conflict Test**:
1. Create password account (test@gmail.com)
2. Logout
3. Try Google login with same email
4. Verify error message appears
5. Verify can login with password

---

### 8. Cross-Provider Detection

**Location**: Signup and Login forms

#### Test Cases

**Test 8.1: Signup with Google-Registered Email**
```
Setup: Account exists with Google OAuth

Steps:
1. Go to signup form
2. Enter email (registered via Google)
3. Enter password
4. Click Sign Up

Expected:
- Error before submission
- Message: "This email is already registered with Google..."
- Prompt: "Please use 'Continue with Google' button"
- Switch to login mode suggestion
```

**Test 8.2: Login with Password for Google Account**
```
Setup: Account exists with Google OAuth only

Steps:
1. Go to login form
2. Enter email (Google account)
3. Enter any password
4. Click Sign In

Expected:
- Error after submission
- Alert box (MongoDB Atlas style)
- Message: "This account was created with Google..."
- Button: "Sign in with Google"
- Clicking button triggers Google OAuth
```

**Test 8.3: Real-Time Email Validation**
```
Steps:
1. Go to signup form
2. Start typing email that exists

Expected:
- As you type, validation happens
- When email matches existing account:
  - ✗ Red X icon appears
  - Error message shows provider
  - Email field outlined in red
```

#### How to Test

**Setup**:
1. Create test account via Google
2. Note the email address
3. Logout completely

**Test Signup Form**:
1. Go to signup
2. Type the Google account email
3. Watch for real-time validation (happens after you pause typing)
4. Error should appear: "already registered with Google"
5. Try to submit form anyway
6. Should be blocked

**Test Login Form**:
1. Go to login
2. Enter Google account email
3. Enter any password
4. Click Sign In
5. Alert box should appear
6. Click "Sign in with Google" button in alert
7. Should trigger Google OAuth popup

---

### 9. Email Validation (Gmail Only)

**Location**: Signup form

#### Test Cases

**Test 9.1: Valid Gmail Address**
```
Input: john.doe@gmail.com
Expected: ✓ Green checkmark, no error
```

**Test 9.2: Invalid Domain**
```
Input: john.doe@yahoo.com
Expected: ✗ Red X, "Only Gmail addresses (@gmail.com) are allowed"
```

**Test 9.3: Disposable Email**
```
Input: test@tempmail.com
Expected: ✗ Red X, "Temporary or disposable email addresses are not allowed"
```

**Test 9.4: Email with Alias (+)**
```
Input: john.doe+alias@gmail.com
Expected: ✗ Red X, "Email aliases (using +) are not allowed"
```

**Test 9.5: Common Test Pattern**
```
Input: test123@gmail.com
Expected: ✗ Red X, "Test or throwaway email patterns detected"
```

#### How to Test

1. Go to signup form
2. Test each email pattern:

**Valid Emails** (should work):
- regular.user@gmail.com
- john.doe2024@gmail.com
- myname123@gmail.com

**Invalid - Wrong Domain**:
- user@yahoo.com → "Only Gmail addresses"
- user@outlook.com → "Only Gmail addresses"
- user@protonmail.com → "Only Gmail addresses"

**Invalid - Disposable**:
- user@tempmail.com
- user@10minutemail.com
- user@guerrillamail.com
- user@mailinator.com

**Invalid - Alias**:
- user+test@gmail.com
- user+signup@gmail.com

**Invalid - Test Patterns**:
- test123@gmail.com
- temp456@gmail.com
- fake789@gmail.com

3. For each, verify:
   - Real-time validation (appears as you type)
   - Red X icon
   - Error message displays
   - Form submission blocked

---

### 10. Password Requirements

**Location**: Signup form

#### Test Cases

**Test 10.1: Too Short**
```
Input: Pass1!
Expected: "Password must be at least 8 characters"
```

**Test 10.2: Minimum Valid**
```
Input: Pass123!
Expected: ✓ Accepted (8 chars, meets requirements)
```

**Test 10.3: No Special Characters**
```
Input: Password123
Expected: Strength meter shows "Fair", suggests adding symbols
```

**Test 10.4: No Numbers**
```
Input: Password!@#
Expected: Strength meter shows "Fair", suggests adding numbers
```

**Test 10.5: All Requirements Met**
```
Input: MyP@ssw0rd2024!
Expected: Strength meter shows "Strong" or "Excellent"
```

#### How to Test

1. Go to signup form
2. Try each password:
   - Under 8 chars → Error blocks submission
   - 8+ chars → Allowed, but strength varies
3. Observe strength meter for each
4. Verify suggestions help user improve password

---

## Integration Testing

### Workflow 1: Complete Signup Flow

```
1. Navigate to /login
2. Click "Create an account"
3. Enter email: newuser@gmail.com
4. Enter strong password (watch strength meter)
5. Confirm password
6. Check "Remember Me" (should be default checked)
7. Click "Sign Up"
8. Verify:
   - Redirect to /dashboard
   - Welcome toast appears
   - Email verification banner shows
   - User info displays correctly
9. Check Firestore:
   - User document created
   - All fields populated correctly
   - Provider: 'password'
   - createdAt timestamp
```

### Workflow 2: Complete Login Flow

```
1. Navigate to /login
2. Enter email
3. Enter password
4. Choose "Remember Me" option
5. Click "Sign In"
6. Verify:
   - Redirect to /dashboard
   - "Welcome back" toast
   - User session persists (based on Remember Me)
7. Test logout:
   - Click user menu → Logout
   - Redirect to /
   - Session cleared
```

### Workflow 3: Cross-Provider Error Handling

```
1. Create account via Google
2. Note the email
3. Logout
4. Try to signup with same email + password
5. Verify error shows
6. Click suggested "Sign in with Google"
7. Verify Google OAuth triggered
8. Verify successful login
```

### Workflow 4: Password Recovery

```
1. Go to login
2. Click "Forgot password?"
3. Enter registered email
4. Click "Reset Password"
5. Check email inbox
6. Click reset link
7. Enter new password
8. Verify:
   - Password requirements enforced
   - Strength meter shows
   - Breach check happens
9. Submit new password
10. Try logging in with new password
```

---

## Security Testing

### Test 1: XSS Prevention

```javascript
// Try injecting scripts in inputs
Email: <script>alert('XSS')</script>@gmail.com
Password: <img src=x onerror=alert('XSS')>

Expected: Treated as literal text, not executed
```

### Test 2: SQL Injection Prevention

```
Email: ' OR '1'='1
Password: ' OR '1'='1 --

Expected: Firebase handles safely, no execution
```

### Test 3: Rate Limiting

```
Steps:
1. Fail login 5 times quickly
2. Observe Firebase rate limiting

Expected:
- After 5 attempts: "Too many requests"
- Account temporarily locked
- Must wait 15-30 minutes OR reset password
```

### Test 4: Session Hijacking Prevention

```
Steps:
1. Login on one device
2. Copy session token from DevTools
3. Try using token on another device

Expected:
- Firebase validates token properly
- Token bound to device/IP (Firebase handles this)
```

### Test 5: CSRF Protection

```
Expected:
- Firebase Auth handles CSRF automatically
- Tokens include CSRF protection
- No manual testing needed
```

---

## Performance Testing

### Test 1: Password Strength Calculation Speed

```javascript
// Measure performance
console.time('password-validation');
// Type password
console.timeEnd('password-validation');

Expected: < 100ms for validation
```

### Test 2: Breach Check Response Time

```javascript
// Measure API call
console.time('breach-check');
// Type password (wait for breach check)
console.timeEnd('breach-check');

Expected:
- Initial call: 200-500ms (API request)
- Subsequent: < 50ms (if cached)
```

### Test 3: Login Performance

```javascript
// Measure login time
console.time('login');
// Click Sign In button
console.timeEnd('login');

Expected: < 2 seconds total (including Firebase auth)
```

### Test 4: Page Load Performance

```
1. Open DevTools → Network → Performance
2. Navigate to /login
3. Record performance

Expected:
- Time to Interactive: < 3 seconds
- First Contentful Paint: < 1 second
- Bundle size: Reasonable (check zxcvbn is lazy-loaded)
```

---

## Regression Testing

### Verify Existing Features Still Work

- [ ] Regular email/password signup
- [ ] Regular email/password login
- [ ] Google OAuth signup
- [ ] Google OAuth login
- [ ] Logout functionality
- [ ] Protected routes redirect correctly
- [ ] Email verification flow
- [ ] Password reset flow
- [ ] Settings → Change password
- [ ] Settings → Change email
- [ ] Theme persistence
- [ ] User profile display
- [ ] All dashboard features
- [ ] Video processing workflows

**Testing Process**:
1. Test all features listed above
2. Compare behavior before and after changes
3. Document any differences
4. Verify no functionality broken

---

## Test Data

### Valid Test Passwords

```
Weak:
- password
- 12345678
- qwerty123

Fair:
- Password1
- Welcome2024
- MyPassword

Good:
- MyStr0ng!Pass
- W3lcom3@2024
- TestP@ssw0rd99

Strong:
- MyV3ry$tr0ng!P@ssw0rd
- C0mpl3x!P@ssw0rd#2024
- S3cur3$P@ssphrase!Today

Excellent:
- aB3$xK9#mL2@qR7!pN4%tV8^
- Correct-Horse-Battery-Staple-2024!
- MyL0ng&C0mpl3x!P@ssphr@s3$2024
```

### Known Breached Passwords

```
(These will trigger breach warning)
- password
- 123456
- qwerty
- letmein
- welcome
- monkey
- dragon
- master
- sunshine
- princess
```

### Test Email Addresses

```
Valid:
- testuser1@gmail.com
- john.doe2024@gmail.com
- my.test.user@gmail.com

Invalid (should reject):
- test@yahoo.com (wrong domain)
- user+alias@gmail.com (has alias)
- test123@gmail.com (test pattern)
- temp@tempmail.com (disposable)
```

---

## Troubleshooting

### Problem: Password strength not showing

**Solutions**:
1. Check browser console for errors
2. Verify zxcvbn is installed: `npm list zxcvbn`
3. Check PasswordInput component is imported
4. Verify showStrengthMeter={true} is set

### Problem: Breach check not working

**Solutions**:
1. Check Network tab for api.pwnedpasswords.com requests
2. Verify internet connection
3. Check CORS errors (shouldn't happen with HaveIBeenPwned)
4. Feature fails gracefully - won't block signup

### Problem: Remember Me not working

**Solutions**:
1. Check DevTools → Application → IndexedDB
2. Verify Firebase persistence is set
3. Check setSessionPersistence is called before signIn
4. Test in different browser (might be browser security)

### Problem: Inactivity timeout not triggering

**Solutions**:
1. Reduce timeout values for testing
2. Check console for activity tracker logs
3. Verify ActivityTracker is initialized
4. Check if user is actually inactive (no mouse/keyboard)

### Problem: Failed attempts counter not showing

**Solutions**:
1. Check component state for failedLoginAttempts
2. Verify error handling in handleLogin function
3. Check toast notification is imported and working
4. Look for console errors

---

## Test Report Template

### Test Session Information

```
Date: _______________
Tester: _______________
Environment: Development / Staging / Production
Browser: _______________ Version: _______________
OS: _______________
```

### Test Results

| Feature | Test Case | Status | Notes |
|---------|-----------|--------|-------|
| Password Strength | Very Weak | ☐ Pass ☐ Fail | |
| Password Strength | Weak | ☐ Pass ☐ Fail | |
| Password Strength | Fair | ☐ Pass ☐ Fail | |
| Password Strength | Good | ☐ Pass ☐ Fail | |
| Password Strength | Excellent | ☐ Pass ☐ Fail | |
| Breach Detection | Breached Password | ☐ Pass ☐ Fail | |
| Breach Detection | Clean Password | ☐ Pass ☐ Fail | |
| Remember Me | Checked | ☐ Pass ☐ Fail | |
| Remember Me | Unchecked | ☐ Pass ☐ Fail | |
| Failed Attempts | Counter Shows | ☐ Pass ☐ Fail | |
| Failed Attempts | Resets on Success | ☐ Pass ☐ Fail | |
| Inactivity | Warning Shows | ☐ Pass ☐ Fail | |
| Inactivity | Auto Logout | ☐ Pass ☐ Fail | |
| Google OAuth | First Signup | ☐ Pass ☐ Fail | |
| Google OAuth | Existing User | ☐ Pass ☐ Fail | |
| Google OAuth | Provider Conflict | ☐ Pass ☐ Fail | |
| Email Validation | Gmail Accepted | ☐ Pass ☐ Fail | |
| Email Validation | Non-Gmail Rejected | ☐ Pass ☐ Fail | |
| Email Validation | Disposable Rejected | ☐ Pass ☐ Fail | |
| Email Validation | Alias Rejected | ☐ Pass ☐ Fail | |

### Issues Found

```
Issue #1:
Title: _______________
Severity: Critical / High / Medium / Low
Steps to Reproduce:
1. _______________
2. _______________
3. _______________
Expected: _______________
Actual: _______________
Screenshot: _______________
```

### Overall Assessment

```
☐ All tests passed
☐ Minor issues found (document above)
☐ Major issues found (document above)
☐ Blocking issues found (do not deploy)

Recommendation:
☐ Ready for production
☐ Ready after fixes
☐ Requires more testing
☐ Not ready for deployment
```

---

## Automated Testing Scripts

### Quick Browser Test

Paste this in browser console to run automated checks:

```javascript
// Automated test suite
async function runQuickTests() {
  console.log('🧪 Starting Quick Tests...\n');

  // Test 1: Password Strength Library
  console.log('Test 1: Password Strength');
  try {
    const { validatePasswordStrength } = await import('./src/lib/passwordValidator.ts');
    const result = validatePasswordStrength('password123');
    console.log(result.score === 0 ? '✅ Pass' : '❌ Fail', '- Weak password detected');
  } catch (e) {
    console.log('❌ Fail - Error:', e.message);
  }

  // Test 2: Breach Checker
  console.log('\nTest 2: Breach Detection');
  try {
    const { checkPasswordBreached } = await import('./src/lib/passwordBreachChecker.ts');
    const breached = await checkPasswordBreached('password');
    console.log(breached ? '✅ Pass' : '❌ Fail', '- Known breach detected');
  } catch (e) {
    console.log('❌ Fail - Error:', e.message);
  }

  // Test 3: Remember Me Checkbox
  console.log('\nTest 3: Remember Me Checkbox');
  const checkbox = document.querySelector('#remember');
  console.log(checkbox ? '✅ Pass' : '❌ Fail', '- Checkbox exists');
  console.log(checkbox?.checked ? '✅ Pass' : '⚠️ Warning', '- Default checked');

  // Test 4: Password Input Component
  console.log('\nTest 4: Password Input');
  const passwordInput = document.querySelector('input[type="password"]');
  console.log(passwordInput ? '✅ Pass' : '❌ Fail', '- Password input exists');

  // Test 5: Strength Meter
  console.log('\nTest 5: Strength Meter');
  // Type in password and check for strength bars
  if (passwordInput) {
    passwordInput.focus();
    passwordInput.value = 'TestPassword123!';
    passwordInput.dispatchEvent(new Event('input', { bubbles: true }));

    setTimeout(() => {
      const strengthBars = document.querySelectorAll('[class*="strength"]');
      console.log(strengthBars.length > 0 ? '✅ Pass' : '❌ Fail', '- Strength meter renders');
    }, 1000);
  }

  console.log('\n✅ Quick tests completed!');
}

// Run tests
runQuickTests();
```

---

## Manual Testing Checklist

Print this checklist and check off as you test:

### Pre-Testing Setup
- [ ] Development server running
- [ ] Browser DevTools open
- [ ] Console clear
- [ ] Network tab open
- [ ] Test accounts prepared

### Password Strength Testing
- [ ] Very weak password tested
- [ ] Weak password tested
- [ ] Fair password tested
- [ ] Good password tested
- [ ] Excellent password tested
- [ ] Strength bars animate correctly
- [ ] Labels update correctly
- [ ] Feedback messages appear
- [ ] Crack time estimates show

### Breach Detection Testing
- [ ] Known breached password shows warning
- [ ] Clean password shows no warning
- [ ] Checking state shows spinner
- [ ] Network request to HaveIBeenPwned verified
- [ ] Only hash prefix sent (privacy check)

### Remember Me Testing
- [ ] Checkbox present and visible
- [ ] Default state is checked
- [ ] With Remember Me: session persists
- [ ] Without Remember Me: session clears
- [ ] Browser restart tested (both scenarios)

### Failed Attempts Testing
- [ ] First 2 attempts: no warning
- [ ] 3rd attempt: warning shows
- [ ] 5th attempt: rate limiting
- [ ] Successful login resets counter

### Inactivity Testing
- [ ] Warning appears before timeout
- [ ] Auto-logout triggers
- [ ] Activity resets timer
- [ ] All activity types tested (mouse, keyboard, scroll)

### Google OAuth Testing
- [ ] New user signup works
- [ ] Existing user login works
- [ ] Provider conflict detected
- [ ] Error messages clear

### Email Validation Testing
- [ ] Gmail accepted
- [ ] Non-Gmail rejected
- [ ] Disposable email rejected
- [ ] Email alias rejected
- [ ] Test patterns rejected

### Integration Testing
- [ ] Complete signup flow
- [ ] Complete login flow
- [ ] Cross-provider flow
- [ ] Password reset flow

### Security Testing
- [ ] XSS prevention verified
- [ ] Rate limiting working
- [ ] Session security checked

### Performance Testing
- [ ] Password validation < 100ms
- [ ] Breach check < 500ms
- [ ] Login < 2 seconds
- [ ] Page load < 3 seconds

### Regression Testing
- [ ] All existing features work
- [ ] No broken functionality
- [ ] No console errors
- [ ] No network errors

### Sign-Off
- [ ] All tests completed
- [ ] Issues documented
- [ ] Screenshots captured
- [ ] Ready for deployment

---

## Support

If you encounter any issues during testing:

1. Check browser console for errors
2. Check Network tab for failed requests
3. Review implementation files
4. Contact development team
5. File bug report with screenshots

---

**Last Updated**: 2025-12-06
**Version**: 1.0.0
**Status**: Ready for Testing
