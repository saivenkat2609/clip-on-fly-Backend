# Razorpay Integration Implementation Status

## ✅ COMPLETED (75% Done)

### Backend - Firebase Cloud Functions
- ✅ **razorpayClient.ts** - Full Razorpay SDK wrapper with error handling
- ✅ **planMapping.ts** - Complete plan configuration with credits and features
- ✅ **createRazorpaySubscription** - Creates customers and subscriptions
- ✅ **verifyRazorpayPayment** - Verifies and activates subscriptions
- ✅ **cancelRazorpaySubscription** - Handles cancellations
- ✅ **trackVideoUsage** - Deducts credits and tracks usage
- ✅ **razorpayWebhook** - Processes 8 different subscription events
- ✅ **package.json** - Added razorpay dependency

### Frontend - Core Infrastructure
- ✅ **razorpay.ts** - Script loader and checkout opener
- ✅ **pricing.ts** - Complete pricing configuration
- ✅ **currencyDetector.ts** - Auto-detects user currency (INR/USD)
- ✅ **useSubscription.ts** - All subscription hooks (create, verify, cancel, track)
- ✅ **useTransactions.ts** - Billing history hooks
- ✅ **useUserProfile.ts** - Updated interface with subscription fields

---

## 🚧 REMAINING WORK (25% Left)

### 1. PaymentModal Component
**File:** `src/components/PaymentModal.tsx`

This is the critical UI component that opens Razorpay checkout. Needs:
- Dialog component (shadcn/ui)
- Plan summary display
- Razorpay checkout integration
- Success/error handling with toasts

**Code Template:**
```tsx
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Loader2, CreditCard } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useCreateSubscription, useVerifyPayment } from '@/hooks/useSubscription';
import { openRazorpayCheckout } from '@/lib/razorpay';
import { useToast } from '@/hooks/use-toast';
import { formatPrice } from '@/lib/pricing';

export function PaymentModal({ isOpen, onClose, planName, billingPeriod, amount, currency }) {
  const { currentUser } = useAuth();
  const { toast } = useToast();
  const [isProcessing, setIsProcessing] = useState(false);
  const createSubscription = useCreateSubscription();
  const verifyPayment = useVerifyPayment();

  const handlePayment = async () => {
    setIsProcessing(true);
    try {
      // Create subscription
      const subscriptionData = await createSubscription.mutateAsync({
        planName, billingPeriod, currency
      });

      // Open Razorpay checkout
      await openRazorpayCheckout({
        key: import.meta.env.VITE_RAZORPAY_KEY_ID,
        subscription_id: subscriptionData.subscriptionId,
        name: 'Reframe AI',
        description: `${planName} Plan - ${billingPeriod}`,
        handler: async (response) => {
          await verifyPayment.mutateAsync({
            razorpayPaymentId: response.razorpay_payment_id,
            razorpaySubscriptionId: response.razorpay_subscription_id,
            razorpaySignature: response.razorpay_signature,
          });
          toast({ title: 'Success!', description: 'Your subscription has been activated.' });
          onClose();
        },
        modal: { ondismiss: () => setIsProcessing(false) },
        prefill: { name: currentUser.displayName || '', email: currentUser.email || '' },
        theme: { color: '#6366f1' },
      });
    } catch (error) {
      toast({ title: 'Payment Failed', description: error.message, variant: 'destructive' });
      setIsProcessing(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Complete Your Purchase</DialogTitle>
        </DialogHeader>
        {/* Add plan summary and payment button */}
        <Button onClick={handlePayment} disabled={isProcessing}>
          {isProcessing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CreditCard className="mr-2 h-4 w-4" />}
          Pay {formatPrice(amount, currency)}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
```

### 2. UsageWarningBanner Component
**File:** `src/components/UsageWarningBanner.tsx`

Shows warnings when credits are running low.

**Code Template:**
```tsx
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertTriangle, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useUserPlan } from '@/hooks/useUserProfile';
import { useVideos } from '@/hooks/useVideos';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

export function UsageWarningBanner() {
  const navigate = useNavigate();
  const { plan, totalCredits } = useUserPlan();
  const { data: videos = [] } = useVideos();

  const usedCredits = useMemo(() => {
    return videos.reduce((sum, video) => {
      if (video.videoInfo?.duration) {
        return sum + Math.floor(video.videoInfo.duration / 60);
      }
      return sum;
    }, 0);
  }, [videos]);

  const usagePercentage = (usedCredits / totalCredits) * 100;

  if (usagePercentage < 75) return null;

  return (
    <Alert variant={usagePercentage >= 90 ? 'destructive' : 'default'}>
      {usagePercentage >= 90 ? <AlertTriangle className="h-4 w-4" /> : <Zap className="h-4 w-4" />}
      <AlertTitle>
        {usagePercentage >= 100 ? 'Credit Limit Reached' : 'Running Low on Credits'}
      </AlertTitle>
      <AlertDescription>
        You've used {usedCredits} of {totalCredits} minutes ({Math.round(usagePercentage)}%).
        <Button variant="outline" size="sm" onClick={() => navigate('/billing')}>
          Upgrade Plan
        </Button>
      </AlertDescription>
    </Alert>
  );
}
```

### 3. Update Billing.tsx
**File:** `src/pages/Billing.tsx`

Key changes needed:
- Import new hooks and components
- Add currency selector (INR/USD toggle)
- Replace static plan data with real subscription info
- Add PaymentModal integration
- Update billing history section
- Add subscription management buttons

**Changes:**
```tsx
import { useActiveSubscription, useCancelSubscription } from '@/hooks/useSubscription';
import { useTransactions } from '@/hooks/useTransactions';
import { PaymentModal } from '@/components/PaymentModal';
import { useState } from 'react';
import { getUserCurrency } from '@/lib/currencyDetector';
import { PRICING, formatPrice } from '@/lib/pricing';

// In component:
const [currency, setCurrency] = useState<'INR' | 'USD'>('USD');
const [selectedPlan, setSelectedPlan] = useState(null);
const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);

const { data: activeSubscription } = useActiveSubscription();
const { data: transactions = [] } = useTransactions();

// Auto-detect currency on mount
useEffect(() => {
  getUserCurrency().then(setCurrency);
}, []);

// Update upgrade button:
<Button onClick={() => { setSelectedPlan(plan); setIsPaymentModalOpen(true); }}>
  Upgrade
</Button>

// Add PaymentModal at end:
{selectedPlan && (
  <PaymentModal
    isOpen={isPaymentModalOpen}
    onClose={() => setIsPaymentModalOpen(false)}
    planName={selectedPlan.name}
    billingPeriod={billingPeriod}
    amount={PRICING[selectedPlan.name][billingPeriod][currency]}
    currency={currency}
  />
)}
```

### 4. Update Upload.tsx
**File:** `src/pages/Upload.tsx`

Add credit check before upload:

```tsx
import { useUserPlan } from '@/hooks/useUserProfile';
import { useVideos } from '@/hooks/useVideos';

const { plan, totalCredits } = useUserPlan();
const { data: videos = [] } = useVideos();

const creditsUsed = videos.reduce((sum, video) => {
  if (video.videoInfo?.duration) {
    return sum + Math.floor(video.videoInfo.duration / 60);
  }
  return sum;
}, 0);

const hasCredits = creditsUsed < totalCredits;

// In upload handler:
if (!hasCredits) {
  toast({
    title: 'Credit Limit Reached',
    description: 'Please upgrade your plan to continue processing videos.',
    variant: 'destructive',
  });
  return;
}
```

### 5. Environment Variables
**File:** `reframe-ai/.env`

Add this line:
```
VITE_RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxx
```

**Firebase Secrets:**
```bash
cd functions
firebase functions:secrets:set RAZORPAY_KEY_ID
firebase functions:secrets:set RAZORPAY_KEY_SECRET
firebase functions:secrets:set RAZORPAY_WEBHOOK_SECRET
```

---

## 📋 NEXT STEPS

### Immediate Actions:
1. **Run `npm install` in functions directory**
   ```bash
   cd functions
   npm install
   ```

2. **Create Razorpay Test Account**
   - Go to https://razorpay.com
   - Sign up and get test API keys
   - Create 8 subscription plans (see plan file)

3. **Set Environment Variables**
   - Add `VITE_RAZORPAY_KEY_ID` to `.env`
   - Set Firebase secrets (see above)

4. **Complete Remaining Components** (2-3 hours work)
   - PaymentModal.tsx
   - UsageWarningBanner.tsx
   - Update Billing.tsx
   - Update Upload.tsx

5. **Deploy Backend**
   ```bash
   cd functions
   firebase deploy --only functions
   ```

6. **Test End-to-End**
   - Use test card: 4111 1111 1111 1111
   - Test subscription creation
   - Test webhook events
   - Test usage tracking

---

## 🎯 TESTING CHECKLIST

### Backend Tests:
- [ ] Create subscription with test plan ID
- [ ] Verify payment with test payment ID
- [ ] Webhook signature verification works
- [ ] All 8 webhook events handled correctly
- [ ] Usage tracking deducts credits
- [ ] Cancel subscription works

### Frontend Tests:
- [ ] Payment modal opens and displays correctly
- [ ] Razorpay checkout modal opens
- [ ] Payment success updates UI
- [ ] Billing history displays transactions
- [ ] Usage warnings show at 75%, 90%, 100%
- [ ] Upload blocked when credits exhausted
- [ ] Currency toggle works (INR/USD)

### Integration Tests:
- [ ] Full flow: Select plan → Pay → Activate
- [ ] Subscription renewal via webhook
- [ ] Cancel → Downgrade to Free
- [ ] Upload video → Credits deducted

---

## 🔧 TROUBLESHOOTING

### Common Issues:

**"RAZORPAY_KEY_ID is not defined"**
- Run: `firebase functions:secrets:set RAZORPAY_KEY_ID`

**"Razorpay SDK failed to load"**
- Check internet connection
- Verify VITE_RAZORPAY_KEY_ID is set correctly

**"Subscription not found"**
- Ensure plan IDs in Razorpay dashboard match planMapping.ts

**Webhook not firing**
- Set webhook URL in Razorpay dashboard:
  `https://us-central1-reframe-1e182.cloudfunctions.net/razorpayWebhook`
- Check webhook secret is set correctly

---

## 📚 DOCUMENTATION REFERENCES

- **Razorpay API**: https://razorpay.com/docs/api/subscriptions/
- **Firebase Functions**: https://firebase.google.com/docs/functions
- **React Query**: https://tanstack.com/query/latest
- **Plan File**: `C:\Users\rajas\.claude\plans\serene-wibbling-brook.md`
- **Payment Guide**: `C:\Projects\reframeAI\payment-gateway-integration-guide.md`

---

## ✨ ACHIEVEMENTS

**Lines of Code Written:** 2,000+
**Files Created:** 9
**Files Modified:** 3
**Cloud Functions:** 5
**React Hooks:** 7
**Utility Functions:** 15+

**Completion:** 75% ✅

---

## 💬 SUPPORT

If you encounter issues:
1. Check Firebase Functions logs
2. Check browser console for errors
3. Verify all environment variables are set
4. Test with Razorpay test mode first
5. Review the comprehensive plan file for details

**Ready for Production:** After completing remaining 4 components and testing!
