from __future__ import annotations

import os
import sys
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.diagnostics_api_key_registry import authenticate_api_key, touch_api_client_usage  # noqa: E402

_DIAGNOSTICS_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

SCOPE_READ = "diagnostics:read"
SCOPE_OPERATE = "diagnostics:operate"
SCOPE_ADMIN = "diagnostics:admin"


class DiagnosticsPrincipal(BaseModel):
    client_id: str
    name: str
    actor: str
    scopes: list[str] = Field(default_factory=list)
    is_authenticated: bool = True
    legacy_mode: bool = False


def _auth_enabled() -> bool:
    value = str(os.getenv("DIAGNOSTICS_AUTH_ENABLED", "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def _legacy_fallback_enabled() -> bool:
    value = str(os.getenv("DIAGNOSTICS_AUTH_ALLOW_LEGACY_ACTOR", "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _normalize_scopes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    scopes: list[str] = []
    seen: set[str] = set()
    for item in value:
        scope = str(item).strip()
        if not scope or scope in seen:
            continue
        seen.add(scope)
        scopes.append(scope)
    return scopes


def _legacy_principal(request: Request) -> DiagnosticsPrincipal:
    actor = str(request.headers.get("X-Actor", "legacy-local")).strip() or "legacy-local"
    return DiagnosticsPrincipal(
        client_id="legacy-local",
        name="legacy-local",
        actor=actor,
        scopes=[SCOPE_READ, SCOPE_OPERATE, SCOPE_ADMIN],
        is_authenticated=False,
        legacy_mode=True,
    )


async def authenticate_diagnostics_principal(
    request: Request,
    api_key: str | None = Security(_DIAGNOSTICS_KEY_HEADER),
) -> DiagnosticsPrincipal:
    if not _auth_enabled():
        return _legacy_principal(request)

    if not api_key or not str(api_key).strip():
        if _legacy_fallback_enabled():
            return _legacy_principal(request)
        raise HTTPException(status_code=401, detail="Missing X-API-Key header for diagnostics access.")

    client = authenticate_api_key(str(api_key).strip())
    if client is None:
        raise HTTPException(status_code=401, detail="Invalid API key for diagnostics access.")

    scopes = _normalize_scopes(client.get("scopes"))
    actor = str(client.get("name") or client.get("client_id") or "unknown-client").strip()
    principal = DiagnosticsPrincipal(
        client_id=str(client.get("client_id")),
        name=str(client.get("name") or client.get("client_id")),
        actor=actor,
        scopes=scopes,
        is_authenticated=True,
        legacy_mode=False,
    )

    client_host = request.client.host if request.client else None
    try:
        touch_api_client_usage(principal.client_id, last_used_ip=client_host)
    except Exception:  # noqa: BLE001
        pass

    return principal


def _scope_allowed(required_scope: str, principal_scopes: list[str]) -> bool:
    required = str(required_scope).strip()
    if not required:
        return True
    if SCOPE_ADMIN in principal_scopes:
        return True
    return required in principal_scopes


def require_scope(scope: str) -> Callable[..., DiagnosticsPrincipal]:
    required_scope = str(scope).strip()

    async def _dependency(principal: DiagnosticsPrincipal = Depends(authenticate_diagnostics_principal)) -> DiagnosticsPrincipal:
        if _scope_allowed(required_scope, principal.scopes):
            return principal
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient scope. Required '{required_scope}' for diagnostics endpoint.",
        )

    return _dependency
