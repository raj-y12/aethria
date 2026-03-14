# Clerk React Router: Token verification (docs summary)

Summary of [Verifying OAuth access tokens](https://clerk.com/docs/react-router/guides/development/verifying-oauth-access-tokens) and related React Router auth docs, and how they apply to this repo.

---

## 1. Verifying OAuth access tokens (the guide you linked)

**Purpose:** Let your **server-side** code accept and verify **OAuth access tokens** (machine tokens) issued by Clerk, in addition to normal session tokens.

**Where it runs:** In **React Router server loaders/actions** (e.g. Remix-style or React Router v7 with server). It does **not** run in the browser.

**Main API:** `getAuth()` from `@clerk/react-router/server` with the `acceptsToken` option:

- **`acceptsToken: 'oauth_token'`** – Only OAuth (machine) tokens. Good for API routes that serve machine clients. If invalid/missing, you get `null` and typically return **401**.
- **`acceptsToken: 'any'`** – Accept either session tokens or OAuth tokens. You can branch on `tokenType` (`'session_token'` vs machine token type).
- **Default** (no `acceptsToken`) – Behaves like session-only; OAuth tokens are not accepted.

**Example (accept only OAuth token):**

```tsx
import { getAuth } from '@clerk/react-router/server'

export async function loader(args: Route.LoaderArgs) {
  const { subject, scopes } = await getAuth(args, { acceptsToken: 'oauth_token' })

  if (!subject) {
    throw new Response('OAuth access token is invalid', { status: 401 })
  }

  return { subject, scopes }
}
```

**Example (accept any token, then branch):**

```tsx
const { tokenType } = await getAuth(args, { acceptsToken: 'any' })

if (tokenType === 'session_token') {
  // request from a user session
} else {
  // machine token (e.g. oauth_token)
}
```

**Important:** OAuth/machine tokens are a separate feature (and may have pricing after beta). This guide is only relevant if you are using **server-side loaders/actions** and need to accept **OAuth access tokens** there.

---

## 2. `getAuth()` reference

- **Import:** `import { getAuth } from '@clerk/react-router/server'`
- **Arguments:** `(args, options?)`
  - `args`: React Router **LoaderFunctionArgs** / **ActionArgs** (the request context).
  - `options.acceptsToken`: `'session_token'` | `'oauth_token'` | `'any'` (and possibly others; see Clerk’s “getAuth parameters” doc).
  - `options.treatPendingAsSignedOut`: whether to treat a pending session as signed out (default `true`).
- **Returns:** An **Auth** object (or null-ish when unauthenticated), e.g.:
  - `userId`, `sessionId`, `orgId`
  - `isAuthenticated`
  - For OAuth: `subject`, `scopes`, `tokenType`
  - `getToken()` for session/JWT
  - `has()` for permissions/roles

So the **entire doc** on “verifying OAuth access tokens” is: use `getAuth(args, { acceptsToken: 'oauth_token' })` (or `'any'`) in **server** loaders/actions and return 401 when the token is invalid.

---

## 3. Reading user data (server vs client)

**Server (loaders/actions):**

- Use **`getAuth(args)`** to get `isAuthenticated`, `userId`, etc.
- Protect routes: if `!isAuthenticated`, `redirect('/sign-in?redirect_url=' + request.url)`.
- For full user object: **`clerkClient(args).users.getUser(userId)`** (Backend API).

**Client (browser):**

- **`useAuth()`** – `isLoaded`, `isSignedIn`, `userId`, `sessionId`, **`getToken()`**.
- **`useUser()`** – `user`, `isSignedIn`, `isLoaded`.

Sending tokens to **your own backend** (e.g. FastAPI):

- In the client, call **`getToken()`** from `useAuth()` and send it in `Authorization: Bearer <token>` to your API.
- Your **Python backend** does **not** use `getAuth()` (that’s Node/React Router server only). It should verify the Clerk **JWT** using Clerk’s secret/key (see Clerk’s “Backend verification” / “Verify JWT” docs for your framework or generic JWT verification).

---

## 4. How this applies to this repo (Aethria)

- **Frontend:** Vite + React + **client-side** React Router + `@clerk/react-router`. There are **no server loaders/actions** (no Node server rendering or loaders).
- **Backend:** **Python FastAPI**. Auth is not handled by React Router or Clerk’s Node server helpers.

So:

- **Verifying OAuth access tokens** and **`getAuth()`** in the docs apply to **React Router server** (loaders/actions). They **do not** run in this repo’s frontend or in FastAPI.
- To protect **client-side** routes: keep using **`useAuth()`** / **`useUser()`** (as you do in `App.tsx` and `LoginPage.tsx`).
- To call your **FastAPI** backend with Clerk auth:
  - **Frontend:** Use **`getToken()`** from `useAuth()` and send it (e.g. `Authorization: Bearer <token>`).
  - **Backend:** Verify the Clerk-issued JWT in Python (Clerk’s “Verify JWT in your backend” or “Backend API” docs for Python/ FastAPI). Do **not** use `getAuth()` in Python; that’s a Node/React Router helper.

If you later add a **Node** (or Remix/React Router server) layer that has loaders/actions and need to accept **OAuth access tokens** from machines, then you’d use that guide and `getAuth(args, { acceptsToken: 'oauth_token' })` there.

---

## 5. Quick reference

| Need | Where | What to use |
|------|--------|-------------|
| Accept/verify **OAuth access tokens** in server code | React Router **server** loaders/actions | `getAuth(args, { acceptsToken: 'oauth_token' })` or `'any'`; return 401 if invalid. |
| Protect server routes / read user in loaders/actions | React Router **server** | `getAuth(args)`, then `redirect` if `!isAuthenticated`; optional `clerkClient(args).users.getUser(userId)`. |
| Protect client routes / show “signed in” UI | Browser | `useAuth()`, `useUser()` (as in this app). |
| Call your **own backend** with Clerk auth | Browser → FastAPI | Client: `getToken()` from `useAuth()`, send `Authorization: Bearer <token>`. Backend: verify Clerk JWT in Python (Clerk backend verification docs). |
