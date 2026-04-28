from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db import engine, fetch_one
from app.schemas import ChangePasswordRequest, RefreshRequest, TokenResponse, UserLoginRequest, UserRegisterRequest, UserResponse
from app.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_admin_user,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)


def _get_user_by_email(email: str) -> dict[str, Any] | None:
    return fetch_one(
        sa.text("SELECT id, email, username, hashed_password, role, is_active, created_at, created_by FROM users WHERE email = :email"),
        {"email": email.strip().lower()},
    )


def _get_user_by_id(user_id: int) -> dict[str, Any] | None:
    return fetch_one(
        sa.text("SELECT id, email, username, role, is_active, created_at, created_by FROM users WHERE id = :id"),
        {"id": user_id},
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, request: Request) -> TokenResponse:
    user = _get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    token_data = {"sub": str(user["id"]), "role": user["role"]}
    token = create_access_token(token_data)
    refresh = create_refresh_token(token_data)
    return TokenResponse(
        access_token=token,
        refresh_token=refresh,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            username=user["username"],
            role=user["role"],
            is_active=user["is_active"],
            created_at=user["created_at"],
            created_by=user.get("created_by"),
        ),
    )


@router.post("/auth/refresh")
def refresh_token(payload: RefreshRequest) -> dict[str, str]:
    data = decode_refresh_token(payload.refresh_token)
    user_id = data.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = fetch_one(
        sa.text("SELECT id, role, is_active FROM users WHERE id = :id"),
        {"id": int(user_id)},
    )
    if not user or not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    token_data = {"sub": str(user["id"]), "role": user["role"]}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }


@router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: dict[str, Any] = Depends(get_current_user)) -> UserResponse:
    row = _get_user_by_id(current_user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**row)


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserRegisterRequest,
    admin: dict[str, Any] = Depends(get_admin_user),
) -> UserResponse:
    email = payload.email.strip().lower()
    username = payload.username.strip()

    existing_email = fetch_one(sa.text("SELECT id FROM users WHERE email = :email"), {"email": email})
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    existing_username = fetch_one(sa.text("SELECT id FROM users WHERE username = :username"), {"username": username})
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed = hash_password(payload.password)
    now = datetime.now(timezone.utc)

    with engine.begin() as conn:
        result = conn.execute(
            sa.text(
                """
                INSERT INTO users (email, username, hashed_password, role, is_active, created_at, created_by)
                VALUES (:email, :username, :hashed_password, :role, TRUE, :created_at, :created_by)
                RETURNING id, email, username, role, is_active, created_at, created_by
                """
            ),
            {
                "email": email,
                "username": username,
                "hashed_password": hashed,
                "role": payload.role,
                "created_at": now,
                "created_by": admin["email"],
            },
        )
        row = dict(result.mappings().first())

    return UserResponse(**row)


@router.get("/auth/users", response_model=list[UserResponse])
def list_users(admin: dict[str, Any] = Depends(get_admin_user)) -> list[UserResponse]:
    from app.db import fetch_all
    rows = fetch_all(
        sa.text("SELECT id, email, username, role, is_active, created_at, created_by FROM users ORDER BY created_at DESC")
    )
    return [UserResponse(**r) for r in rows]


@router.patch("/auth/users/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    admin: dict[str, Any] = Depends(get_admin_user),
) -> UserResponse:
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    with engine.begin() as conn:
        result = conn.execute(
            sa.text(
                "UPDATE users SET is_active = FALSE WHERE id = :id "
                "RETURNING id, email, username, role, is_active, created_at, created_by"
            ),
            {"id": user_id},
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**dict(row))


@router.patch("/auth/me/password", status_code=200)
def change_password(
    payload: ChangePasswordRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    row = fetch_one(
        sa.text("SELECT hashed_password FROM users WHERE id = :id"),
        {"id": current_user["id"]},
    )
    if not row or not verify_password(payload.current_password, row["hashed_password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_hashed = hash_password(payload.new_password)
    with engine.begin() as conn:
        conn.execute(
            sa.text("UPDATE users SET hashed_password = :h WHERE id = :id"),
            {"h": new_hashed, "id": current_user["id"]},
        )
    return {"detail": "Password changed successfully"}


@router.patch("/auth/users/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: int,
    admin: dict[str, Any] = Depends(get_admin_user),
) -> UserResponse:
    with engine.begin() as conn:
        result = conn.execute(
            sa.text(
                "UPDATE users SET is_active = TRUE WHERE id = :id "
                "RETURNING id, email, username, role, is_active, created_at, created_by"
            ),
            {"id": user_id},
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**dict(row))
