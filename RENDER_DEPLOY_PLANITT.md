# Render Deployment Guide — Planitt

This guide focuses on deploying only the **NestJS backend** (MongoDB + unified API for signals/news/market/jobs) while keeping the **AI stack (Ollama + FastAPI worker)** local/private.

## 1) Deploy MongoDB Atlas
1. Create a MongoDB Atlas cluster.
2. Create a database user with read/write permissions for the `planitt` database.
3. Get your connection string (e.g. `mongodb+srv://planitt:123@planitt.mongodb.net/`).

## 2) Deploy `planitt-backend` on Render (public)
Create a **Web Service** for the NestJS backend.

### Required environment variables
- `NODE_ENV=production`
- `PORT=3000`
- `MONGODB_URI=<your-atlas-connection-string>`
- `JWT_SECRET=<generate-a-strong-secret>`
- `PLANITT_INTERNAL_API_KEY=<shared-internal-api-key>`
- `CORS_ORIGINS=<comma-separated web/app origins>`

## 2.1) Deploy `planitt-admin` on Netlify (public, single-backend mode)
The admin app does not call Render directly from the browser. It uses server-side Next.js route handlers and proxies to NestJS only.

### Required Netlify environment variables

- `NEST_API_INTERNAL_API_KEY=<same-as-PLANITT_INTERNAL_API_KEY>`
- `ADMIN_DEPLOYMENT_MODE=single_backend`
- `NEST_API_BASE_URL=https://planitt-backend-crypto.onrender.com`
- `NEXTAUTH_SECRET=<strong-random-secret>`
- `ADMIN_USERNAME=<admin-user>`
- `ADMIN_PASSWORD=<admin-password>`

If `NEST_API_INTERNAL_API_KEY` is omitted, admin routes fall back to JWT mode and require `NEST_API_JWT`.

### CORS
Backend CORS is configured via `CORS_ORIGINS` (comma-separated). In production, set this explicitly (for example your Netlify domain and local admin origin).

## 3) FastAPI runtime: local worker only
Use FastAPI only as a local/private compute worker. Do not run FastAPI as a public Render service.

### Local scanner required environment variables
- `ENABLE_POSTGRES_DB_INIT=false`
- `ENABLE_BACKGROUND_SCANNER=true`
- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://ollama:11434` (when using Docker networking)
- `OLLAMA_MODEL=mistral` (or your chosen model)
- `PLANITT_BACKEND_BASE_URL=<your-backend-origin>`
- `PLANITT_BACKEND_INTERNAL_API_KEY=<same-as-planitt-backend>`
- `PLANITT_PROCESSOR_INTERNAL_API_KEY=<any-internal-key>`
- `PLANITT_MIN_CONFIDENCE=70`
- `ENABLE_BACKGROUND_SCANNER=true`

### Keep strategy internals private (important)
Do not expose local scanner/Ollama publicly. Keep generation local or in a private network only.

## 4) Internal API call flow (single backend API)
1. Admin enqueues a generation task:
   - `POST /generation-jobs`
2. Local FastAPI worker claims a task:
   - `GET /internal/generation-jobs/next`
3. Worker computes locally and forwards results:
   - `POST /signals`
   - `POST /internal/news`
   - `POST /internal/market-status`
   - `POST /internal/generation-jobs/:id/complete` (or `/fail`)
4. Web/app/admin read from one public API base URL:
   - `GET /signals`, `GET /news`, `GET /market-status`, `GET /generation-jobs`
5. Internal endpoints use:
   - Header: `x-api-key: <PLANITT_INTERNAL_API_KEY>`

Note on naming:
- `NEST_API_BASE_URL`: used by Netlify admin server routes.
- `PLANITT_BACKEND_BASE_URL`: used by local worker when polling/forwarding to Nest backend.

## 5) Notes / gaps
- Keep `JWT_SECRET` set even if current reads use API key mode, so future auth extensions remain safe.
- “Hit TP/Hit SL” status transitions require execution/price monitoring logic not included yet.

