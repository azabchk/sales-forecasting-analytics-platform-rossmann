"""
Ensure a smoke-test admin user exists in the database.
Safe to run multiple times (uses INSERT … ON CONFLICT DO NOTHING).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)

BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import sqlalchemy as sa
from passlib.context import CryptContext

SMOKE_EMAIL = os.getenv("SMOKE_USER_EMAIL", "smoke@example.com")
SMOKE_PASSWORD = os.getenv("SMOKE_USER_PASSWORD", "SmokePass123!")

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main() -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")

    engine = sa.create_engine(db_url)
    hashed = _pwd.hash(SMOKE_PASSWORD)
    now = datetime.now(timezone.utc)

    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO users (email, username, hashed_password, role, is_active, created_at, created_by)
                VALUES (:email, :username, :hashed, 'admin', TRUE, :now, 'smoke-setup')
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {"email": SMOKE_EMAIL, "username": "smokeuser", "hashed": hashed, "now": now},
        )

    print(f"[smoke-user] Smoke user ready: {SMOKE_EMAIL}")


if __name__ == "__main__":
    main()
