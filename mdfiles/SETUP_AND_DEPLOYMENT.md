# Razorpay Integration - Setup & Deployment Guide

## 🎉 Implementation Complete!

All code has been written and integrated. Follow this guide to configure and deploy.

---

## Step 1: Install Backend Dependencies

```bash
cd C:\Projects\reframeAI\reframe-ai\functions
npm install
```

This will install the `razorpay` package (v2.9.2) along with all other dependencies.

---

## Step 2: Create Razorpay Account & Get API Keys

### 2.1 Sign Up
1. Go to https://razorpay.com
2. Click "Sign Up" and create an account
3. Complete email verification

### 2.2 Get Test API Keys
1. Log in to Razorpay Dashboard
2. Go to **Settings** → **API Keys**
3. Click **Generate Test Key**
4. Copy both:
   - **Key ID** (starts with `rzp_test_`)
   - **Key Secret** (keep this secure!)

### 2.3 Generate Webhook Secret
1. Go to **Settings** → **Webhooks**
2. Click **Add New Webhook**
3. Set URL: `https://us-central1-reframe-1e182.cloudfunctions.net/razorpayWebhook`
   (Update `reframe-1e182` with your Firebase project ID)
4. Select events to listen:
   - subscription.activated
   - subscription.charged
   - subscription.cancelled
   - subscription.completed
   - subscription.halted
   - subscription.paused
   - subscription.resumed
   - payment.failed
5. Click **Create** and copy the **Webhook Secret**

---

## Step 3: Create Subscription Plans in Razorpay

You need to create 8 subscription plans in Razorpay Dashboard.

### 3.1 Navigate to Plans
1. Go to **Products** → **Subscriptions** → **Plans**
2. Click **Create Plan**

### 3.2 Create Each Plan

**Plan 1: Starter Monthly (INR)**
- Plan Name: `Starter Monthly INR`
- Plan ID: `plan_starter_monthly_inr`
- Amount: `240000` (₹2,400 in paise)
- Currency: `INR`
- Billing Interval: `1 month`

**Plan 2: Starter Yearly (INR)**
- Plan Name: `Starter Yearly INR`
- Plan ID: `plan_starter_yearly_inr`
- Amount: `2320000` (₹23,200 in paise)
- Currency: `INR`
- Billing Interval: `1 year`

**Plan 3: Starter Monthly (USD)**
- Plan Name: `Starter Monthly USD`
- Plan ID: `plan_starter_monthly_usd`
- Amount: `2900` ($29 in cents)
- Currency: `USD`
- Billing Interval: `1 month`

**Plan 4: Starter Yearly (USD)**
- Plan Name: `Starter Yearly USD`
- Plan ID: `plan_starter_yearly_usd`
- Amount: `27900` ($279 in cents)
- Currency: `USD`
- Billing Interval: `1 year`

**Plan 5: Professional Monthly (INR)**
- Plan Name: `Professional Monthly INR`
- Plan ID: `plan_professional_monthly_inr`
- Amount: `656000` (₹6,560 in paise)
- Currency: `INR`
- Billing Interval: `1 month`

**Plan 6: Professional Yearly (INR)**
- Plan Name: `Professional Yearly INR`
- Plan ID: `plan_professional_yearly_inr`
- Amount: `6306400` (₹63,064 in paise)
- Currency: `INR`
- Billing Interval: `1 year`

**Plan 7: Professional Monthly (USD)**
- Plan Name: `Professional Monthly USD`
- Plan ID: `plan_professional_monthly_usd`
- Amount: `7900` ($79 in cents)
- Currency: `USD`
- Billing Interval: `1 month`

**Plan 8: Professional Yearly (USD)**
- Plan Name: `Professional Yearly USD`
- Plan ID: `plan_professional_yearly_usd`
- Amount: `75800` ($758 in cents)
- Currency: `USD`
- Billing Interval: `1 year`

**IMPORTANT:** Plan IDs must match exactly as shown above!

---

## Step 4: Set Environment Variables

### 4.1 Frontend Environment Variables

**File:** `C:\Projects\reframeAI\reframe-ai\.env`

Add this line (create file if it doesn't exist):

```env
VITE_RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxx
```

Replace `rzp_test_xxxxxxxxxxxxx` with your actual Razorpay Test Key ID.

### 4.2 Backend Firebase Secrets

Run these commands in your terminal:

```bash
cd C:\Projects\reframeAI\reframe-ai\functions

# Set Razorpay Key ID
firebase functions:secrets:set RAZORPAY_KEY_ID
# When prompted, paste: rzp_test_xxxxxxxxxxxxx

# Set Razorpay Key Secret
firebase functions:secrets:set RAZORPAY_KEY_SECRET
# When prompted, paste your key secret

# Set Webhook Secret
firebase functions:secrets:set RAZORPAY_WEBHOOK_SECRET
# When prompted, paste your webhook secret
```

**Verify secrets are set:**
```bash
firebase functions:secrets:access RAZORPAY_KEY_ID
```

---

## Step 5: Deploy Firebase Functions

### 5.1 Build TypeScript
```bash
cd C:\Projects\reframeAI\reframe-ai\functions
npm run build
```

### 5.2 Deploy All Functions
```bash
firebase deploy --only functions
```

This will deploy:
- createRazorpaySubscription
- verifyRazorpayPayment
- cancelRazorpaySubscription
- trackVideoUsage
- razorpayWebhook

### 5.3 Verify Deployment
After deployment, you'll see URLs like:
```
✔ functions[razorpayWebhook]: https://us-central1-reframe-1e182.cloudfunctions.net/razorpayWebhook
✔ functions[createRazorpaySubscription]: ...
```

**IMPORTANT:** Copy the webhook URL and update it in Razorpay Dashboard (Step 2.3)

---

## Step 6: Deploy Frontend

### 6.1 Build Frontend
```bash
cd C:\Projects\reframeAI\reframe-ai
npm run build
```

### 6.2 Deploy to Hosting
```bash
firebase deploy --only hosting
```

Or deploy to your hosting provider (Vercel, Netlify, etc.)

---

## Step 7: Test the Integration

### 7.1 Test Cards (Razorpay Test Mode)

**Success:**
- Card: `4111 1111 1111 1111`
- CVV: Any 3 digits
- Expiry: Any future date

**Decline:**
- Card: `4000 0000 0000 0002`

**Other test cards:** https://razorpay.com/docs/payments/payments/test-card-details/

### 7.2 Test Flow

1. **Navigate to Billing Page**
   - Go to http://localhost:8080/billing (dev) or your deployed URL
   - You should see the pricing plans with INR/USD toggle

2. **Select a Plan**
   - Toggle between Monthly/Yearly
   - Toggle between USD/INR
   - Click "Upgrade" on Starter or Professional plan

3. **Complete Payment**
   - Payment modal should open
   - Click "Pay with Razorpay"
   - Razorpay checkout should open
   - Enter test card: `4111 1111 1111 1111`
   - Complete payment

4. **Verify Activation**
   - You should see success toast
   - Current plan should update to selected plan
   - Credits should be updated
   - Transaction should appear in billing history

5. **Test Usage Tracking**
   - Go to Upload page
   - You should see available credits
   - Upload/process a video
   - Credits should be deducted (Note: actual tracking happens after video processing)

6. **Test Webhook**
   - Check Firebase Functions logs:
     ```bash
     firebase functions:log
     ```
   - You should see webhook events logged

---

## Step 8: Production Deployment

### 8.1 Switch to Live Mode

1. **Get Live API Keys**
   - In Razorpay Dashboard, go to Settings → API Keys
   - Click "Generate Live Key"
   - Complete KYC verification if required
   - Copy Live Key ID and Secret

2. **Create Live Plans**
   - Create all 8 plans again in Live mode with same Plan IDs

3. **Update Webhook**
   - Add production webhook URL in Live mode

4. **Update Environment Variables**
   ```bash
   # Frontend
   VITE_RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxx

   # Backend
   firebase functions:secrets:set RAZORPAY_KEY_ID
   # Paste live key ID
   firebase functions:secrets:set RAZORPAY_KEY_SECRET
   # Paste live key secret
   ```

5. **Deploy**
   ```bash
   firebase deploy
   ```

### 8.2 Production Checklist

- [ ] KYC verification completed in Razorpay
- [ ] Live API keys obtained
- [ ] All 8 live plans created with correct Plan IDs
- [ ] Live webhook configured
- [ ] Environment variables updated
- [ ] Firebase Functions deployed
- [ ] Frontend deployed
- [ ] Test payment with real card
- [ ] Monitor first transactions carefully

---

## Troubleshooting

### "RAZORPAY_KEY_ID is not defined"
**Solution:** Run `firebase functions:secrets:set RAZORPAY_KEY_ID`

### "Razorpay SDK failed to load"
**Solution:**
- Check internet connection
- Verify VITE_RAZORPAY_KEY_ID in .env
- Clear browser cache

### "Plan ID not found"
**Solution:**
- Verify plan IDs in Razorpay dashboard match exactly
- Check planMapping.ts for typos
- Ensure plans are in correct mode (test/live)

### "Webhook signature verification failed"
**Solution:**
- Verify webhook secret is set correctly
- Check webhook URL in Razorpay dashboard
- Ensure webhook events are selected

### "Subscription not found"
**Solution:**
- Check Firestore for subscription document
- Verify user_id matches
- Check Firebase Functions logs for errors

### Payment Modal Doesn't Open
**Solution:**
- Check browser console for errors
- Verify Razorpay script loaded (check Network tab)
- Check that VITE_RAZORPAY_KEY_ID is set

---

## Monitoring

### Firebase Functions Logs
```bash
firebase functions:log --only razorpayWebhook
firebase functions:log --only createRazorpaySubscription
```

### Razorpay Dashboard
- Go to **Transactions** to see all payments
- Go to **Subscriptions** to see all subscriptions
- Go to **Webhooks** → **Logs** to see webhook events

### Firestore Console
Check these collections:
- `users/{userId}/subscriptions/`
- `users/{userId}/transactions/`
- `users/{userId}/usage/`

---

## Security Best Practices

✅ **DO:**
- Keep Key Secret and Webhook Secret secure
- Use Firebase Secrets for backend keys
- Verify webhook signatures
- Validate all inputs server-side
- Log all transactions
- Monitor for suspicious activity

❌ **DON'T:**
- Commit secrets to git
- Expose Key Secret in frontend
- Skip webhook signature verification
- Trust client-side data
- Store card details

---

## Support Resources

- **Razorpay Docs:** https://razorpay.com/docs/
- **Razorpay Support:** support@razorpay.com
- **Firebase Docs:** https://firebase.google.com/docs
- **Implementation Guide:** `RAZORPAY_IMPLEMENTATION_STATUS.md`
- **Plan File:** `C:\Users\rajas\.claude\plans\serene-wibbling-brook.md`

---

## Quick Reference

### Test Mode URLs
- Dashboard: https://dashboard.razorpay.com/test
- Webhook: https://us-central1-YOUR-PROJECT.cloudfunctions.net/razorpayWebhook

### Plan IDs (MUST MATCH)
```
plan_starter_monthly_inr
plan_starter_yearly_inr
plan_starter_monthly_usd
plan_starter_yearly_usd
plan_professional_monthly_inr
plan_professional_yearly_inr
plan_professional_monthly_usd
plan_professional_yearly_usd
```

### Currency Conversion (Approximate)
- 1 USD = 83 INR
- Remember: Razorpay amounts are in smallest unit (paise for INR, cents for USD)

---

## 🎉 You're All Set!

Your Razorpay integration is complete and ready to go. Follow the steps above to configure and deploy.

**Next Steps:**
1. Complete Razorpay account setup (Step 2)
2. Create subscription plans (Step 3)
3. Set environment variables (Step 4)
4. Deploy functions (Step 5)
5. Test thoroughly (Step 7)
6. Go live! (Step 8)

Good luck! 🚀
