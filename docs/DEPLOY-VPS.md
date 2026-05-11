# VPS Self-Host Deployment (Optional)

This is a full self-host path with Docker Compose using:

- FastAPI backend (gunicorn + uvicorn workers)
- React frontend served by nginx
- nginx reverse proxy
- managed external PostgreSQL (recommended)

## 1) Provision VPS

Recommended minimum:

- 2 vCPU
- 4 GB RAM
- 40 GB SSD
- Ubuntu 22.04 LTS

## 2) Install Docker + Compose

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Re-login after `usermod`.

## 3) Deploy Repository

```bash
git clone git@github.com:azabchk/sales-forecasting-analytics-platform-rossmann.git
cd sales-forecasting-analytics-platform-rossmann
git checkout v2.0.0
cp .env.production.example .env.production
```

Fill `.env.production` with real values (especially `DATABASE_URL`, `CORS_ORIGINS`, `VITE_API_BASE_URL`).

## 4) Validate Environment

```bash
ENV_FILE=.env.production BACKEND_PUBLIC_URL=https://api.yourcompany.com bash scripts/prod_env_check.sh
```

## 5) Start Production Stack

```bash
docker compose --env-file .env.production -f docker-compose.yml -f compose.production.yaml up -d --build --no-deps backend frontend reverse_proxy
```

## 6) Verify

```bash
docker compose --env-file .env.production -f docker-compose.yml -f compose.production.yaml ps
curl -fsS http://127.0.0.1/api/v1/health || curl -fsS http://127.0.0.1:8000/api/v1/health
```

## 7) TLS / HTTPS Strategy

Choose one:

### Option A: Cloudflare proxy in front of VPS

- Keep nginx origin on port 80.
- Proxy DNS through Cloudflare (orange cloud).
- Set Cloudflare SSL mode to **Full (strict)** once origin certificate is configured.

### Option B: Let's Encrypt on VPS

- Install certbot/nginx plugin.
- Issue certs for `app.yourcompany.com` and `api.yourcompany.com`.
- Update nginx config to listen on 443 with cert files.

## 8) Operations

Restart:

```bash
docker compose --env-file .env.production -f docker-compose.yml -f compose.production.yaml restart
```

Logs:

```bash
docker compose --env-file .env.production -f docker-compose.yml -f compose.production.yaml logs -f reverse_proxy backend frontend
```

If you intentionally want local Postgres on VPS (not recommended for production), start it explicitly:

```bash
docker compose --env-file .env.production -f docker-compose.yml -f compose.production.yaml up -d postgres
```

## Security Notes

- Do not commit `.env.production`.
- Keep DB on managed service when possible.
- Restrict VPS firewall to 22/80/443 and known admin IPs.
