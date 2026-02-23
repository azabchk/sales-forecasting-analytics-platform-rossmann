# Domain + DNS Setup (Cloudflare)

This guide assumes:

- Company apex: `yourcompany.com`
- Frontend: `app.yourcompany.com`
- Backend API: `api.yourcompany.com`
- Optional staging: `stg-app.yourcompany.com`, `stg-api.yourcompany.com`

## 1) Move Domain to Cloudflare

1. Buy domain (any registrar) or transfer to Cloudflare Registrar.
2. In Cloudflare dashboard, add the domain.
3. Update nameservers at registrar to Cloudflare nameservers.
4. Wait until Cloudflare status is **Active**.

## 2) DNS Records for Frontend (Vercel)

In Cloudflare DNS:

- Type: `CNAME`
- Name: `app`
- Target: value provided by Vercel (usually `cname.vercel-dns.com`)
- Proxy status: **DNS only** during verification, then proxy as needed

For staging frontend:

- `CNAME stg-app -> <vercel-staging-target>`

## 3) DNS Records for Backend

### If backend is on Render

- Type: `CNAME`
- Name: `api`
- Target: `<your-render-service>.onrender.com`

### If backend is on Fly.io

- Type: `CNAME`
- Name: `api`
- Target: `<your-app>.fly.dev`

### If backend is on VPS

- Type: `A`
- Name: `api`
- IPv4: `<your_vps_public_ip>`

For staging backend, create equivalent `stg-api` records.

## 4) Enable HTTPS

- Vercel: automatic HTTPS once domain is connected.
- Render/Fly: automatic HTTPS for connected custom domain.
- VPS: configure Cloudflare Origin Certificate or Let's Encrypt.

## 5) Redirect Policy

- Enable HTTPS redirect on hosting platform (Vercel/Render/Fly).
- On VPS nginx, add HTTP->HTTPS redirect once certificates are configured.

## 6) Validate

```bash
nslookup app.yourcompany.com
nslookup api.yourcompany.com
curl -I https://app.yourcompany.com
curl -I https://api.yourcompany.com/api/v1/health
```
