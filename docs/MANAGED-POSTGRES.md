# Managed PostgreSQL Options

Supported production options for `DATABASE_URL`.

## Common Requirements

- Use PostgreSQL 14+
- Enforce TLS (`sslmode=require` if provider needs it)
- Restrict inbound connections by IP / VPC where possible
- Enable daily backups and point-in-time recovery

`DATABASE_URL` format:

```text
postgresql+psycopg2://<user>:<password>@<host>:<port>/<db_name>
```

## Option 1: Supabase Postgres

1. Create Supabase project.
2. Open **Project Settings -> Database**.
3. Copy connection string and convert scheme to `postgresql+psycopg2://`.
4. Set in platform env:
   - `DATABASE_URL`
5. Networking/security:
   - Keep DB password in secret manager only.
   - Restrict network access (if available on your plan).

## Option 2: DigitalOcean Managed Postgres

1. Create database cluster in DigitalOcean.
2. Create database user + database.
3. In connection details, copy host/port/user/password.
4. Set:
   - `DATABASE_URL`
5. Networking/security:
   - Add trusted sources (Render/Fly egress ranges or your VPS IP).
   - Enable automatic failover and backups.

## Option 3: AWS RDS PostgreSQL

1. Create RDS PostgreSQL instance.
2. Configure security group ingress for backend origin only.
3. Create DB/user (or use initial DB).
4. Set:
   - `DATABASE_URL`
5. Networking/security:
   - Prefer private subnet + app in same VPC.
   - Enable automated backups + retention policy.

## Post-deploy Verification

Run:

```bash
BACKEND_PUBLIC_URL=https://api.yourcompany.com DATABASE_URL='postgresql+psycopg2://...'
bash scripts/prod_env_check.sh
```
