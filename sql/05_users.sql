-- 05_users.sql
-- User accounts for platform authentication

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(256) NOT NULL UNIQUE,
    username    VARCHAR(128) NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role        VARCHAR(32)  NOT NULL DEFAULT 'analyst',
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by  VARCHAR(256)
);

CREATE INDEX IF NOT EXISTS ix_users_email    ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);
CREATE INDEX IF NOT EXISTS ix_users_role     ON users(role);
