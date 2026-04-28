from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import sqlalchemy as sa

from app.db import fetch_one

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-use-long-random-string")
REFRESH_SECRET_KEY = os.getenv("REFRESH_SECRET_KEY", SECRET_KEY + "_refresh")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=True)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict[str, Any]) -> str:
    payload = dict(data)
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload["exp"] = expire
    payload["type"] = "access"
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    payload = dict(data)
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload["exp"] = expire
    payload["type"] = "refresh"
    return jwt.encode(payload, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def decode_refresh_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalid or expired")


def _decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    payload = _decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = fetch_one(
        sa.text("SELECT id, email, username, role, is_active FROM users WHERE id = :id"),
        {"id": int(user_id)},
    )
    if not user or not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def get_admin_user(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
