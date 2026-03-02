# Private routes

Routes in this folder are exposed under **web-front-end** at `/<filename>` (filename lowercased, so `private-access.tsx` → `/private-access`).

- **`private-access.tsx`** → `/private-access`: app-front-end in an iframe (app’s EnterSystemPage login first, then main app).

To **remove access** to a private route, delete its file. The route is registered at build time via `import.meta.glob`; after the next build, that path will no longer exist and will redirect to `/`.

Optional env for the embedded app URL: `VITE_APP_URL` (defaults to `http://localhost:3000` in dev).
