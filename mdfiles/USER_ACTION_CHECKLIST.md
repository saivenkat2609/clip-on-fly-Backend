# User Action Checklist - Razorpay Payment Gateway Integration

This document contains **ALL actions YOU need to take** to deploy the Razorpay payment gateway integration.

---

## ✅ Pre-Deployment Checklist

### 1. Install Backend Dependencies
**Action Required:** Install npm packages in the functions directory

```bash
cd C:\Projects\reframeAI\reframe-ai\functions
npm install
```

**Expected Result:** `razorpay@^2.9.2` package should be installed successfully

**Common Issues:**
- If you get SSL certificate errors, try:
  - `npm config set strict-ssl false` (temporary fix)
  - Or fix your network's SSL certificate chain
- If installation fails, check your Node.js version (should be v20)

---

### 2. Create Razorpay Account

**Action Required:** Sign up and set up your Razorpay account

1. Go to https://razorpay.com
2. Click "Sign Up" button
3. Enter your business details:
   - Business Name
   - Email
   - Phone Number
4. Complete email verification
5. Log in to Razorpay Dashboard

**Expected Result:** You should have access to the Razorpay Dashboard

---

### 3. Get Razorpay Test API Keys

**Action Required:** Generate test mode API keys

1. In Razorpay Dashboard, click "Settings" (gear icon)
2. Navigate to "API Keys" section
3. Click "Generate Test Key" button
4. You'll see two keys:
   - **Key ID** (starts with `rzp_test_`) - Copy this
   - **Key Secret** (hidden) - Click "Reveal" and copy this
5. **IMPORTANT:** Save both keys securely (use password manager)

**Expected Result:** You should have:
- `rzp_test_xxxxxxxxxxxxx` (Key ID)
- `xxxxxxxxxxxxxxxxxxxxxxxx` (Key Secret)

---

### 4. Generate Webhook Secret

**Action Required:** Set up webhook endpoint and get webhook secret

1. In Razorpay Dashboard, go to "Settings" → "Webhooks"
2. Click "Add New Webhook" button
3. Enter webhook URL:
   ```
   https://us-central1-reframe-1e182.cloudfunctions.net/razorpayWebhook
   ```
   **Note:** Replace `reframe-1e182` with YOUR Firebase project ID

   To find your Firebase project ID:
   - Open `.firebaserc` file in your project root
   - Look for the `default` project name

4. Select ALL of these events:
   - ✅ subscription.activated
   - ✅ subscription.charged
   - ✅ subscription.cancelled
   - ✅ subscription.completed
   - ✅ subscription.halted
   - ✅ subscription.paused
   - ✅ subscription.resumed
   - ✅ payment.failed

5. Click "Create Webhook"
6. Copy the **Webhook Secret** (starts with `whsec_`)

**Expected Result:** Webhook configured with secret like `whsec_xxxxxxxxxxxxx`

**IMPORTANT:** Don't close this page yet - you'll update the URL after deploying functions

---

### 5. Create Subscription Plans in Razorpay

**Action Required:** Create 8 subscription plans with EXACT plan IDs

Navigate to: Dashboard → Products → Subscriptions → Plans → "Create Plan"

#### Plan 1: Starter Monthly (INR)
```
Plan Name: Starter Monthly INR
Plan ID: plan_starter_monthly_inr
Amount: 240000 (₹2,400 in paise)
Currency: INR
Billing Interval: Every 1 month
```

#### Plan 2: Starter Yearly (INR)
```
Plan Name: Starter Yearly INR
Plan ID: plan_starter_yearly_inr
Amount: 2320000 (₹23,200 in paise)
Currency: INR
Billing Interval: Every 1 year
```

#### Plan 3: Starter Monthly (USD)
```
Plan Name: Starter Monthly USD
Plan ID: plan_starter_monthly_usd
Amount: 2900 ($29 in cents)
Currency: USD
Billing Interval: Every 1 month
```

#### Plan 4: Starter Yearly (USD)
```
Plan Name: Starter Yearly USD
Plan ID: plan_starter_yearly_usd
Amount: 27900 ($279 in cents)
Currency: USD
Billing Interval: Every 1 year
```

#### Plan 5: Professional Monthly (INR)
```
Plan Name: Professional Monthly INR
Plan ID: plan_professional_monthly_inr
Amount: 656000 (₹6,560 in paise)
Currency: INR
Billing Interval: Every 1 month
```

#### Plan 6: Professional Yearly (INR)
```
Plan Name: Professional Yearly INR
Plan ID: plan_professional_yearly_inr
Amount: 6306400 (₹63,064 in paise)
Currency: INR
Billing Interval: Every 1 year
```

#### Plan 7: Professional Monthly (USD)
```
Plan Name: Professional Monthly USD
Plan ID: plan_professional_monthly_usd
Amount: 7900 ($79 in cents)
Currency: USD
Billing Interval: Every 1 month
```

#### Plan 8: Professional Yearly (USD)
```
Plan Name: Professional Yearly USD
Plan ID: plan_professional_yearly_usd
Amount: 75800 ($758 in cents)
Currency: USD
Billing Interval: Every 1 year
```

**Expected Result:** All 8 plans created in Razorpay Dashboard

**⚠️ CRITICAL:** Plan IDs MUST match exactly as shown above, or payments will fail!

**Verification:** Go to Plans list and verify all 8 plans are listed

---

### 6. Set Frontend Environment Variable

**Action Required:** Add Razorpay Key ID to frontend .env file

**File:** `C:\Projects\reframeAI\reframe-ai\.env`

If `.env` file doesn't exist, create it in the `reframe-ai` directory.

Add this line:
```env
VITE_RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxx
```

Replace `rzp_test_xxxxxxxxxxxxx` with your actual Test Key ID from Step 3.

**Example .env file:**
```env
VITE_FIREBASE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
VITE_FIREBASE_AUTH_DOMAIN=reframe-1e182.firebaseapp.com
VITE_RAZORPAY_KEY_ID=rzp_test_ABCD1234EFGH5678
```

**Expected Result:** `.env` file contains `VITE_RAZORPAY_KEY_ID`

**⚠️ IMPORTANT:** Never commit `.env` to git! Add to `.gitignore` if not already there.

---

### 7. Set Backend Firebase Secrets

**Action Required:** Store Razorpay secrets securely in Firebase

Open terminal and run these commands:

```bash
cd C:\Projects\reframeAI\reframe-ai

# Set Razorpay Key ID
firebase functions:secrets:set RAZORPAY_KEY_ID
# When prompted, paste your Key ID: rzp_test_xxxxxxxxxxxxx

# Set Razorpay Key Secret
firebase functions:secrets:set RAZORPAY_KEY_SECRET
# When prompted, paste your Key Secret (the long one)

# Set Webhook Secret
firebase functions:secrets:set RAZORPAY_WEBHOOK_SECRET
# When prompted, paste your Webhook Secret: whsec_xxxxxxxxxxxxx
```

**Expected Result:** You should see success messages for all 3 secrets

**Verify secrets are set:**
```bash
firebase functions:secrets:access RAZORPAY_KEY_ID
```

This should display your Key ID (without revealing the actual value in logs).

**Common Issues:**
- If `firebase` command not found: Install Firebase CLI with `npm install -g firebase-tools`
- If not logged in: Run `firebase login` first

---

### 8. Deploy Firebase Functions

**Action Required:** Build and deploy Cloud Functions

```bash
cd C:\Projects\reframeAI\reframe-ai\functions

# Build TypeScript to JavaScript
npm run build

# Deploy all functions (from parent directory)
cd ..
firebase deploy --only functions
```

**Expected Result:** You should see output like:
```
✔ functions[createRazorpaySubscription]: Successful create operation.
✔ functions[verifyRazorpayPayment]: Successful create operation.
✔ functions[cancelRazorpaySubscription]: Successful create operation.
✔ functions[trackVideoUsage]: Successful create operation.
✔ functions[razorpayWebhook]: Successful create operation.
```

**Copy the webhook URL** from the output. It will look like:
```
https://us-central1-reframe-1e182.cloudfunctions.net/razorpayWebhook
```

**Common Issues:**
- If build fails: Check for TypeScript errors, fix them first
- If deploy fails with permission error: Check Firebase project permissions
- If secrets not found: Go back to Step 7 and set secrets

---

### 9. Update Webhook URL in Razorpay (IMPORTANT!)

**Action Required:** Update webhook URL with deployed function URL

1. Go back to Razorpay Dashboard → Settings → Webhooks
2. Click on the webhook you created in Step 4
3. Update the URL with the actual deployed function URL from Step 8
4. Click "Save Changes"

**Expected Result:** Webhook URL matches your deployed Cloud Function

---

### 10. Deploy Firestore Security Rules and Indexes

**Action Required:** Deploy updated security rules and indexes

```bash
cd C:\Projects\reframeAI\reframe-ai

# Deploy security rules
firebase deploy --only firestore:rules

# Deploy indexes
firebase deploy --only firestore:indexes
```

**Expected Result:**
```
✔ Deploy complete!
```

**What this does:**
- Security rules: Protects subscription/transaction data (read-only for users)
- Indexes: Optimizes queries for subscription and transaction data

---

### 11. Build and Deploy Frontend

**Action Required:** Build frontend with new Razorpay integration

```bash
cd C:\Projects\reframeAI\reframe-ai

# Install dependencies (if not already done)
npm install

# Build production bundle
npm run build
```

**Expected Result:** `dist` folder created with built files

**Deploy to hosting:**

If using Firebase Hosting:
```bash
firebase deploy --only hosting
```

If using Vercel/Netlify:
- Follow their deployment process
- **IMPORTANT:** Make sure to set `VITE_RAZORPAY_KEY_ID` in their environment variables section

**Expected Result:** Frontend deployed and accessible via URL

---

### 12. Test the Integration

**Action Required:** Complete a full test payment flow

#### Test Payment Flow:

1. **Navigate to Billing Page**
   - Go to: `https://your-deployed-url.com/billing`
   - Or locally: `http://localhost:8080/billing`

2. **Check Currency Toggle**
   - Toggle between USD and INR
   - Verify prices display correctly

3. **Select a Plan**
   - Click "Upgrade" on either Starter or Professional plan
   - Choose Monthly or Yearly billing

4. **Complete Test Payment**
   - Payment modal should open
   - Click "Pay with Razorpay"
   - Razorpay checkout should appear
   - Use **test card:** `4111 1111 1111 1111`
   - CVV: Any 3 digits (e.g., `123`)
   - Expiry: Any future date (e.g., `12/25`)
   - Click "Pay"

5. **Verify Success**
   - Success toast should appear
   - Page should refresh
   - Your plan should show as "Starter" or "Professional"
   - Credits should be updated (300 or 500)

6. **Check Billing History**
   - Scroll to "Billing History" section
   - You should see your test transaction

7. **Test Upload Page**
   - Go to Upload page
   - Verify available credits display correctly
   - If you have Free plan, you should see usage warnings

8. **Check Firebase Console**
   - Go to Firestore Database
   - Navigate to `users/{your-uid}/subscriptions`
   - Verify subscription document exists
   - Navigate to `users/{your-uid}/transactions`
   - Verify transaction document exists

9. **Check Razorpay Dashboard**
   - Go to Razorpay Dashboard → Transactions
   - Your test payment should be listed
   - Go to Subscriptions
   - Your subscription should be listed as "Active"

**Expected Result:** ✅ Complete payment flow working end-to-end

**Test Cards:**
- **Success:** `4111 1111 1111 1111`
- **Failure:** `4000 0000 0000 0002`
- **3D Secure:** `4000 0000 0000 3220`

Full list: https://razorpay.com/docs/payments/payments/test-card-details/

---

### 13. Test Webhook Events (Optional but Recommended)

**Action Required:** Trigger webhook events manually

1. In Razorpay Dashboard, go to Webhooks → Logs
2. You should see events logged:
   - `subscription.activated` (when payment completed)
   - `subscription.charged` (for renewals)

3. Check Firebase Functions logs:
   ```bash
   firebase functions:log --only razorpayWebhook
   ```

4. You should see webhook processing logs

**Expected Result:** Webhooks being received and processed correctly

---

### 14. Test Subscription Cancellation

**Action Required:** Test cancel subscription flow

1. Go to Billing page
2. Click "Cancel Subscription" button
3. Confirm cancellation
4. Verify in Razorpay Dashboard that subscription is cancelled

**Expected Result:** Subscription status changes to "Cancelled"

---

### 15. Test Usage Tracking (After Video Processing)

**Action Required:** Process a video and verify credit deduction

1. Go to Upload page
2. Process a YouTube video (or upload a file)
3. After processing completes, check:
   - Credits should be deducted
   - Usage should be tracked in Firestore `users/{uid}/usage` collection

**Expected Result:** Credits deducted correctly based on video duration

**Note:** This requires your video processing pipeline to be set up

---

## 🚀 Production Deployment Checklist

### When Ready to Go Live:

- [ ] **Complete KYC Verification** in Razorpay (required for live mode)
- [ ] **Get Live API Keys** from Razorpay Dashboard
- [ ] **Create 8 Plans Again** in Live Mode (same plan IDs)
- [ ] **Update Webhook** to use live mode webhook URL
- [ ] **Update Environment Variables** to use live keys:
  - Frontend: `VITE_RAZORPAY_KEY_ID=rzp_live_xxxxx`
  - Backend: Re-run `firebase functions:secrets:set` with live keys
- [ ] **Deploy Functions** with live secrets
- [ ] **Deploy Frontend** with live key
- [ ] **Test with Real Card** (use your own card, charge will be real!)
- [ ] **Monitor First Transactions** closely for any errors
- [ ] **Set Up Alerts** in Razorpay for failed payments
- [ ] **Configure Email Notifications** (optional)

---

## 🔍 Verification Checklist

Run through this checklist to ensure everything is set up correctly:

### Backend Verification:
- [ ] `razorpay` npm package installed in `functions/node_modules`
- [ ] 3 Firebase secrets set (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET)
- [ ] 5 Cloud Functions deployed successfully
- [ ] Webhook URL matches deployed function URL
- [ ] Firestore security rules deployed
- [ ] Firestore indexes deployed

### Frontend Verification:
- [ ] `.env` file contains `VITE_RAZORPAY_KEY_ID`
- [ ] Frontend built successfully
- [ ] Frontend deployed to hosting
- [ ] Billing page loads without errors
- [ ] Payment modal opens correctly
- [ ] Razorpay checkout script loads

### Razorpay Dashboard Verification:
- [ ] Account created and verified
- [ ] 8 subscription plans created with correct plan IDs
- [ ] Webhook configured with all 8 events
- [ ] Test API keys obtained
- [ ] Webhook secret obtained

### Integration Verification:
- [ ] Can create subscription
- [ ] Payment modal opens
- [ ] Razorpay checkout loads
- [ ] Test payment succeeds
- [ ] Subscription activated
- [ ] Transaction recorded
- [ ] Credits updated
- [ ] Billing history displays
- [ ] Webhooks received
- [ ] Can cancel subscription

---

## 📞 Support & Troubleshooting

### Common Issues:

#### "Razorpay SDK failed to load"
**Solution:**
- Check browser console for errors
- Verify `VITE_RAZORPAY_KEY_ID` is set in `.env`
- Clear browser cache
- Check internet connection

#### "Plan ID not found"
**Solution:**
- Verify all 8 plans created in Razorpay Dashboard
- Check plan IDs match exactly (case-sensitive)
- Ensure using correct mode (test vs live)

#### "Webhook signature verification failed"
**Solution:**
- Verify webhook secret set correctly in Firebase secrets
- Check webhook URL in Razorpay matches deployed function
- Ensure all 8 events are selected

#### "Insufficient credits"
**Solution:**
- Check user's `creditsUsed` in Firestore
- Verify `totalCredits` is set correctly based on plan
- Credits reset on subscription renewal (first of month)

#### Payment Modal Doesn't Open
**Solution:**
- Check browser console for errors
- Verify Razorpay script loaded (Network tab)
- Check Firebase Functions logs for errors
- Ensure user is authenticated

#### Firebase Functions Deployment Fails
**Solution:**
- Run `npm run build` first to check for TypeScript errors
- Verify Firebase secrets are set
- Check Firebase project permissions
- Ensure correct Firebase project selected

---

## 📚 Documentation References

- **Setup Guide:** `SETUP_AND_DEPLOYMENT.md`
- **Implementation Summary:** `IMPLEMENTATION_COMPLETE.md`
- **Best Practices:** `payment-gateway-integration-guide.md`
- **Razorpay Docs:** https://razorpay.com/docs/
- **Firebase Docs:** https://firebase.google.com/docs

---

## ✅ Final Verification

**Before marking as complete, verify:**

1. ✅ All dependencies installed
2. ✅ Razorpay account created
3. ✅ 8 subscription plans created
4. ✅ Environment variables set (frontend + backend)
5. ✅ Firebase Functions deployed
6. ✅ Webhook configured
7. ✅ Firestore rules and indexes deployed
8. ✅ Frontend deployed
9. ✅ Test payment completed successfully
10. ✅ Webhooks working
11. ✅ Subscription management working
12. ✅ Usage tracking working

**If all items checked:** 🎉 **You're ready to go live!**

---

## 🎯 Quick Start Summary

For experienced developers, here's the TL;DR:

```bash
# 1. Install backend dependencies
cd functions && npm install

# 2. Set environment variables
echo "VITE_RAZORPAY_KEY_ID=rzp_test_xxxxx" > .env
firebase functions:secrets:set RAZORPAY_KEY_ID
firebase functions:secrets:set RAZORPAY_KEY_SECRET
firebase functions:secrets:set RAZORPAY_WEBHOOK_SECRET

# 3. Create 8 plans in Razorpay Dashboard (manual step)

# 4. Deploy everything
cd .. && firebase deploy

# 5. Test payment with card: 4111 1111 1111 1111
```

**Remember:** Create 8 subscription plans manually in Razorpay Dashboard with exact plan IDs!

---

**Last Updated:** December 25, 2025
**Status:** Ready for Deployment
**Estimated Setup Time:** 2-3 hours

Good luck with your deployment! 🚀
