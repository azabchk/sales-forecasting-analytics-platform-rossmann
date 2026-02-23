# Deploy Frontend on Vercel (Recommended)

This deploys the React/Vite frontend to `app.yourcompany.com`.

## 1) Create Vercel Project

1. In Vercel dashboard, click **Add New -> Project**.
2. Import this GitHub repository.
3. Set **Root Directory** to `frontend`.
4. Set build settings:
   - Framework Preset: `Vite`
   - Build Command: `npm run build`
   - Output Directory: `dist`
   - Install Command: `npm ci`

## 2) Set Environment Variables

In Vercel project settings -> Environment Variables:

- `VITE_API_BASE_URL=https://api.yourcompany.com/api/v1`

For staging project:

- `VITE_API_BASE_URL=https://stg-api.yourcompany.com/api/v1`

## 3) Domain Mapping

1. In Vercel project -> **Domains**, add:
   - `app.yourcompany.com` (production)
   - `stg-app.yourcompany.com` (staging project)
2. Follow Vercel DNS target instructions in `docs/DOMAIN-DNS.md`.

## 4) Verify

After deployment:

- App URL opens successfully.
- Browser network calls hit `https://api.yourcompany.com/api/v1/*`.
- Direct route refresh works (handled by `frontend/vercel.json`).

## 5) Rollback

- In Vercel deployments list, promote the previous successful deployment.
