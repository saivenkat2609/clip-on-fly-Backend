# Payment Gateway Integration Best Practices Guide

## Table of Contents
1. [Overview](#overview)
2. [Choosing a Payment Gateway](#choosing-a-payment-gateway)
3. [Security Best Practices](#security-best-practices)
4. [Integration Approaches](#integration-approaches)
5. [International Payment Considerations](#international-payment-considerations)
6. [Technical Implementation](#technical-implementation)
7. [Error Handling & Resilience](#error-handling--resilience)
8. [Testing Strategy](#testing-strategy)
9. [Compliance & Legal](#compliance--legal)
10. [User Experience Best Practices](#user-experience-best-practices)

---

## Overview

Payment gateway integration is a critical component of any e-commerce or SaaS application. This guide outlines industry best practices for securely and efficiently integrating payment services, with a focus on international transactions.

### Key Principles
- **Security First**: Never store sensitive payment data on your servers
- **Compliance**: Adhere to PCI DSS standards and local regulations
- **User Experience**: Minimize friction in the payment process
- **Reliability**: Implement robust error handling and retry mechanisms
- **Transparency**: Provide clear pricing, fees, and transaction status

---

## Choosing a Payment Gateway

### Popular International Payment Gateways

#### **Stripe**
- **Strengths**: Developer-friendly, extensive documentation, supports 135+ currencies
- **Use Case**: Best for SaaS, subscription services, and global businesses
- **Coverage**: 45+ countries
- **Features**: Strong fraud detection, recurring billing, marketplace support

#### **PayPal/Braintree**
- **Strengths**: Widely recognized, supports 200+ markets and 100+ currencies
- **Use Case**: E-commerce, marketplaces, businesses needing brand recognition
- **Features**: Buyer protection, one-touch payments, Venmo integration

#### **Adyen**
- **Strengths**: Single platform for global payments, supports 250+ payment methods
- **Use Case**: Large enterprises, omnichannel businesses
- **Features**: Advanced routing, revenue optimization, unified reporting

#### **Square**
- **Strengths**: Excellent for point-of-sale and online integration
- **Use Case**: Retail, restaurants, small to medium businesses
- **Features**: Hardware integration, inventory management

#### **Razorpay** (Asia-Pacific)
- **Strengths**: Strong presence in India and Southeast Asia
- **Use Case**: Businesses targeting Indian and regional markets
- **Features**: UPI, wallets, EMI options, local payment methods

#### **Mollie** (Europe)
- **Strengths**: Popular in Europe, supports local payment methods
- **Use Case**: European businesses, e-commerce
- **Features**: iDEAL, SEPA, Bancontact, and other EU methods

### Selection Criteria

1. **Geographic Coverage**: Does it support your target markets?
2. **Payment Methods**: Credit/debit cards, digital wallets, bank transfers, local methods
3. **Currency Support**: Multi-currency processing and settlement
4. **Fees**: Transaction fees, monthly fees, currency conversion fees
5. **Integration Complexity**: API quality, SDKs, documentation
6. **Settlement Time**: How quickly funds are transferred to your account
7. **Support**: Developer support, customer service quality
8. **Compliance**: PCI DSS Level 1, local regulatory compliance
9. **Features**: Recurring billing, fraud detection, dispute management
10. **Scalability**: Can it handle your growth projections?

---

## Security Best Practices

### PCI DSS Compliance

**Never store sensitive card data** on your servers. Use one of these approaches:

#### Level 1: Hosted Payment Pages (Lowest PCI Burden)
- Redirect users to payment gateway's secure page
- Gateway handles all sensitive data
- Minimal compliance requirements for your application

#### Level 2: Tokenization (Recommended)
- Collect payment details in an iframe or via JavaScript SDK
- Gateway converts card data to a token on client-side
- Only tokens are sent to your server
- Requires SAQ-A compliance (~20 questions)

#### Level 3: Direct API Integration (Highest Burden)
- Your server handles raw card data
- Requires full PCI DSS compliance (SAQ-D, ~300 controls)
- **NOT RECOMMENDED** unless absolutely necessary

### Implementation Security

```javascript
// DO: Use tokenization
// Client-side with Stripe.js
const {token, error} = await stripe.createToken(cardElement);
// Send only the token to your server
fetch('/api/charge', {
  method: 'POST',
  body: JSON.stringify({ token: token.id })
});

// DON'T: Send raw card data to your server
fetch('/api/charge', {
  method: 'POST',
  body: JSON.stringify({
    cardNumber: '4242424242424242', // NEVER DO THIS
    cvv: '123',
    expiry: '12/25'
  })
});
```

### Essential Security Measures

1. **Use HTTPS/TLS**: All payment-related pages must use SSL/TLS certificates
2. **Implement CSP**: Content Security Policy headers to prevent XSS
3. **Input Validation**: Validate all input server-side, never trust client data
4. **Rate Limiting**: Prevent brute force attacks on payment endpoints
5. **Fraud Detection**: Use gateway's built-in fraud tools + custom rules
6. **3D Secure/SCA**: Implement Strong Customer Authentication (required in EU)
7. **Secure Webhooks**: Verify webhook signatures to prevent spoofing
8. **Logging**: Log all transactions but never log sensitive data
9. **Access Control**: Restrict access to payment endpoints and admin panels
10. **Regular Updates**: Keep all dependencies and SDKs up to date

### Data Protection

```javascript
// Example: Webhook signature verification (Stripe)
const verifyWebhook = (req) => {
  const signature = req.headers['stripe-signature'];
  try {
    const event = stripe.webhooks.constructEvent(
      req.body,
      signature,
      process.env.WEBHOOK_SECRET
    );
    return event;
  } catch (err) {
    throw new Error('Invalid signature');
  }
};
```

---

## Integration Approaches

### 1. Hosted Payment Pages (Redirect)

**How it works**: User is redirected to gateway's payment page, then back to your site.

**Pros**:
- Minimal PCI compliance burden
- Gateway handles UI and security
- Quick to implement

**Cons**:
- Less control over user experience
- Potential drop-off during redirect
- Limited customization

**Best for**: Startups, small businesses, low transaction volumes

```javascript
// Example: PayPal Express Checkout
app.post('/create-payment', async (req, res) => {
  const payment = {
    intent: 'sale',
    redirect_urls: {
      return_url: 'https://yoursite.com/success',
      cancel_url: 'https://yoursite.com/cancel'
    },
    transactions: [{
      amount: { total: '10.00', currency: 'USD' }
    }]
  };

  const result = await paypal.payment.create(payment);
  res.redirect(result.links.find(l => l.rel === 'approval_url').href);
});
```

### 2. Embedded Payment Forms (iframe/SDK)

**How it works**: Gateway provides an iframe or JavaScript SDK that embeds in your page.

**Pros**:
- Better user experience (no redirect)
- Moderate compliance requirements
- Some customization options

**Cons**:
- Requires JavaScript
- Limited styling control
- Slightly more complex integration

**Best for**: Most web applications (RECOMMENDED)

```javascript
// Example: Stripe Elements
const stripe = Stripe('pk_test_...');
const elements = stripe.elements();
const cardElement = elements.create('card', {
  style: {
    base: {
      fontSize: '16px',
      color: '#32325d',
    }
  }
});
cardElement.mount('#card-element');

// Handle form submission
const form = document.getElementById('payment-form');
form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const {token, error} = await stripe.createToken(cardElement);
  if (error) {
    // Display error
    return;
  }

  // Send token to your server
  const response = await fetch('/api/charge', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ token: token.id, amount: 1000 })
  });
});
```

### 3. Payment Request API / Digital Wallets

**How it works**: Integrate Apple Pay, Google Pay, and other digital wallets.

**Pros**:
- Fastest checkout experience
- Higher conversion rates
- Increased security
- Mobile-optimized

**Cons**:
- Limited to supported devices/browsers
- Additional setup required

**Best for**: Mobile apps, modern web apps with significant mobile traffic

```javascript
// Example: Stripe Payment Request Button
const paymentRequest = stripe.paymentRequest({
  country: 'US',
  currency: 'usd',
  total: {
    label: 'Demo total',
    amount: 1000,
  },
  requestPayerName: true,
  requestPayerEmail: true,
});

const prButton = elements.create('paymentRequestButton', {
  paymentRequest: paymentRequest,
});

// Check availability
paymentRequest.canMakePayment().then(result => {
  if (result) {
    prButton.mount('#payment-request-button');
  }
});

// Handle token
paymentRequest.on('token', async (ev) => {
  const response = await fetch('/api/charge', {
    method: 'POST',
    body: JSON.stringify({ token: ev.token.id })
  });

  if (response.ok) {
    ev.complete('success');
  } else {
    ev.complete('fail');
  }
});
```

### 4. Server-Side API Integration

**How it works**: Your server communicates directly with gateway API.

**Pros**:
- Full control over flow
- Server-side processing
- Can implement complex business logic

**Cons**:
- Higher PCI compliance if handling raw card data
- More development effort
- Security responsibility

**Best for**: Backend payment processing, subscriptions, marketplace payouts

```javascript
// Example: Server-side charge with Stripe
const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);

app.post('/api/charge', async (req, res) => {
  try {
    const {token, amount, currency, description} = req.body;

    // Create charge
    const charge = await stripe.charges.create({
      amount: amount,
      currency: currency || 'usd',
      description: description,
      source: token,
      metadata: {
        order_id: req.body.orderId
      }
    });

    // Save to database
    await saveTransaction({
      chargeId: charge.id,
      amount: charge.amount,
      status: charge.status,
      userId: req.user.id
    });

    res.json({ success: true, chargeId: charge.id });
  } catch (error) {
    console.error('Payment failed:', error);
    res.status(400).json({ error: error.message });
  }
});
```

---

## International Payment Considerations

### Multi-Currency Support

#### Strategy 1: Present Prices in Customer's Local Currency
```javascript
// Detect user's location and show appropriate currency
const currencies = {
  'US': 'USD',
  'GB': 'GBP',
  'EU': 'EUR',
  'JP': 'JPY',
  'IN': 'INR'
};

const userCurrency = currencies[userCountry] || 'USD';
const localizedPrice = convertCurrency(basePrice, 'USD', userCurrency);
```

**Pros**:
- Better user experience
- Increases conversion rates
- Reduces confusion

**Cons**:
- Need to manage exchange rates
- Potential for rate fluctuation losses
- More complex accounting

#### Strategy 2: Multi-Currency Settlement
- Accept payments in multiple currencies
- Settle in your preferred currency or local currency
- Gateway handles conversion

```javascript
// Stripe: Charge in customer's currency
const charge = await stripe.charges.create({
  amount: 1000,
  currency: 'eur', // Charge in EUR
  source: token,
});
```

### Local Payment Methods

Different regions prefer different payment methods:

**Europe**:
- iDEAL (Netherlands)
- SEPA Direct Debit
- SOFORT (Germany, Austria)
- Bancontact (Belgium)
- Giropay (Germany)

**Asia-Pacific**:
- Alipay (China)
- WeChat Pay (China)
- UPI (India)
- GrabPay (Southeast Asia)
- PayNow (Singapore)

**Latin America**:
- Boleto (Brazil)
- OXXO (Mexico)
- Mercado Pago

**Implementation**:
```javascript
// Stripe: Create payment with local method
const paymentIntent = await stripe.paymentIntents.create({
  amount: 1000,
  currency: 'eur',
  payment_method_types: ['card', 'ideal', 'sepa_debit'],
});
```

### Tax and Regulatory Compliance

1. **VAT/GST**: Calculate and collect appropriate taxes
2. **Financial Regulations**: Comply with local financial laws
3. **Consumer Protection**: Honor refund and chargeback rights
4. **Data Privacy**: GDPR (EU), CCPA (California), LGPD (Brazil)
5. **Strong Customer Authentication**: PSD2 compliance for EU payments
6. **Cross-Border Fees**: Disclose all fees transparently

```javascript
// Example: Calculate VAT for EU customers
const calculateTotal = (basePrice, country) => {
  const vatRates = {
    'DE': 0.19, // Germany
    'FR': 0.20, // France
    'GB': 0.20, // UK
    // ... more countries
  };

  const vatRate = vatRates[country] || 0;
  const vatAmount = basePrice * vatRate;
  const total = basePrice + vatAmount;

  return { basePrice, vatAmount, vatRate, total };
};
```

---

## Technical Implementation

### Backend Architecture

```javascript
// Recommended structure
/api
  /payments
    /create          // Create payment intent/session
    /confirm         // Confirm payment
    /cancel          // Cancel payment
    /refund          // Process refund
  /webhooks
    /stripe          // Handle Stripe webhooks
    /paypal          // Handle PayPal webhooks
  /subscriptions
    /create          // Create subscription
    /update          // Update subscription
    /cancel          // Cancel subscription
```

### Database Schema

```sql
-- Transactions table
CREATE TABLE transactions (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  gateway VARCHAR(50) NOT NULL, -- 'stripe', 'paypal', etc.
  gateway_transaction_id VARCHAR(255) UNIQUE,
  amount DECIMAL(10,2) NOT NULL,
  currency VARCHAR(3) NOT NULL,
  status VARCHAR(50) NOT NULL, -- 'pending', 'succeeded', 'failed', 'refunded'
  payment_method VARCHAR(50), -- 'card', 'paypal', 'ideal', etc.
  description TEXT,
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Refunds table
CREATE TABLE refunds (
  id UUID PRIMARY KEY,
  transaction_id UUID REFERENCES transactions(id),
  gateway_refund_id VARCHAR(255) UNIQUE,
  amount DECIMAL(10,2) NOT NULL,
  reason TEXT,
  status VARCHAR(50) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Subscriptions table
CREATE TABLE subscriptions (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  gateway VARCHAR(50) NOT NULL,
  gateway_subscription_id VARCHAR(255) UNIQUE,
  plan_id VARCHAR(100),
  status VARCHAR(50) NOT NULL, -- 'active', 'canceled', 'past_due', etc.
  current_period_start TIMESTAMP,
  current_period_end TIMESTAMP,
  cancel_at_period_end BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
```

### Idempotency

Prevent duplicate charges by implementing idempotency:

```javascript
// Client generates unique key for each payment attempt
const idempotencyKey = generateUUID(); // or use order ID

// Server-side: Check if request was already processed
app.post('/api/charge', async (req, res) => {
  const { token, amount, idempotencyKey } = req.body;

  // Check if we've already processed this request
  const existingCharge = await db.transactions.findOne({
    where: { idempotency_key: idempotencyKey }
  });

  if (existingCharge) {
    return res.json({ success: true, charge: existingCharge });
  }

  // Process new charge
  const charge = await stripe.charges.create({
    amount,
    source: token,
    currency: 'usd'
  }, {
    idempotencyKey: idempotencyKey // Stripe also supports this
  });

  // Save to database
  await db.transactions.create({
    idempotency_key: idempotencyKey,
    gateway_transaction_id: charge.id,
    amount: charge.amount,
    status: charge.status
  });

  res.json({ success: true, charge });
});
```

### Webhook Handling

Webhooks notify your server about payment events asynchronously:

```javascript
// Stripe webhook handler
app.post('/api/webhooks/stripe',
  express.raw({type: 'application/json'}), // Important: raw body for signature verification
  async (req, res) => {
    const sig = req.headers['stripe-signature'];
    let event;

    try {
      // Verify webhook signature
      event = stripe.webhooks.constructEvent(
        req.body,
        sig,
        process.env.STRIPE_WEBHOOK_SECRET
      );
    } catch (err) {
      console.error('Webhook signature verification failed:', err.message);
      return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    // Handle different event types
    switch (event.type) {
      case 'payment_intent.succeeded':
        const paymentIntent = event.data.object;
        await handleSuccessfulPayment(paymentIntent);
        break;

      case 'payment_intent.payment_failed':
        const failedPayment = event.data.object;
        await handleFailedPayment(failedPayment);
        break;

      case 'customer.subscription.deleted':
        const subscription = event.data.object;
        await handleSubscriptionCanceled(subscription);
        break;

      case 'charge.refunded':
        const refund = event.data.object;
        await handleRefund(refund);
        break;

      default:
        console.log(`Unhandled event type: ${event.type}`);
    }

    // Return 200 to acknowledge receipt
    res.json({received: true});
});

// Webhook handlers
async function handleSuccessfulPayment(paymentIntent) {
  await db.transactions.update({
    where: { gateway_transaction_id: paymentIntent.id },
    data: { status: 'succeeded' }
  });

  // Send confirmation email
  await sendPaymentConfirmation(paymentIntent);

  // Fulfill order
  await fulfillOrder(paymentIntent.metadata.order_id);
}
```

### Environment Configuration

```bash
# .env file
# Never commit this file to version control

# Gateway API Keys
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...

# Application
NODE_ENV=production
API_URL=https://api.yoursite.com
FRONTEND_URL=https://yoursite.com

# Database
DATABASE_URL=postgresql://...

# Security
ENCRYPTION_KEY=...
JWT_SECRET=...
```

---

## Error Handling & Resilience

### Common Payment Errors

1. **Card Declined**: Insufficient funds, expired card, bank rejection
2. **Authentication Failed**: 3D Secure failure, incorrect CVV
3. **Network Issues**: Timeout, connection error
4. **Invalid Data**: Incorrect card number, invalid expiry
5. **Gateway Errors**: Service temporarily unavailable

### Error Handling Strategy

```javascript
// Client-side error display
const handlePaymentError = (error) => {
  const errorMessages = {
    'card_declined': 'Your card was declined. Please try another card.',
    'expired_card': 'Your card has expired. Please use a different card.',
    'insufficient_funds': 'Insufficient funds. Please try another payment method.',
    'incorrect_cvc': 'The security code is incorrect. Please try again.',
    'processing_error': 'An error occurred processing your card. Please try again.',
    'rate_limit': 'Too many requests. Please wait a moment and try again.',
  };

  const message = errorMessages[error.code] || 'Payment failed. Please try again.';
  displayError(message);

  // Log for debugging
  console.error('Payment error:', error);

  // Track in analytics
  analytics.track('payment_error', {
    error_code: error.code,
    error_message: error.message
  });
};

// Server-side error handling with retry logic
const processPaymentWithRetry = async (paymentData, maxRetries = 3) => {
  let lastError;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const charge = await stripe.charges.create(paymentData);
      return { success: true, charge };

    } catch (error) {
      lastError = error;

      // Don't retry on certain errors
      const noRetryErrors = [
        'card_declined',
        'expired_card',
        'incorrect_cvc',
        'invalid_number'
      ];

      if (noRetryErrors.includes(error.code)) {
        break; // Exit retry loop
      }

      // Exponential backoff for network errors
      if (attempt < maxRetries) {
        const delay = Math.pow(2, attempt) * 1000; // 2s, 4s, 8s
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  return { success: false, error: lastError };
};
```

### Graceful Degradation

```javascript
// Fallback payment methods
const PaymentForm = () => {
  const [primaryMethodAvailable, setPrimaryMethodAvailable] = useState(true);

  return (
    <div>
      {primaryMethodAvailable ? (
        <StripePaymentForm onError={() => setPrimaryMethodAvailable(false)} />
      ) : (
        <div>
          <p>Having trouble? Try these alternatives:</p>
          <PayPalButton />
          <BankTransferOption />
          <ContactSupport />
        </div>
      )}
    </div>
  );
};
```

### Monitoring and Alerting

```javascript
// Track payment success rates
const trackPaymentMetrics = async (transaction) => {
  await metrics.increment('payments.attempted');

  if (transaction.status === 'succeeded') {
    await metrics.increment('payments.succeeded');
  } else {
    await metrics.increment('payments.failed');

    // Alert if failure rate exceeds threshold
    const failureRate = await calculateFailureRate();
    if (failureRate > 0.05) { // 5%
      await sendAlert('High payment failure rate', { failureRate });
    }
  }
};
```

---

## Testing Strategy

### Test Environments

1. **Development**: Use sandbox/test mode
2. **Staging**: Mirror production setup with test credentials
3. **Production**: Real transactions with real money

### Test Card Numbers

```javascript
// Stripe test cards
const testCards = {
  success: '4242424242424242',
  decline: '4000000000000002',
  insufficientFunds: '4000000000009995',
  expired: '4000000000000069',
  processing: '4000000000000259',
  authentication: '4000002760003184', // Requires 3D Secure
};

// Test in different currencies
const testInternational = {
  gbp: '4000008260003184', // UK card requiring 3DS
  eur: '4000002500003155', // French card
  cad: '4000001240000000', // Canadian card
};
```

### Testing Checklist

#### Functional Testing
- [ ] Successful payment flow
- [ ] Declined card handling
- [ ] Expired card handling
- [ ] Insufficient funds
- [ ] Network timeout simulation
- [ ] 3D Secure authentication
- [ ] Multiple currency processing
- [ ] Refund processing
- [ ] Subscription creation/cancellation
- [ ] Webhook delivery and processing
- [ ] Idempotency (duplicate request handling)

#### Security Testing
- [ ] SSL/TLS certificate validation
- [ ] Webhook signature verification
- [ ] XSS protection on payment forms
- [ ] CSRF token validation
- [ ] Rate limiting on payment endpoints
- [ ] SQL injection prevention
- [ ] Sensitive data not logged
- [ ] Proper access controls

#### Performance Testing
- [ ] Load testing payment endpoints
- [ ] Concurrent payment handling
- [ ] Webhook processing under load
- [ ] Database query performance
- [ ] API response times

#### Integration Testing
```javascript
// Example: Automated payment test
describe('Payment Processing', () => {
  it('should process successful payment', async () => {
    const token = await createTestToken('4242424242424242');

    const response = await request(app)
      .post('/api/charge')
      .send({
        token: token.id,
        amount: 1000,
        currency: 'usd'
      })
      .expect(200);

    expect(response.body.success).toBe(true);
    expect(response.body.charge).toBeDefined();

    // Verify database record
    const transaction = await db.transactions.findOne({
      where: { gateway_transaction_id: response.body.charge.id }
    });
    expect(transaction.status).toBe('succeeded');
  });

  it('should handle declined card', async () => {
    const token = await createTestToken('4000000000000002');

    const response = await request(app)
      .post('/api/charge')
      .send({ token: token.id, amount: 1000 })
      .expect(400);

    expect(response.body.error).toBeDefined();
  });
});
```

### Testing Webhooks Locally

```bash
# Use gateway's CLI tool to forward webhooks to local dev
# Stripe example:
stripe listen --forward-to localhost:3000/api/webhooks/stripe

# Trigger test events
stripe trigger payment_intent.succeeded
stripe trigger charge.refunded
```

---

## Compliance & Legal

### PCI DSS Compliance Levels

**SAQ A** (Simplest - Recommended)
- Use hosted payment pages or tokenization
- No card data touches your servers
- ~20 questions to answer
- Annual self-assessment

**SAQ A-EP**
- Use iframes or JavaScript SDKs
- Card data passes through your site but not your servers
- ~150 questions
- May require quarterly network scans

**SAQ D** (Most Complex - Avoid)
- Your servers handle raw card data
- Full PCI DSS compliance
- ~300 requirements
- Annual audit required for large volumes
- Network segmentation, encryption, access controls, etc.

### Strong Customer Authentication (SCA)

Required for payments in the European Economic Area (PSD2 regulation):

```javascript
// Implement 3D Secure 2.0
const paymentIntent = await stripe.paymentIntents.create({
  amount: 1000,
  currency: 'eur',
  payment_method_types: ['card'],
  // These fields help reduce friction by providing context
  payment_method_options: {
    card: {
      request_three_d_secure: 'automatic'
    }
  },
  metadata: {
    order_id: '12345'
  }
});

// Handle authentication on client
const {error} = await stripe.confirmCardPayment(
  clientSecret,
  {
    payment_method: {card: cardElement}
  }
);
```

### GDPR Compliance

1. **Data Minimization**: Only collect necessary payment data
2. **Right to Access**: Allow users to download their payment history
3. **Right to Deletion**: Implement account/data deletion
4. **Data Portability**: Export user data in machine-readable format
5. **Consent**: Get explicit consent for storing payment methods

```javascript
// GDPR-compliant data export
app.get('/api/user/data-export', authenticate, async (req, res) => {
  const userData = {
    profile: await getUserProfile(req.user.id),
    transactions: await getTransactions(req.user.id),
    subscriptions: await getSubscriptions(req.user.id),
  };

  // Redact sensitive information
  userData.transactions = userData.transactions.map(t => ({
    ...t,
    card_last4: t.card_last4, // OK to include
    card_full: undefined, // Never export full card numbers
  }));

  res.json(userData);
});

// Account deletion
app.delete('/api/user/account', authenticate, async (req, res) => {
  // Cancel active subscriptions
  await cancelAllSubscriptions(req.user.id);

  // Delete user data
  await deleteUser(req.user.id);

  // Note: Transaction records may need to be retained for tax/legal purposes
  // Instead of deleting, anonymize them
  await anonymizeTransactions(req.user.id);

  res.json({ success: true });
});
```

### Terms and Conditions

Your payment flow should include:
1. Clear pricing display
2. Terms of service acceptance
3. Refund policy
4. Privacy policy
5. Contact information for disputes
6. Currency and any conversion fees

---

## User Experience Best Practices

### Checkout Flow Optimization

#### 1. Minimize Steps
```javascript
// Bad: Multiple pages
Page 1: Cart → Page 2: Shipping → Page 3: Payment → Page 4: Review → Page 5: Confirm

// Good: Single page or fewer steps
Single Page: Cart + Shipping + Payment
```

#### 2. Guest Checkout
Allow purchases without account creation:
```javascript
<form>
  <input type="email" placeholder="Email for receipt" required />
  <p>
    <input type="checkbox" id="create-account" />
    <label htmlFor="create-account">Create an account (optional)</label>
  </p>
  <!-- Payment fields -->
</form>
```

#### 3. Express Checkout Buttons
Place Apple Pay, Google Pay buttons prominently:
```javascript
<div className="payment-options">
  <div className="express-checkout">
    <ApplePayButton />
    <GooglePayButton />
    <PayPalButton />
  </div>
  <div className="divider">or pay with card</div>
  <CardForm />
</div>
```

#### 4. Address Autocomplete
```javascript
// Use Google Places API or similar
<input
  type="text"
  id="address"
  autoComplete="street-address"
  placeholder="Start typing your address..."
/>
```

#### 5. Real-Time Validation
```javascript
const CardInput = () => {
  const [errors, setErrors] = useState({});

  const validateCard = (number) => {
    // Luhn algorithm for card validation
    if (!isValidCardNumber(number)) {
      setErrors({card: 'Invalid card number'});
    } else {
      setErrors({card: null});
    }
  };

  return (
    <div>
      <input
        type="text"
        onChange={(e) => validateCard(e.target.value)}
        onBlur={(e) => validateCard(e.target.value)}
      />
      {errors.card && <span className="error">{errors.card}</span>}
    </div>
  );
};
```

### Payment Status Communication

```javascript
// Clear status indicators
const PaymentStatus = ({status, amount, currency}) => {
  const statusConfig = {
    processing: {
      icon: '⏳',
      title: 'Processing Payment',
      message: 'Please wait while we process your payment...',
      color: 'blue'
    },
    succeeded: {
      icon: '✓',
      title: 'Payment Successful',
      message: `Your payment of ${formatMoney(amount, currency)} was successful.`,
      color: 'green'
    },
    failed: {
      icon: '✗',
      title: 'Payment Failed',
      message: 'There was an issue processing your payment. Please try again.',
      color: 'red'
    }
  };

  const config = statusConfig[status];

  return (
    <div className={`status-${config.color}`}>
      <div className="icon">{config.icon}</div>
      <h2>{config.title}</h2>
      <p>{config.message}</p>
    </div>
  );
};
```

### Mobile Optimization

1. **Large Touch Targets**: Minimum 44x44px buttons
2. **Auto-Focus**: Focus first input field on load
3. **Numeric Keyboards**: Use `type="tel"` for card numbers
4. **Autofill Support**: Use proper `autocomplete` attributes

```html
<!-- Proper autocomplete attributes -->
<input type="text" autocomplete="cc-number" placeholder="Card number" />
<input type="text" autocomplete="cc-name" placeholder="Name on card" />
<input type="text" autocomplete="cc-exp" placeholder="MM/YY" />
<input type="text" autocomplete="cc-csc" placeholder="CVV" />
```

### Transparency and Trust

1. **Security Badges**: Display SSL, PCI DSS badges
2. **Price Breakdown**: Show itemized costs
3. **No Hidden Fees**: Display all fees upfront
4. **Save Payment Info**: Offer to save cards securely
5. **Money-Back Guarantee**: Display refund policy clearly

```javascript
// Price breakdown example
<div className="price-breakdown">
  <div className="line-item">
    <span>Subtotal</span>
    <span>$100.00</span>
  </div>
  <div className="line-item">
    <span>Shipping</span>
    <span>$5.00</span>
  </div>
  <div className="line-item">
    <span>Tax</span>
    <span>$8.40</span>
  </div>
  <div className="line-item total">
    <span><strong>Total</strong></span>
    <span><strong>$113.40 USD</strong></span>
  </div>
  <div className="security-note">
    🔒 Secure payment processed by Stripe
  </div>
</div>
```

---

## Conclusion

### Quick Start Checklist

- [ ] Choose a payment gateway based on your needs
- [ ] Sign up and get API keys (test and live)
- [ ] Decide on integration approach (recommend: embedded SDK with tokenization)
- [ ] Set up HTTPS/SSL on your domain
- [ ] Implement payment form with proper security
- [ ] Create backend endpoints for payment processing
- [ ] Set up webhook handlers
- [ ] Implement error handling and user feedback
- [ ] Test thoroughly with test cards
- [ ] Ensure PCI DSS compliance (SAQ-A recommended)
- [ ] Review legal requirements (GDPR, PSD2, etc.)
- [ ] Set up monitoring and alerting
- [ ] Document your integration for your team
- [ ] Go live with small transactions first
- [ ] Monitor and optimize based on real data

### Recommended Tech Stack

**For most web applications**:
- **Gateway**: Stripe (best developer experience) or Adyen (enterprise)
- **Approach**: Embedded SDK with tokenization (Stripe Elements)
- **Additional**: Payment Request API for Apple/Google Pay
- **Backend**: Server-side API integration for charge creation
- **Webhooks**: Asynchronous event handling
- **Compliance**: SAQ-A level (minimal burden)

### Resources

- **Stripe Docs**: https://stripe.com/docs
- **PayPal Developer**: https://developer.paypal.com
- **Adyen Docs**: https://docs.adyen.com
- **PCI DSS**: https://www.pcisecuritystandards.org
- **PSD2/SCA**: https://stripe.com/guides/strong-customer-authentication

### Common Mistakes to Avoid

1. ❌ Storing raw card data on your servers
2. ❌ Not implementing webhook handlers
3. ❌ Ignoring failed payment states
4. ❌ Not testing edge cases (declined cards, network issues)
5. ❌ Poor error messages for users
6. ❌ Not implementing idempotency
7. ❌ Forgetting to verify webhook signatures
8. ❌ Not supporting local payment methods for international users
9. ❌ Inadequate logging and monitoring
10. ❌ Not handling subscription edge cases (past due, canceled)

---

**Document Version**: 1.0
**Last Updated**: December 2025
**Maintained By**: Development Team
