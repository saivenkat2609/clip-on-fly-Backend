# Authentication Best Practices Analysis - Reframe AI

## Executive Summary

**Current Status**: Your authentication system is **well-implemented** with many industry best practices already in place. This document analyzes how major platforms (Google, GitHub, LinkedIn, Stripe, MongoDB Atlas) handle authentication and provides specific recommendations to elevate your system to enterprise-grade.

**Overall Grade**: B+ (85/100)
- ✅ Excellent: Cross-provider detection, email validation, secure token management
- ⚠️ Needs Improvement: Account linking UX, session management, MFA support
- ❌ Missing: Rate limiting UI feedback, account recovery options, audit logging

---

## Table of Contents

1. [Industry Best Practices Overview](#1-industry-best-practices-overview)
2. [Account Linking & Same Email Handling](#2-account-linking--same-email-handling)
3. [Session & Cookie Management](#3-session--cookie-management)
4. [Security Best Practices](#4-security-best-practices)
5. [User Experience Patterns](#5-user-experience-patterns)
6. [Specific Improvements for Reframe AI](#6-specific-improvements-for-reframe-ai)
7. [Implementation Roadmap](#7-implementation-roadmap)

---

## 1. Industry Best Practices Overview

### How Major Platforms Handle Authentication

#### GitHub
```
✅ Email/password + OAuth (Google, GitHub)
✅ Allow multiple OAuth providers for same email
✅ Primary email + verified secondary emails
✅ 2FA/MFA required for sensitive operations
✅ Session management with device tracking
✅ Automatic account linking for same verified email
✅ Passkeys/WebAuthn support
```

#### Google Account
```
✅ Email/password as primary
✅ Phone number verification
✅ 2-Step Verification (SMS, authenticator, hardware key)
✅ Account recovery via phone/email/security questions
✅ Device management and suspicious activity alerts
✅ Session management across devices
✅ OAuth consent screens with granular permissions
```

#### LinkedIn
```
✅ Email/password + OAuth (Google, Apple)
✅ Automatic account merging for same email
✅ LinkedIn login via OAuth
✅ 2FA via SMS
✅ Session persistence with "Remember me"
✅ Clear session expiry communication
```

#### Stripe
```
✅ Email/password only (business context)
✅ 2FA required for all accounts
✅ Session timeout after inactivity (30 min)
✅ IP whitelisting for teams
✅ Audit logs for all auth events
✅ API key management separate from user auth
✅ Team member invite system
```

#### MongoDB Atlas
```
✅ Email/password + OAuth (Google)
✅ SSO for enterprise (SAML, OIDC)
✅ MFA required for production access
✅ IP access lists
✅ Database user credentials separate from account
✅ Session management with clear expiry
✅ Automatic logout on browser close option
```

### Common Patterns Across All Platforms

1. **Progressive Security**: Start simple, add layers as user value increases
2. **Transparent Session Management**: Users know when they'll be logged out
3. **Multiple Recovery Options**: Email + phone + backup codes
4. **Clear Provider Communication**: "Signed in with Google" indicators
5. **Audit Trail**: Login history, device tracking, location
6. **Graceful Degradation**: Works without JavaScript for critical flows

---

## 2. Account Linking & Same Email Handling

### Current Implementation in Reframe AI

```typescript
// Current behavior:
✅ Password → Google: Auto-links accounts
❌ Google → Password: Blocked with error message
✅ Detects provider conflicts
⚠️ No manual account linking UI
```

**Limitation**: If user signs up with Google first, they can NEVER add a password. This is problematic if:
- User wants to use password on devices without Google OAuth
- User's Google account gets compromised
- User wants to separate personal (Google) from work (password) login

### Industry Standard Approaches

#### Approach 1: GitHub Model (Best for SaaS)

**Philosophy**: One account per email, multiple sign-in methods

```typescript
// Example flow:
User signs up with Google (john@gmail.com)
  → Account created with provider: 'google'

Later, user tries to sign in with password
  → System detects email exists
  → Shows: "An account with this email exists. Sign in with Google, or link a password."

User clicks "Add password"
  → Requires sign in with Google first (verify ownership)
  → Allows setting password
  → Now user can login with EITHER Google OR password

Account structure:
{
  email: "john@gmail.com",
  providers: [
    { type: 'google', googleId: '...', linkedAt: '...' },
    { type: 'password', hashedPassword: '...', linkedAt: '...' }
  ],
  primaryProvider: 'google',
  createdWith: 'google'
}
```

**Benefits**:
- Users never locked out
- Can add/remove providers
- Graceful provider deprecation (if Google OAuth breaks)
- Better enterprise support

#### Approach 2: LinkedIn Model (Auto-Merge)

**Philosophy**: Same verified email = same person, auto-merge

```typescript
// Example flow:
User signs up with Google (john@gmail.com)
  → Account created, email verified by Google

Later, user tries to sign up with password (john@gmail.com)
  → System detects email exists AND is verified
  → Auto-links password to existing account
  → Shows: "We found your account! Password added."
  → Sends notification email: "New sign-in method added"

// Security: Only auto-merge if email is verified
```

**Benefits**:
- Seamless UX
- No user confusion
- Prevents duplicate accounts
- Works for forgetful users

#### Approach 3: Stripe Model (Single Method Only)

**Philosophy**: One method per account, require support for changes

```typescript
// Stripe's approach:
- Email/password only (no OAuth)
- To change email: verify both old and new
- To change authentication: contact support
- Focus on security over convenience

// Reasoning: Business/financial context
```

**Benefits**:
- Simple, clear, secure
- Audit trail for changes
- Prevents social engineering
- Enterprise compliance-friendly

### Recommended Approach for Reframe AI

**Use GitHub Model with LinkedIn-style UX**

```typescript
interface UserAuth {
  email: string;
  emailVerified: boolean;
  providers: Array<{
    type: 'google' | 'password';
    googleId?: string;
    hashedPassword?: string;
    linkedAt: Date;
    lastUsed?: Date;
  }>;
  primaryProvider: 'google' | 'password';
  createdWith: 'google' | 'password';
  accountLinkingHistory: Array<{
    action: 'link' | 'unlink';
    provider: string;
    timestamp: Date;
    ipAddress: string;
  }>;
}
```

**Implementation Steps**:

1. **Update Firestore Schema** (backward compatible):
```typescript
// Existing accounts keep current structure
// New field: providers (array)
// Migration: Convert existing 'provider' field to providers array
```

2. **Add Account Linking UI** (Settings page):
```typescript
// Settings → Account → Sign-in Methods
Connected Methods:
  ✓ Google (john@gmail.com) - Primary
  + Add Password

// When user clicks "Add Password":
→ Verify identity (re-authenticate with Google)
→ Show password creation form
→ Link password to account
→ Send confirmation email
```

3. **Update Sign-in Logic**:
```typescript
async function handleSignIn(email: string, method: 'google' | 'password') {
  // Fetch all providers for this email
  const providers = await fetchSignInMethodsForEmail(email);

  if (providers.length === 0) {
    // New account
    return { action: 'signup', availableMethod: method };
  }

  if (providers.includes(method)) {
    // User can sign in with this method
    return { action: 'signin', method };
  }

  // User signed up with different method
  return {
    action: 'link-or-signin',
    existingProviders: providers,
    attemptedProvider: method,
    message: `You have an account with ${providers.join(', ')}.
              Sign in with that method, or link ${method} in Settings.`
  };
}
```

4. **Migration Plan**:
```typescript
// One-time migration function
async function migrateExistingAccounts() {
  const users = await db.collection('users').get();

  for (const user of users.docs) {
    const data = user.data();

    // Skip if already migrated
    if (data.providers) continue;

    // Convert single provider to array
    await user.ref.update({
      providers: [{
        type: data.provider,
        googleId: data.provider === 'google' ? data.uid : null,
        hashedPassword: null, // Firebase Auth handles this
        linkedAt: data.createdAt,
        lastUsed: data.lastLogin
      }],
      primaryProvider: data.provider,
      createdWith: data.provider,
      accountLinkingHistory: []
    });
  }
}
```

---

## 3. Session & Cookie Management

### Current Implementation in Reframe AI

```typescript
✅ Firebase manages sessions in IndexedDB
✅ Automatic token refresh
✅ No manual session storage
✅ Theme/preferences in localStorage (per-user)
❌ No session timeout configured
❌ No "Remember me" option
❌ No device management
❌ No session expiry notifications
```

### Industry Best Practices

#### Session Duration Strategies

**Stripe**: 30 minutes inactivity → logout
**GitHub**: 2 weeks → require re-login for sensitive actions
**Google**: Persistent (months) → re-auth for purchases/changes
**MongoDB Atlas**: Configurable (30 min default)

#### Firebase Auth Session Persistence Modes

```typescript
// Current (implicit): browserSessionPersistence
// On browser close: Session MAY persist (inconsistent)

// Three modes available:
setPersistence(auth, browserSessionPersistence);  // Cleared on close
setPersistence(auth, browserLocalPersistence);    // Persists indefinitely
setPersistence(auth, inMemoryPersistence);        // Cleared on refresh
```

### Recommended Implementation

#### 1. Add "Remember Me" Checkbox

```typescript
// Login.tsx
<Checkbox
  id="rememberMe"
  checked={rememberMe}
  onCheckedChange={setRememberMe}
/>
<label htmlFor="rememberMe">
  Stay signed in for 30 days
</label>

// In signIn function:
const persistence = rememberMe
  ? browserLocalPersistence   // 30 days
  : browserSessionPersistence; // Until browser close

await setPersistence(auth, persistence);
await signInWithEmailAndPassword(auth, email, password);
```

#### 2. Implement Session Timeout for Sensitive Actions

```typescript
// lib/sessionManager.ts
export class SessionManager {
  private static SENSITIVE_ACTION_TIMEOUT = 30 * 60 * 1000; // 30 min

  static async requireRecentAuth(action: string): Promise<boolean> {
    const user = auth.currentUser;
    if (!user) return false;

    const metadata = user.metadata;
    const lastSignIn = metadata.lastSignInTime;
    const now = Date.now();

    if (now - new Date(lastSignIn).getTime() > this.SENSITIVE_ACTION_TIMEOUT) {
      // Show re-authentication dialog
      return this.showReauthDialog(action);
    }

    return true;
  }

  private static async showReauthDialog(action: string): Promise<boolean> {
    // Modal: "Confirm your identity to {action}"
    // Show password input (or Google re-auth)
    // Return true if success, false if cancelled
  }
}

// Usage in Settings:
async function changeEmail(newEmail: string) {
  const canProceed = await SessionManager.requireRecentAuth('change email');
  if (!canProceed) return;

  // Proceed with email change
}
```

#### 3. Session Monitoring & Auto-Logout

```typescript
// contexts/AuthContext.tsx
export function AuthProvider({ children }) {
  const [lastActivity, setLastActivity] = useState(Date.now());
  const INACTIVITY_TIMEOUT = 30 * 60 * 1000; // 30 minutes

  useEffect(() => {
    // Track user activity
    const updateActivity = () => setLastActivity(Date.now());

    window.addEventListener('mousedown', updateActivity);
    window.addEventListener('keydown', updateActivity);
    window.addEventListener('scroll', updateActivity);
    window.addEventListener('touchstart', updateActivity);

    // Check for inactivity every minute
    const interval = setInterval(() => {
      const inactive = Date.now() - lastActivity;

      if (inactive > INACTIVITY_TIMEOUT && currentUser) {
        // Show warning: "You'll be logged out in 5 minutes"
        if (inactive > INACTIVITY_TIMEOUT + 5 * 60 * 1000) {
          logout();
          toast({
            title: "Logged out due to inactivity",
            description: "Sign in again to continue",
          });
        }
      }
    }, 60 * 1000);

    return () => {
      clearInterval(interval);
      window.removeEventListener('mousedown', updateActivity);
      window.removeEventListener('keydown', updateActivity);
      window.removeEventListener('scroll', updateActivity);
      window.removeEventListener('touchstart', updateActivity);
    };
  }, [lastActivity, currentUser]);
}
```

#### 4. Device & Session Management UI

```typescript
// Settings → Security → Active Sessions
interface Session {
  id: string;
  deviceType: 'desktop' | 'mobile' | 'tablet';
  browser: string;
  os: string;
  location: string; // From IP geolocation
  ipAddress: string;
  lastActive: Date;
  current: boolean;
}

// Display active sessions
{sessions.map(session => (
  <div className="session-card">
    <div className="device-icon">
      {session.deviceType === 'desktop' ? <Monitor /> : <Smartphone />}
    </div>
    <div className="session-info">
      <p className="browser">{session.browser} on {session.os}</p>
      <p className="location">{session.location}</p>
      <p className="last-active">
        {session.current
          ? 'This device'
          : `Last active ${formatDistanceToNow(session.lastActive)} ago`
        }
      </p>
    </div>
    {!session.current && (
      <Button variant="outline" onClick={() => revokeSession(session.id)}>
        Sign Out
      </Button>
    )}
  </div>
))}

<Button variant="destructive" onClick={signOutAllDevices}>
  Sign Out All Other Devices
</Button>
```

**Implementation**: Use Firebase Firestore to track sessions

```typescript
// On login, create session document
await db.collection('users').doc(userId).collection('sessions').add({
  deviceType: getDeviceType(),
  browser: getBrowser(),
  os: getOS(),
  location: await getLocationFromIP(),
  ipAddress: await getClientIP(),
  loginAt: new Date(),
  lastActive: new Date(),
  userAgent: navigator.userAgent,
  tokenId: await user.getIdToken() // For revocation
});

// Update lastActive on each API call
// Delete session on logout
// Show all sessions in Settings
```

---

## 4. Security Best Practices

### Current Implementation Scorecard

```
✅ Password minimum 8 characters
✅ Email verification sent
✅ Secure token storage (IndexedDB)
✅ HTTPS enforced
✅ 800+ disposable domains blocked
✅ Reauthentication for email/password changes
✅ No sensitive data in localStorage
✅ Cross-provider conflict prevention

❌ No password strength requirements (upper/lower/number/symbol)
❌ No password breach checking (HaveIBeenPwned)
❌ No rate limiting visibility
❌ No MFA/2FA
❌ No account recovery codes
❌ No login notifications
❌ No IP-based suspicious activity detection
❌ No CAPTCHA on repeated failures
```

### Industry Standard Security Layers

#### Layer 1: Strong Password Policy

```typescript
// lib/passwordValidator.ts
export interface PasswordStrength {
  score: 0 | 1 | 2 | 3 | 4; // 0=terrible, 4=excellent
  feedback: string[];
  passed: boolean;
}

export function validatePasswordStrength(password: string): PasswordStrength {
  const feedback: string[] = [];
  let score = 0;

  // Length
  if (password.length >= 12) score++;
  else if (password.length >= 8) score += 0.5;
  else feedback.push('Use at least 8 characters (12+ recommended)');

  // Uppercase
  if (/[A-Z]/.test(password)) score++;
  else feedback.push('Include uppercase letters');

  // Lowercase
  if (/[a-z]/.test(password)) score++;
  else feedback.push('Include lowercase letters');

  // Numbers
  if (/\d/.test(password)) score++;
  else feedback.push('Include numbers');

  // Symbols
  if (/[^A-Za-z0-9]/.test(password)) score++;
  else feedback.push('Include symbols (!@#$%^&*)');

  // Common passwords
  if (isCommonPassword(password)) {
    score = 0;
    feedback.push('This is a commonly used password');
  }

  // Patterns (123456, abcdef, qwerty)
  if (hasKeyboardPattern(password)) {
    score -= 1;
    feedback.push('Avoid keyboard patterns');
  }

  const finalScore = Math.max(0, Math.min(4, Math.floor(score)));

  return {
    score: finalScore as 0 | 1 | 2 | 3 | 4,
    feedback,
    passed: finalScore >= 3
  };
}

// UI: Show password strength meter
<PasswordInput
  value={password}
  onChange={setPassword}
  showStrengthMeter
/>

// Visual:
Weak     ▓░░░░  (red)
Fair     ▓▓░░░  (orange)
Good     ▓▓▓░░  (yellow)
Strong   ▓▓▓▓░  (light green)
Excellent ▓▓▓▓▓ (green)
```

#### Layer 2: Password Breach Detection

```typescript
// lib/pwnedPasswordCheck.ts
export async function checkPasswordBreached(password: string): Promise<boolean> {
  // Use HaveIBeenPwned API (k-Anonymity model)
  // Only sends first 5 chars of SHA-1 hash

  const sha1 = await crypto.subtle.digest(
    'SHA-1',
    new TextEncoder().encode(password)
  );
  const hashHex = Array.from(new Uint8Array(sha1))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
    .toUpperCase();

  const prefix = hashHex.substring(0, 5);
  const suffix = hashHex.substring(5);

  const response = await fetch(`https://api.pwnedpasswords.com/range/${prefix}`);
  const hashes = await response.text();

  // Check if our suffix appears in results
  return hashes.split('\n').some(line => line.startsWith(suffix));
}

// Usage in signup:
const isBreached = await checkPasswordBreached(password);
if (isBreached) {
  toast({
    title: "Password found in data breach",
    description: "This password has been exposed in a data breach. Please choose a different password.",
    variant: "destructive"
  });
  return;
}
```

#### Layer 3: Multi-Factor Authentication (MFA)

```typescript
// Enable TOTP-based MFA using Firebase
// Settings → Security → Two-Factor Authentication

import {
  multiFactor,
  TotpMultiFactorGenerator,
  TotpSecret
} from 'firebase/auth';

// Enrollment flow:
async function enableMFA() {
  const user = auth.currentUser!;
  const session = await multiFactor(user).getSession();

  // Generate TOTP secret
  const totpSecret = await TotpMultiFactorGenerator.generateSecret(session);

  // Show QR code for Google Authenticator / Authy
  const qrCodeUrl = totpSecret.generateQrCodeUrl(
    user.email!,
    'Reframe AI'
  );

  // User scans QR code
  // User enters verification code
  const verificationCode = await promptForCode();

  // Finalize enrollment
  const multiFactorAssertion = TotpMultiFactorGenerator.assertionForEnrollment(
    totpSecret,
    verificationCode
  );

  await multiFactor(user).enroll(multiFactorAssertion, 'Authenticator App');

  // Generate backup codes
  const backupCodes = generateBackupCodes(8);
  await saveBackupCodes(user.uid, backupCodes);

  // Show backup codes to user
  showBackupCodesModal(backupCodes);
}

// Sign-in flow with MFA:
try {
  await signInWithEmailAndPassword(auth, email, password);
} catch (error) {
  if (error.code === 'auth/multi-factor-auth-required') {
    const resolver = getMultiFactorResolver(auth, error);

    // Show MFA code input
    const verificationCode = await promptForMFACode();

    // Verify
    const assertion = TotpMultiFactorGenerator.assertionForSignIn(
      resolver.hints[0].uid,
      verificationCode
    );

    await resolver.resolveSignIn(assertion);
  }
}

// UI: Settings page
<Card>
  <CardHeader>
    <CardTitle>Two-Factor Authentication</CardTitle>
    <CardDescription>
      Add an extra layer of security to your account
    </CardDescription>
  </CardHeader>
  <CardContent>
    {mfaEnabled ? (
      <>
        <div className="flex items-center gap-2 text-green-600">
          <ShieldCheck className="h-5 w-5" />
          <span>Enabled</span>
        </div>
        <Button variant="outline" onClick={disableMFA}>
          Disable
        </Button>
        <Button variant="outline" onClick={showBackupCodes}>
          View Backup Codes
        </Button>
      </>
    ) : (
      <Button onClick={enableMFA}>
        Enable Two-Factor Authentication
      </Button>
    )}
  </CardContent>
</Card>
```

#### Layer 4: Login Notifications

```typescript
// Send email notification on every login
async function onLogin(userId: string, metadata: LoginMetadata) {
  const user = await db.collection('users').doc(userId).get();
  const userData = user.data()!;

  // Check if this is a new device/location
  const isNewDevice = await checkNewDevice(userId, metadata);
  const isSuspicious = await checkSuspiciousActivity(metadata);

  if (isNewDevice || isSuspicious) {
    // Send email notification
    await sendLoginNotification({
      to: userData.email,
      subject: isNewDevice
        ? 'New sign-in to your Reframe AI account'
        : '⚠️ Suspicious sign-in detected',
      data: {
        deviceType: metadata.deviceType,
        browser: metadata.browser,
        os: metadata.os,
        location: metadata.location,
        ipAddress: metadata.ipAddress,
        timestamp: new Date(),
        isNewDevice,
        isSuspicious
      }
    });
  }

  // Log all logins
  await db.collection('users').doc(userId).collection('loginHistory').add({
    ...metadata,
    timestamp: new Date(),
    flagged: isSuspicious
  });
}

// Email template:
Subject: New sign-in to your Reframe AI account

Hi John,

Your Reframe AI account was just signed in from a new device:

Device: Chrome on macOS
Location: San Francisco, CA, USA
Time: December 6, 2025 at 12:30 PM PST
IP Address: 192.168.1.1

If this was you, you can safely ignore this email.

If this wasn't you:
1. Reset your password immediately: [Reset Password]
2. Review your active sessions: [Manage Sessions]
3. Contact support: support@reframe-ai.com

This is an automated security notification.
```

#### Layer 5: Rate Limiting with User Feedback

```typescript
// Currently handled by Firebase (behind the scenes)
// Add UI feedback for rate limiting

// contexts/AuthContext.tsx
async function signIn(email: string, password: string) {
  try {
    await signInWithEmailAndPassword(auth, email, password);
  } catch (error) {
    if (error.code === 'auth/too-many-requests') {
      // Firebase has blocked this IP
      toast({
        title: "Too many failed attempts",
        description: "Your account has been temporarily locked for security. Try again in 30 minutes or reset your password.",
        variant: "destructive",
        duration: 10000
      });

      // Show CAPTCHA or wait timer
      setShowCaptcha(true);
    } else if (error.code === 'auth/wrong-password') {
      // Track failed attempts client-side
      const attempts = incrementFailedAttempts(email);

      if (attempts >= 3) {
        toast({
          title: "Multiple failed attempts",
          description: `${5 - attempts} attempts remaining before temporary lockout. Forgot your password?`,
          variant: "warning"
        });
      }
    }
  }
}
```

#### Layer 6: Account Recovery Options

```typescript
// Multiple recovery methods
interface RecoveryOptions {
  email: {
    enabled: true,
    address: string,
    verified: boolean
  },
  phone?: {
    enabled: boolean,
    number: string,
    verified: boolean
  },
  backupCodes: {
    enabled: boolean,
    remaining: number
  },
  securityQuestions?: {
    enabled: boolean,
    count: number
  }
}

// Settings → Security → Account Recovery
<Card>
  <CardHeader>
    <CardTitle>Account Recovery</CardTitle>
    <CardDescription>
      Set up recovery options in case you lose access
    </CardDescription>
  </CardHeader>
  <CardContent>
    <div className="space-y-4">
      {/* Email (always present) */}
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">Recovery Email</p>
          <p className="text-sm text-muted-foreground">{user.email}</p>
        </div>
        {user.emailVerified ? (
          <Badge variant="success">Verified</Badge>
        ) : (
          <Button variant="outline" size="sm">Verify</Button>
        )}
      </div>

      {/* Phone (optional) */}
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">Recovery Phone</p>
          <p className="text-sm text-muted-foreground">
            {recoveryPhone || 'Not set'}
          </p>
        </div>
        <Button variant="outline" size="sm">
          {recoveryPhone ? 'Change' : 'Add'}
        </Button>
      </div>

      {/* Backup Codes */}
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">Backup Codes</p>
          <p className="text-sm text-muted-foreground">
            {backupCodesRemaining} codes remaining
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={regenerateBackupCodes}>
          Regenerate
        </Button>
      </div>
    </div>
  </CardContent>
</Card>
```

---

## 5. User Experience Patterns

### Industry UX Best Practices

#### 1. Clear Provider Communication

**GitHub Example**:
```
Header: "Signed in as @username"
Dropdown shows: "Signed in with GitHub"
Settings shows: "Primary authentication: GitHub OAuth"
```

**Your Implementation**:
```tsx
// Add provider indicator in header
<div className="user-menu">
  <Avatar>
    <AvatarImage src={user.photoURL} />
    <AvatarFallback>{initials}</AvatarFallback>
  </Avatar>
  <div className="user-info">
    <p className="name">{user.displayName}</p>
    <p className="provider text-xs text-muted-foreground">
      {user.provider === 'google' ? (
        <>
          <svg className="w-3 h-3 inline mr-1">
            {/* Google icon */}
          </svg>
          Signed in with Google
        </>
      ) : (
        <>
          <Mail className="w-3 h-3 inline mr-1" />
          Signed in with Email
        </>
      )}
    </p>
  </div>
</div>
```

#### 2. Progressive Disclosure of Security Features

**LinkedIn Example**:
```
Free users: Email/password + Google OAuth
Premium users: + SSO, audit logs
Enterprise: + SAML, SCIM, advanced controls
```

**Your Implementation**:
```tsx
// Progressively enable features based on usage
const securityFeatures = {
  free: ['email_password', 'google_oauth', 'email_verification'],
  pro: ['all_free', 'mfa', 'session_management', 'login_notifications'],
  enterprise: ['all_pro', 'sso', 'audit_logs', 'ip_whitelist']
};

// In Settings, show upgrade prompts
{user.plan === 'free' && (
  <Card className="border-blue-200 bg-blue-50">
    <CardHeader>
      <CardTitle className="text-blue-900">
        Enhanced Security (Pro Feature)
      </CardTitle>
    </CardHeader>
    <CardContent>
      <p className="text-blue-800 mb-4">
        Upgrade to Pro for two-factor authentication, session management, and more.
      </p>
      <Button>Upgrade to Pro</Button>
    </CardContent>
  </Card>
)}
```

#### 3. Helpful Error Messages

**Stripe Example**:
```
❌ Bad: "Authentication failed"
✅ Good: "Your password is incorrect. You have 2 more attempts before your account is temporarily locked. Forgot your password?"
```

**Your Current Implementation** (already excellent):
```typescript
✅ "This email is already registered with Google. Please use the 'Continue with Google' button."
✅ "This account was created with Google. Use the Google button to sign in."
✅ "Only Gmail addresses (@gmail.com) are allowed."
```

**Additional improvements**:
```typescript
// Add actionable errors
if (error.code === 'auth/user-not-found') {
  return {
    title: "No account found",
    description: "We couldn't find an account with that email.",
    action: {
      label: "Sign up instead",
      onClick: () => setMode('signup')
    }
  };
}

if (error.code === 'auth/wrong-password') {
  const attempts = getFailedAttempts(email);
  return {
    title: "Incorrect password",
    description: `${5 - attempts} attempts remaining before lockout.`,
    action: {
      label: "Reset password",
      onClick: () => navigate('/forgot-password', { state: { email } })
    }
  };
}
```

#### 4. Loading States & Feedback

**Google Example**:
```
Button text changes:
"Sign in" → [spinner] "Signing in..." → "Signed in!" → redirect
```

**Your Implementation**:
```tsx
// Add granular loading states
enum AuthState {
  IDLE = 'idle',
  CHECKING_EMAIL = 'checking_email',
  AUTHENTICATING = 'authenticating',
  CREATING_PROFILE = 'creating_profile',
  SENDING_VERIFICATION = 'sending_verification',
  SUCCESS = 'success',
  ERROR = 'error'
}

<Button disabled={authState !== AuthState.IDLE}>
  {authState === AuthState.IDLE && 'Sign In'}
  {authState === AuthState.CHECKING_EMAIL && (
    <>
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      Checking email...
    </>
  )}
  {authState === AuthState.AUTHENTICATING && (
    <>
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      Signing in...
    </>
  )}
  {authState === AuthState.SUCCESS && (
    <>
      <Check className="mr-2 h-4 w-4" />
      Success!
    </>
  )}
</Button>
```

#### 5. Onboarding & First-Time User Experience

**Stripe Example**:
```
After signup:
1. Welcome email
2. Email verification reminder
3. Setup checklist (verify email, add payment, create first API key)
4. Guided tour
```

**Your Implementation**:
```tsx
// Add onboarding flow
interface OnboardingState {
  emailVerified: boolean;
  profileCompleted: boolean;
  firstVideoCreated: boolean;
  hasExploredFeatures: boolean;
}

// Show onboarding checklist in dashboard
<Card>
  <CardHeader>
    <CardTitle>Get Started with Reframe AI</CardTitle>
    <Progress value={onboardingProgress} className="mt-2" />
  </CardHeader>
  <CardContent>
    <div className="space-y-2">
      <OnboardingTask
        completed={onboarding.emailVerified}
        title="Verify your email"
        description="Keep your account secure"
        action="Resend verification"
      />
      <OnboardingTask
        completed={onboarding.profileCompleted}
        title="Complete your profile"
        description="Add your name and company"
        action="Complete profile"
      />
      <OnboardingTask
        completed={onboarding.firstVideoCreated}
        title="Create your first video"
        description="Process a YouTube video or upload your own"
        action="Get started"
      />
    </div>
  </CardContent>
</Card>
```

---

## 6. Specific Improvements for Reframe AI

### Priority 1: Critical (Implement Immediately)

#### 1.1. Add Account Linking UI
**Impact**: High | **Effort**: Medium | **Timeline**: 1-2 weeks

**Files to modify**:
- `src/pages/Settings.tsx` - Add "Sign-in Methods" section
- `src/contexts/AuthContext.tsx` - Add `linkProvider()` and `unlinkProvider()` methods
- `firestore.rules` - Add security rules for provider updates

**Implementation**:
```tsx
// Settings.tsx - Add new section
<Card>
  <CardHeader>
    <CardTitle>Sign-in Methods</CardTitle>
    <CardDescription>
      Manage how you sign in to your account
    </CardDescription>
  </CardHeader>
  <CardContent>
    <div className="space-y-4">
      {/* Google OAuth */}
      <div className="flex items-center justify-between p-4 border rounded-lg">
        <div className="flex items-center gap-3">
          <svg className="w-6 h-6">{/* Google icon */}</svg>
          <div>
            <p className="font-medium">Google</p>
            <p className="text-sm text-muted-foreground">
              {hasGoogleProvider
                ? `Connected as ${user.email}`
                : 'Not connected'
              }
            </p>
          </div>
        </div>
        {hasGoogleProvider ? (
          <div className="flex items-center gap-2">
            {isGooglePrimary && (
              <Badge variant="secondary">Primary</Badge>
            )}
            {providers.length > 1 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => unlinkProvider('google')}
              >
                Disconnect
              </Button>
            )}
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => linkProvider('google')}
          >
            Connect
          </Button>
        )}
      </div>

      {/* Email/Password */}
      <div className="flex items-center justify-between p-4 border rounded-lg">
        <div className="flex items-center gap-3">
          <Mail className="w-6 h-6" />
          <div>
            <p className="font-medium">Email & Password</p>
            <p className="text-sm text-muted-foreground">
              {hasPasswordProvider
                ? 'Password set'
                : 'No password set'
              }
            </p>
          </div>
        </div>
        {hasPasswordProvider ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/settings/security/change-password')}
          >
            Change Password
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAddPasswordDialog(true)}
          >
            Add Password
          </Button>
        )}
      </div>
    </div>
  </CardContent>
</Card>

// Add Password Dialog
<Dialog open={showAddPasswordDialog} onOpenChange={setShowAddPasswordDialog}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Add Password to Your Account</DialogTitle>
      <DialogDescription>
        You'll be able to sign in with either Google or your password.
      </DialogDescription>
    </DialogHeader>
    <div className="space-y-4">
      {/* Step 1: Verify identity (if Google account) */}
      {!hasRecentlyAuthenticated && (
        <Alert>
          <ShieldAlert className="h-4 w-4" />
          <AlertDescription>
            For security, please re-authenticate with Google first.
          </AlertDescription>
        </Alert>
      )}

      {/* Step 2: Set password */}
      {hasRecentlyAuthenticated && (
        <>
          <PasswordInput
            label="New Password"
            value={newPassword}
            onChange={setNewPassword}
            showStrengthMeter
          />
          <PasswordInput
            label="Confirm Password"
            value={confirmPassword}
            onChange={setConfirmPassword}
          />
        </>
      )}
    </div>
    <DialogFooter>
      <Button variant="outline" onClick={() => setShowAddPasswordDialog(false)}>
        Cancel
      </Button>
      <Button onClick={handleAddPassword}>
        {hasRecentlyAuthenticated ? 'Add Password' : 'Verify with Google'}
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

#### 1.2. Implement "Remember Me" with Session Timeout
**Impact**: High | **Effort**: Low | **Timeline**: 2-3 days

```typescript
// Login.tsx
const [rememberMe, setRememberMe] = useState(true);

async function handleLogin() {
  const persistence = rememberMe
    ? browserLocalPersistence
    : browserSessionPersistence;

  await setPersistence(auth, persistence);
  await signIn(email, password);
}

// Add checkbox in UI
<div className="flex items-center justify-between">
  <div className="flex items-center space-x-2">
    <Checkbox
      id="remember"
      checked={rememberMe}
      onCheckedChange={setRememberMe}
    />
    <label
      htmlFor="remember"
      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
    >
      Stay signed in for 30 days
    </label>
  </div>
  <Link
    to="/forgot-password"
    className="text-sm text-primary hover:underline"
  >
    Forgot password?
  </Link>
</div>
```

#### 1.3. Add Password Strength Meter
**Impact**: High | **Effort**: Low | **Timeline**: 1 day

Use existing library: `zxcvbn` (used by Dropbox, GitHub)

```bash
npm install zxcvbn
npm install --save-dev @types/zxcvbn
```

```tsx
// components/PasswordInput.tsx
import zxcvbn from 'zxcvbn';

export function PasswordInput({
  value,
  onChange,
  showStrengthMeter = false
}) {
  const strength = value ? zxcvbn(value) : null;

  return (
    <div className="space-y-2">
      <Input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />

      {showStrengthMeter && value && (
        <div className="space-y-1">
          {/* Strength bar */}
          <div className="flex gap-1">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className={cn(
                  "h-1 flex-1 rounded-full transition-colors",
                  i <= strength.score
                    ? [
                        "bg-red-500",
                        "bg-orange-500",
                        "bg-yellow-500",
                        "bg-lime-500",
                        "bg-green-500"
                      ][strength.score]
                    : "bg-gray-200"
                )}
              />
            ))}
          </div>

          {/* Strength label */}
          <p className="text-xs text-muted-foreground">
            {['Weak', 'Fair', 'Good', 'Strong', 'Excellent'][strength.score]}
          </p>

          {/* Feedback */}
          {strength.feedback.warning && (
            <p className="text-xs text-yellow-600">
              {strength.feedback.warning}
            </p>
          )}

          {strength.feedback.suggestions.map((suggestion, i) => (
            <p key={i} className="text-xs text-muted-foreground">
              💡 {suggestion}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
```

### Priority 2: Important (Implement Within 1-2 Months)

#### 2.1. Add Login History & Session Management
**Impact**: Medium | **Effort**: Medium | **Timeline**: 1 week

#### 2.2. Implement MFA/2FA with TOTP
**Impact**: High (for enterprise) | **Effort**: High | **Timeline**: 2 weeks

#### 2.3. Add Login Notifications via Email
**Impact**: Medium | **Effort**: Low | **Timeline**: 3 days

#### 2.4. Password Breach Detection (HaveIBeenPwned)
**Impact**: Medium | **Effort**: Low | **Timeline**: 1 day

### Priority 3: Nice to Have (Implement Within 3-6 Months)

#### 3.1. SSO Support (Google Workspace, Microsoft Azure AD)
**Impact**: High (for enterprise) | **Effort**: Very High | **Timeline**: 4 weeks

#### 3.2. Passkeys/WebAuthn Support
**Impact**: Medium | **Effort**: High | **Timeline**: 3 weeks

#### 3.3. Audit Logs & Security Dashboard
**Impact**: Medium (for compliance) | **Effort**: Medium | **Timeline**: 2 weeks

---

## 7. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Week 1**:
- ✅ Add "Remember Me" checkbox
- ✅ Implement password strength meter
- ✅ Add password breach checking
- ✅ Update Firestore schema for providers array

**Week 2**:
- ✅ Build account linking UI in Settings
- ✅ Implement `linkProvider()` and `unlinkProvider()` methods
- ✅ Add provider indicators throughout UI
- ✅ Write migration script for existing accounts

### Phase 2: Security Enhancement (Weeks 3-4)

**Week 3**:
- ✅ Implement login history tracking
- ✅ Build session management UI
- ✅ Add device detection and geolocation
- ✅ Create "Active Sessions" page

**Week 4**:
- ✅ Implement login email notifications
- ✅ Add suspicious activity detection
- ✅ Create security alerts system
- ✅ Add rate limiting feedback UI

### Phase 3: Advanced Features (Weeks 5-8)

**Week 5-6**:
- ✅ Implement TOTP-based MFA
- ✅ Build MFA enrollment flow
- ✅ Generate and store backup codes
- ✅ Add MFA challenge on sign-in

**Week 7-8**:
- ✅ Add inactivity timeout with warnings
- ✅ Implement "sign out all devices"
- ✅ Build security dashboard
- ✅ Add audit logging

### Phase 4: Enterprise Features (Weeks 9-12)

**Week 9-10**:
- ✅ Research SSO requirements
- ✅ Implement SAML 2.0 authentication
- ✅ Add Google Workspace SSO
- ✅ Build SSO configuration UI

**Week 11-12**:
- ✅ Implement Passkeys/WebAuthn
- ✅ Add account recovery options
- ✅ Build compliance documentation
- ✅ Security audit and penetration testing

---

## Quick Wins (Can Implement Today)

### 1. Add Provider Icon in Header (5 minutes)
```tsx
// components/Header.tsx
<div className="flex items-center gap-2">
  <Avatar>
    <AvatarImage src={user.photoURL} />
    <AvatarFallback>{initials}</AvatarFallback>
  </Avatar>
  {user.provider === 'google' && (
    <svg className="w-4 h-4" viewBox="0 0 24 24">
      {/* Google icon */}
    </svg>
  )}
</div>
```

### 2. Add "Forgot Password?" Link in Wrong Provider Message (2 minutes)
```tsx
// Login.tsx
{providerMismatch && (
  <Alert>
    <AlertDescription>
      This account was created with {existingProvider}.
      <Link to="/forgot-password" className="underline ml-1">
        Reset your password
      </Link>
      {' '}or{' '}
      <Button variant="link" onClick={signInWithCorrectProvider}>
        sign in with {existingProvider}
      </Button>
    </AlertDescription>
  </Alert>
)}
```

### 3. Show Failed Login Attempts Counter (10 minutes)
```tsx
// Login.tsx
const [failedAttempts, setFailedAttempts] = useState(0);

async function handleLogin() {
  try {
    await signIn(email, password);
    setFailedAttempts(0);
  } catch (error) {
    if (error.code === 'auth/wrong-password') {
      setFailedAttempts(prev => prev + 1);

      if (failedAttempts >= 2) {
        toast({
          title: "Multiple failed attempts",
          description: `${5 - failedAttempts} attempts remaining. Consider resetting your password.`,
          variant: "warning"
        });
      }
    }
  }
}
```

---

## Summary & Recommendations

### What You're Doing Well ✅

1. **Email Validation**: 800+ disposable domains blocked, Gmail-only policy
2. **Cross-Provider Detection**: Smart handling of provider conflicts
3. **Token Management**: Secure, automatic, no manual storage
4. **User Experience**: Clear error messages, real-time validation
5. **Theme Persistence**: User-specific, synced across devices

### Critical Gaps to Address ⚠️

1. **Account Linking**: Users can't add password after Google signup
2. **Session Timeout**: No inactivity logout or "Remember Me"
3. **Password Strength**: No strength meter or breach checking
4. **MFA/2FA**: No two-factor authentication support
5. **Session Management**: No device tracking or session list

### Top 3 Priorities

1. **Add Account Linking UI** (1-2 weeks)
   - Allows users to link multiple sign-in methods
   - Prevents lockouts
   - Better enterprise appeal

2. **Implement "Remember Me" + Session Timeout** (2-3 days)
   - Industry standard feature
   - Balances security and convenience
   - Simple to implement

3. **Add Password Strength Meter** (1 day)
   - Improves security
   - Better user experience
   - Quick win with high impact

### Long-Term Vision

**Goal**: Match security features of Stripe, GitHub, and MongoDB Atlas

**Timeline**: 3-6 months for enterprise-grade auth

**Investment**: ~200 hours of development

**ROI**:
- Higher customer trust
- Enterprise sales readiness
- Reduced support burden (fewer lockouts)
- Compliance readiness (SOC 2, GDPR)

---

## Conclusion

Your authentication system is **solid and well-architected**. The foundation is excellent, with smart provider detection and secure token management. By implementing the recommendations in this document—especially account linking, session management, and MFA—you'll have an authentication system that matches or exceeds industry leaders.

**Next Steps**:
1. Review this document with your team
2. Prioritize features based on your roadmap
3. Start with Quick Wins (can be done today)
4. Follow the Phase 1 implementation (2 weeks)
5. Iterate based on user feedback

Remember: Authentication is never "done"—it evolves with threats and user expectations. Build a foundation for continuous improvement.
