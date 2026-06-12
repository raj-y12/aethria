# Environment Variables

Do not commit secret values. Keep local values in `.env` files and configure production values in the relevant host.

## Backend

Required for production pipeline execution:

- `OPENAI_API_KEY`
- `USE_SUPABASE_STORAGE=1`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `CLERK_JWKS_URL`

Common optional backend variables:

- `CLERK_ISSUER`
- `CLERK_SECRET_KEY`
- `SCOUT_MODEL`
- `REVIEWER_MODEL`
- `PARTNER_USE_LLM`
- `META_AGENT_ENABLED`
- `META_AGENT_INTERVAL_SECONDS`
- `MAX_CONCURRENT_PIPELINE_CYCLES`
- `RESUME_AGENT_LOOPS_ON_STARTUP`
- `MAX_RESUMED_AGENT_LOOPS`
- `FUND_THESIS_RUNTIME_ALIGNMENT_ROW_LIMIT`
- `ALLOWED_ORIGINS`
- `AETHRIA_AGENT_USER_ID`

## App Frontend (`app-front-end`)

- `VITE_CLERK_PUBLISHABLE_KEY`
- `CLERK_PUBLISHABLE_KEY`
- `VITE_API_URL`

`VITE_API_URL` points the app to the backend API in local or hosted environments.

## Web Frontend (`web-front-end`)

- `VITE_API_URL`
- `VITE_APP_URL`
- `VITE_CLERK_PUBLISHABLE_KEY`
- `CLERK_PUBLISHABLE_KEY`
- `RESEND_API_KEY`
- `AETHRIA_WAITLIST_NOTIFY_EMAIL`

`RESEND_API_KEY` and `AETHRIA_WAITLIST_NOTIFY_EMAIL` are used by the Vercel serverless waitlist function in `web-front-end/api/waitlist.ts`.

## Local Examples

- `app-front-end/.env.example`
- `web-front-end/.env.example`

The root `.gitignore` keeps `.env` and `.env.*` files out of git while allowing `.env.example` files to remain tracked.
