# YouTube API Verification Guide

## Table of Contents
1. [Overview](#overview)
2. [Why Verification is Needed](#why-verification-is-needed)
3. [Pre-Verification Checklist](#pre-verification-checklist)
4. [Verification Process](#verification-process)
5. [Domain Changes & Re-Verification](#domain-changes--re-verification)
6. [Timeline & Tips](#timeline--tips)
7. [Common Issues](#common-issues)

---

## Overview

YouTube API verification (also called OAuth App Verification) is required when your application:
- Requests sensitive YouTube scopes (like `youtube.upload`, `youtube.force-ssl`)
- Will be used by users outside your development team
- Needs to post videos to user accounts without showing "unverified app" warnings

**Without verification:** Users see scary warning messages saying your app is "unverified" and may choose not to grant permissions.

**With verification:** Clean, professional OAuth consent screen with your app name and logo.

---

## Why Verification is Needed

Your app (`NebulaAI`) requests these YouTube scopes:
```javascript
'https://www.googleapis.com/auth/youtube.upload'
'https://www.googleapis.com/auth/youtube.force-ssl'
```

These are **restricted scopes** that require Google verification because they:
- Upload content to YouTube on behalf of users
- Have potential for abuse (spam, malware distribution)
- Access sensitive user data

---

## Pre-Verification Checklist

### ✅ Before Applying, Ensure You Have:

#### 1. **Published Application**
- [ ] Website is live and publicly accessible (not localhost)
- [ ] OAuth redirect URIs point to production domain
- [ ] Privacy Policy page is published and accessible
- [ ] Terms of Service page is published (recommended)

#### 2. **Google Cloud Project Setup**
- [ ] OAuth consent screen fully configured
- [ ] App name, logo, and support email set
- [ ] Authorized domains added (e.g., `netlify.app` or your custom domain)
- [ ] Privacy Policy URL added to OAuth consent screen
- [ ] OAuth Client ID created and configured

#### 3. **Required Pages on Your Website**

**Privacy Policy (MANDATORY):**
- Must be publicly accessible without login
- Must explain what data you collect from YouTube
- Must explain how you use, store, and protect user data
- Example URL: `https://yourapp.netlify.app/privacy-policy`

**Terms of Service (RECOMMENDED):**
- User agreement for your service
- Example URL: `https://yourapp.netlify.app/terms-of-service`

**Homepage (MANDATORY):**
- Clear explanation of what your app does
- Visible branding (logo, app name)
- Example URL: `https://yourapp.netlify.app`

#### 4. **Working YouTube Integration**
- [ ] OAuth flow works end-to-end
- [ ] Users can successfully authorize YouTube access
- [ ] Video upload functionality works
- [ ] Test with multiple Google accounts

#### 5. **Verification Video (REQUIRED)**
- [ ] Record a screencast showing your app's YouTube integration
- [ ] Video should demonstrate:
  - User clicking "Connect YouTube"
  - OAuth consent screen appearing
  - User granting permissions
  - Video successfully uploading to YouTube
- [ ] Upload to YouTube or Google Drive (unlisted is fine)
- [ ] Keep video under 3 minutes

---

## Verification Process

### Step 1: Go to Google Cloud Console

1. Visit: https://console.cloud.google.com
2. Select your project (e.g., `reframe-1e182`)
3. Go to **APIs & Services** → **OAuth consent screen**

### Step 2: Fill Out OAuth Consent Screen

**App Information:**
- **App name:** NebulaAI (or your app name)
- **User support email:** Your support email
- **App logo:** Upload your app logo (120x120px PNG/JPG)
- **App domain:** `https://yourapp.netlify.app`

**App Domain URLs:**
- **Application home page:** `https://yourapp.netlify.app`
- **Privacy policy:** `https://yourapp.netlify.app/privacy-policy`
- **Terms of service:** `https://yourapp.netlify.app/terms-of-service` (optional)

**Authorized domains:**
- Add: `netlify.app` (if using Netlify)
- Add: `yourdomain.com` (if you have custom domain)
- Add: `cloudfunctions.net` (for Firebase Functions redirect)

**Developer contact information:**
- Add your email address

**Scopes:**
- Ensure YouTube scopes are added:
  - `https://www.googleapis.com/auth/youtube.upload`
  - `https://www.googleapis.com/auth/youtube.force-ssl`

**Save** the consent screen configuration.

---

### Step 3: Submit for Verification

1. On the **OAuth consent screen** page, look for:
   - **"Publish App"** button (click it first to publish)
   - **"Prepare for verification"** or **"Submit for verification"** button

2. Click **"Submit for verification"** or **"Prepare for verification"**

3. You'll be taken to a form with these sections:

#### **Section A: App Information**
- Confirm app name, logo, and domain
- Verify privacy policy URL is accessible

#### **Section B: OAuth Scopes Justification**

For each restricted scope, explain:

**For `youtube.upload`:**
```
Justification:
Our application (NebulaAI) allows users to create and edit short-form video
clips from longer videos. Users can then directly publish their edited clips
to their own YouTube channels with a single click. We need the youtube.upload
scope to upload videos to the user's YouTube account on their behalf after
they've edited and approved the content.

User Benefit:
Streamlines the video publishing workflow by eliminating the need to download
videos and manually upload them to YouTube.
```

**For `youtube.force-ssl`:**
```
Justification:
Required to access and manage the user's YouTube channel information and
metadata. This scope works in conjunction with youtube.upload to properly
set video titles, descriptions, tags, and privacy settings when publishing
user-edited clips.

User Benefit:
Allows users to customize video metadata (title, description, tags) and
privacy settings directly within our app before publishing to YouTube.
```

#### **Section C: Demo Video**

Upload your verification video showing:
1. User journey from login to YouTube authorization
2. OAuth consent screen appearing
3. User granting permissions
4. Video being uploaded to YouTube
5. Confirmation of upload success

**Video Requirements:**
- Must show actual working functionality (not a mock-up)
- Audio narration helpful but not required
- Keep under 3 minutes
- Must be accessible to Google reviewers (YouTube unlisted link works)

#### **Section D: Additional Information**

**Test Account Credentials (if applicable):**
- If your app requires login before YouTube integration, provide test credentials
- Google reviewers will use these to test your app

**Additional Notes:**
```
Additional Context:
- Our application is a video editing SaaS platform for content creators
- We only upload videos that users explicitly create and approve within our app
- Users maintain full control over their YouTube account
- We do not access or modify any existing YouTube content
- All uploads are initiated by user action (clicking "Post to YouTube" button)
```

---

### Step 4: Submit and Wait

1. Review all information carefully
2. Click **"Submit"**
3. You'll receive a confirmation email from Google

**Verification Timeline:**
- Google typically responds within **4-6 weeks**
- Can take up to **8 weeks** during busy periods
- You'll receive email updates on status

---

## Domain Changes & Re-Verification

### Scenario 1: Currently Using Netlify Subdomain

**Current domain:** `yourapp.netlify.app`

**Steps when moving to custom domain:**

1. **Add New Domain to Google Cloud Console:**
   - Go to **OAuth consent screen**
   - Under **Authorized domains**, add your new domain: `yourdomain.com`
   - Keep old domain (`netlify.app`) until migration is complete

2. **Update OAuth Redirect URIs:**
   - Go to **Credentials** → Your OAuth Client
   - Add new redirect URIs with custom domain
   - Example: `https://yourdomain.com/auth/youtube/callback`

3. **Update Website URLs:**
   - Update Privacy Policy URL: `https://yourdomain.com/privacy-policy`
   - Update Homepage URL: `https://yourdomain.com`

4. **Re-Verification Required?**

   **NO re-verification needed if:**
   - ✅ You add the new domain to **Authorized domains** before switching
   - ✅ You keep the same OAuth Client ID
   - ✅ You only change the domain (not scopes or app functionality)

   **YES re-verification needed if:**
   - ❌ You remove the old domain before adding the new one
   - ❌ You create a new OAuth Client ID
   - ❌ You add new restricted scopes
   - ❌ You significantly change app functionality

### Scenario 2: Smooth Domain Migration

**Best Practice (NO re-verification):**

```
Step 1: While still on netlify.app
  ├─ Add yourdomain.com to Authorized domains
  └─ Add new redirect URIs with yourdomain.com

Step 2: Deploy to custom domain
  ├─ Update DNS records
  └─ Deploy app to yourdomain.com

Step 3: Update OAuth consent screen URLs
  ├─ Change homepage to yourdomain.com
  └─ Update Privacy Policy URL to yourdomain.com

Step 4: Test thoroughly
  └─ Verify OAuth flow works on new domain

Step 5 (optional, after 30 days): Remove old domain
  └─ Remove netlify.app from Authorized domains
```

**⚠️ IMPORTANT:**
- Add the new domain BEFORE you switch
- Keep both domains authorized during transition
- Don't remove old domain until new domain is fully working

---

## Timeline & Tips

### Expected Timeline

| Stage | Duration |
|-------|----------|
| Prepare application & pages | 1-2 weeks |
| Submit verification request | 1 day |
| Google initial review | 2-3 weeks |
| Respond to questions (if any) | 1 week |
| Final approval | 1-2 weeks |
| **Total** | **4-8 weeks** |

### Tips for Faster Approval

1. **Be Detailed:** More explanation = fewer follow-up questions
2. **Professional Presentation:** Clean, working website with clear branding
3. **Clear Demo Video:** Show exactly how YouTube integration works
4. **Responsive:** Reply to Google's emails within 24-48 hours
5. **Accurate Scope Justification:** Explain clearly why you need each scope

### What Happens During Review

Google reviewers will:
- Visit your website and privacy policy
- Watch your demo video
- Test your OAuth flow (if test credentials provided)
- Verify scope usage matches your justification
- Check for security best practices

---

## Common Issues

### Issue 1: "Authorized Domain Not Verified"

**Problem:** Google can't verify ownership of your domain

**Solution for Netlify:**
- Netlify domains are pre-verified
- Use `netlify.app` as authorized domain (not `yourapp.netlify.app`)
- For custom domains, verify via Google Search Console

**Solution for Custom Domain:**
1. Go to https://search.google.com/search-console
2. Add and verify your domain
3. Then add to OAuth consent screen

---

### Issue 2: "Privacy Policy Not Accessible"

**Problem:** Google reviewers can't access your privacy policy

**Solution:**
- Must be accessible WITHOUT login
- Must be at exact URL specified in OAuth consent screen
- Test in incognito browser
- Check: `https://yourapp.netlify.app/privacy-policy`

---

### Issue 3: "Scope Justification Insufficient"

**Problem:** Google wants more details on why you need specific scopes

**Solution:**
- Explain specific user action that triggers API call
- Describe alternative solutions you considered
- Explain why this scope is minimum required
- Reference Google's API documentation

---

### Issue 4: "Demo Video Unclear"

**Problem:** Reviewers can't understand your app flow

**Solution:**
- Re-record with narration explaining each step
- Show full user journey (not just API calls)
- Include text annotations
- Zoom in on important UI elements

---

### Issue 5: "App is Not Published"

**Problem:** Forgot to click "Publish App" before submitting for verification

**Solution:**
1. Go to OAuth consent screen
2. Click **"Publish App"** button
3. Then click **"Submit for verification"**

---

## Quick Reference Checklist

Before submitting, verify ALL these items:

### Technical Setup
- [ ] OAuth consent screen fully configured
- [ ] OAuth Client ID created
- [ ] Redirect URIs match your production URLs
- [ ] Firebase Functions deployed with correct YouTube scopes
- [ ] App published to production (not localhost)

### Website Requirements
- [ ] Homepage is live and accessible
- [ ] Privacy Policy page is live and accessible (without login)
- [ ] Terms of Service page is live (optional but recommended)
- [ ] App branding (logo, name) is professional

### Verification Submission
- [ ] App is "Published" (not in Testing mode)
- [ ] Authorized domains added correctly
- [ ] Scope justifications written clearly
- [ ] Demo video recorded and uploaded
- [ ] Test credentials provided (if app requires login)
- [ ] All URLs in OAuth consent screen are working

### Domain Setup
- [ ] If using Netlify: authorized domain is `netlify.app`
- [ ] If using custom domain: domain verified in Google Search Console
- [ ] If planning domain change: both domains added to authorized domains

---

## Support & Resources

**Google OAuth Verification Resources:**
- OAuth App Verification: https://support.google.com/cloud/answer/9110914
- OAuth Consent Screen: https://support.google.com/cloud/answer/10311615
- YouTube API Verification: https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps

**Google Search Console (Domain Verification):**
- https://search.google.com/search-console

**Contact Google Support:**
- https://support.google.com/cloud/contact/oauth_app_verification

---

## Summary

1. ✅ **Prepare:** Build working app with Privacy Policy and demo video
2. ✅ **Configure:** Set up OAuth consent screen completely
3. ✅ **Submit:** Fill verification form with detailed justifications
4. ✅ **Wait:** 4-8 weeks for review
5. ✅ **Domain Change:** Add new domain BEFORE switching (no re-verification needed)

**Most Important:**
- Add new domain to authorized domains BEFORE migrating
- Keep old domain until new domain is working
- This prevents need for re-verification

Good luck with your verification! 🚀
