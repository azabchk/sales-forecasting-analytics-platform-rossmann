# Production Hardening Checklist

Use this checklist before go-live.

## Application Security (OWASP Top 10 quick pass)

- [ ] Injection: all DB queries use parameterized statements (no string SQL interpolation from user input).
- [ ] Auth/session: diagnostics API keys are rotated and scoped.
- [ ] Sensitive data exposure: secrets are env vars, not committed.
- [ ] Access control: diagnostics/admin endpoints protected by scope checks.
- [ ] Security misconfiguration: production `CORS_ORIGINS` restricted to trusted app domains only.
- [ ] Vulnerable dependencies: run `npm audit` and dependency updates before release.
- [ ] Logging/monitoring: API logs and health checks enabled.
- [ ] SSRF/open redirects: external webhook targets validated/sanitized.

## CORS Rules by Environment

- Staging:
  - `CORS_ORIGINS=https://stg-app.yourcompany.com`
- Production:
  - `CORS_ORIGINS=https://app.yourcompany.com`
- Never use `*` in production.

## Secrets Management

- [ ] Store secrets in platform env vars (Vercel/Render/Fly/GitHub Secrets).
- [ ] Keep `.env.production` out of git.
- [ ] Use separate secrets per environment (`staging` vs `production`).
- [ ] Rotate DB credentials and API keys on schedule.
- [ ] Verify logs/artifacts redact DB passwords and API tokens.

## Database Change Safety

- [ ] Apply schema changes using additive migrations only (expand/migrate/contract).
- [ ] Keep nullable/new columns and new tables backward-compatible with existing routes.
- [ ] Confirm `scripts/init_db.py` SQL bundle updates are documented before release.

## Database Backups

- [ ] Enable automated daily backups in managed Postgres.
- [ ] Enable point-in-time recovery if available.
- [ ] Test restore procedure at least once per quarter.

## CI/CD and Release Safety

- [ ] CI smoke pipeline green before deploy.
- [ ] Tag release (`v2.0.0` or newer) and publish release notes.
- [ ] Run `scripts/prod_env_check.sh` against production env.

## Observability

- [ ] `/api/v1/health` monitored.
- [ ] Error logs centralized.
- [ ] Prometheus/Grafana stack integration planned or enabled for hosted ops.
