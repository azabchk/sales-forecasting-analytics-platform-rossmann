#!/usr/bin/env python3
"""
Bootstrap script — creates the first admin account.
Run once after `scripts/init_db.py`:

    python scripts/create_admin.py

You will be prompted for email, username, and password.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow importing from project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=False)

import sqlalchemy as sa
from passlib.context import CryptContext

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set in .env")
    sys.exit(1)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main() -> None:
    print("=== Create Admin Account ===")
    email = input("Email: ").strip().lower()
    username = input("Username: ").strip()
    password = input("Password (min 8 chars): ").strip()

    if len(password) < 8:
        print("ERROR: Password must be at least 8 characters.")
        sys.exit(1)
    if not email or "@" not in email:
        print("ERROR: Invalid email.")
        sys.exit(1)
    if not username:
        print("ERROR: Username cannot be empty.")
        sys.exit(1)

    engine = sa.create_engine(DATABASE_URL, future=True)
    hashed = pwd_context.hash(password)

    with engine.begin() as conn:
        existing = conn.execute(
            sa.text("SELECT id FROM users WHERE email = :email OR username = :username"),
            {"email": email, "username": username},
        ).fetchone()
        if existing:
            print("ERROR: Email or username already exists.")
            sys.exit(1)

        conn.execute(
            sa.text(
                """
                INSERT INTO users (email, username, hashed_password, role, is_active, created_by)
                VALUES (:email, :username, :hashed, 'admin', TRUE, 'bootstrap_script')
                """
            ),
            {"email": email, "username": username, "hashed": hashed},
        )

    print(f"\n✓ Admin account created: {username} <{email}>")
    print("You can now log in to the platform.")


if __name__ == "__main__":
    main()
