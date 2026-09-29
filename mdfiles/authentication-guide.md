# JWT Token & Cookie-Based Authentication

## Overview

Authentication in modern web applications typically uses either **JWT tokens** or **session cookies** (or a combination) to maintain user identity across requests.

## Cookie-Based (Session) Authentication

### How It Works

1. **User Login**: Client sends credentials (username/password)
2. **Server Validation**: Server validates credentials
3. **Session Creation**: Server creates a session, stores it in memory/database with a unique session ID
4. **Cookie Response**: Server sends session ID back as an HTTP-only cookie
5. **Subsequent Requests**: Browser automatically includes cookie in every request
6. **Session Lookup**: Server looks up session ID to retrieve user data
7. **Logout**: Server destroys session, client clears cookie

### Example Flow

```
Client                          Server                    Database
  |                               |                           |
  |-- POST /login --------------->|                           |
  |   {user, pass}                |                           |
  |                               |-- Validate credentials -->|
  |                               |<-- User data -------------|
  |                               |                           |
  |                               |-- Store session --------->|
  |                               |   {sessionId: "abc123",   |
  |                               |    userId: 42}            |
  |                               |                           |
  |<-- Set-Cookie: sessionId -----|                           |
  |    HttpOnly, Secure           |                           |
  |                               |                           |
  |-- GET /profile -------------->|                           |
  |   Cookie: sessionId=abc123    |                           |
  |                               |-- Lookup session -------->|
  |                               |<-- User data -------------|
  |<-- User profile data ---------|                           |
```

### Pros & Cons

**Pros:**
- Server has full control (can invalidate sessions immediately)
- No sensitive data exposed to client
- Works well for traditional web apps

**Cons:**
- Requires server-side storage
- Harder to scale horizontally
- CSRF vulnerability (requires CSRF tokens)

---

## JWT (JSON Web Token) Authentication

### How It Works

1. **User Login**: Client sends credentials
2. **Server Validation**: Server validates credentials
3. **JWT Creation**: Server generates a signed JWT containing user claims
4. **Token Response**: Server sends JWT to client
5. **Client Storage**: Client stores JWT (localStorage, sessionStorage, or cookie)
6. **Subsequent Requests**: Client includes JWT in Authorization header
7. **Token Verification**: Server verifies JWT signature and extracts claims
8. **Logout**: Client deletes token (server can use blacklist/expiration)

### JWT Structure

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c

Header:        {"alg": "HS256", "typ": "JWT"}
Payload:       {"sub": "1234567890", "name": "John Doe", "iat": 1516239022}
Signature:     HMACSHA256(base64(header) + "." + base64(payload), secret)
```

### Example Flow

```
Client                          Server
  |                               |
  |-- POST /login --------------->|
  |   {user, pass}                |
  |                               |-- Validate credentials
  |                               |
  |                               |-- Generate JWT --------
  |                               |   {userId: 42,
  |                               |    role: "admin",
  |                               |    exp: 1234567890}
  |                               |
  |<-- {token: "eyJ..."}----------|
  |                               |
  |   Store token locally         |
  |                               |
  |-- GET /profile -------------->|
  |   Authorization: Bearer eyJ...|
  |                               |-- Verify signature ----
  |                               |-- Extract claims ------
  |<-- User profile data ---------|
```

### Pros & Cons

**Pros:**
- Stateless (no server-side storage needed)
- Scalable (works across multiple servers)
- Works well for APIs and microservices
- Mobile-friendly

**Cons:**
- Cannot invalidate before expiration (unless using blacklist)
- Token size larger than session ID
- Exposed to XSS if stored in localStorage

---

## Hybrid Approach: JWT in HttpOnly Cookies

Many modern applications use **JWT stored in HttpOnly cookies** to get the best of both worlds.

### Example Flow

```javascript
// Server-side (Node.js/Express)
app.post('/login', async (req, res) => {
  const { username, password } = req.body;

  // Validate user
  const user = await validateUser(username, password);

  // Generate JWT
  const token = jwt.sign(
    { userId: user.id, role: user.role },
    process.env.JWT_SECRET,
    { expiresIn: '7d' }
  );

  // Send as HttpOnly cookie
  res.cookie('token', token, {
    httpOnly: true,    // Prevents JavaScript access
    secure: true,      // HTTPS only
    sameSite: 'strict', // CSRF protection
    maxAge: 7 * 24 * 60 * 60 * 1000 // 7 days
  });

  res.json({ success: true });
});

// Middleware to verify JWT
const authMiddleware = (req, res, next) => {
  const token = req.cookies.token;

  if (!token) {
    return res.status(401).json({ error: 'Not authenticated' });
  }

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = decoded;
    next();
  } catch (err) {
    res.status(401).json({ error: 'Invalid token' });
  }
};
```

```javascript
// Client-side
// Login
await fetch('/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password }),
  credentials: 'include' // Important for cookies
});

// Authenticated request
const response = await fetch('/profile', {
  credentials: 'include' // Browser automatically sends cookie
});
```

---

## Security Best Practices

### For Cookies
- Always use `HttpOnly` flag (prevents XSS)
- Always use `Secure` flag in production (HTTPS only)
- Use `SameSite=Strict` or `Lax` (CSRF protection)
- Implement CSRF tokens for state-changing operations

### For JWTs
- Use short expiration times (15min - 1hr for access tokens)
- Implement refresh tokens for longer sessions
- Store in HttpOnly cookies (not localStorage) when possible
- Always verify signature on the server
- Use strong secrets (256-bit minimum)

### General
- Always use HTTPS in production
- Implement rate limiting on login endpoints
- Hash passwords with bcrypt/argon2
- Consider 2FA for sensitive applications
- Log authentication events

---

## Real-World Examples

### Google/Facebook
- Uses session cookies for web apps
- OAuth tokens for API access
- Refresh tokens for long-lived access

### GitHub
- JWT for API authentication
- Session cookies for web interface
- Personal access tokens for CLI/automation

### Stripe
- API keys (similar to JWT) for server-to-server
- Session cookies for dashboard
- Webhook signatures for callbacks

---

## Choosing Between Them

**Use Cookie-Based Sessions when:**
- Building traditional server-rendered web apps
- Need immediate session invalidation
- Session data is complex or frequently updated

**Use JWT when:**
- Building APIs or microservices
- Need stateless authentication
- Building mobile apps or SPAs
- Need cross-domain authentication

**Use Hybrid (JWT in HttpOnly cookies) when:**
- Building modern web apps
- Want security of cookies with stateless benefits
- Need both web and API access
