# Deploy Frontend via Vercel Git Import (Monorepo)

This guide is for importing this repository directly in Vercel and deploying the frontend from `frontend/`.

## 1) Import Repository

1. Open Vercel dashboard.
2. Click **Add New -> Project**.
3. Choose **Import Git Repository** and select this repo.
4. Set **Root Directory** to `frontend`.

## 2) Build Settings

Use these exact settings:

- Install Command: `npm ci`
- Build Command: `npm run build`
- Output Directory: `dist`

## 3) Environment Variables

In Project Settings -> Environment Variables, add:

- `VITE_API_BASE_URL=https://api.<domain-or-backend-url>/api/v1`

Example:

- `VITE_API_BASE_URL=https://api.yourcompany.com/api/v1`

## 4) Deploy

1. Click **Deploy**.
2. Wait for build and deployment to finish.

## 5) Verification Checklist

- Open deployed root URL `/` and confirm dashboard loads.
- Open a deep route directly, for example `/contracts`.
- Refresh that deep route and confirm it does **not** return 404.
- If deep-route refresh 404 appears, verify `frontend/vercel.json` contains SPA rewrite:
  - `/(.*)` -> `/index.html`
