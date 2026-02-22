from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
import yaml

from app.main import app
from backend.tests.diagnostics_auth_helpers import create_auth_headers

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_registry import insert_preflight_run  # noqa: E402


def _prepare_env(monkeypatch, tmp_path: Path) -> tuple[str, Path, Path]:
    db_path = tmp_path / "diagnostics_alerts.db"
    database_url = f"sqlite+pysqlite:///{db_path.resolve()}"
    artifact_root = (tmp_path / "preflight_root").resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    policy_path = tmp_path / "preflight_alert_policies.yaml"

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PREFLIGHT_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("PREFLIGHT_ALERT_POLICY_PATH", str(policy_path.resolve()))
    monkeypatch.setenv("DIAGNOSTICS_AUTH_ENABLED", "1")
    return database_url, artifact_root, policy_path


def _write_policy(path: Path, policies: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        yaml.safe_dump({"version": "v1", "policies": policies}, file, sort_keys=False)


def _seed_preflight_record(
    *,
    database_url: str,
    artifact_root: Path,
    run_id: str,
    source_name: str,
    blocked: bool,
    final_status: str,
    created_at: datetime | None = None,
) -> None:
    artifact_dir = artifact_root / run_id / source_name
    artifact_dir.mkdir(parents=True, exist_ok=True)
    unified_path = artifact_dir / "unified.csv"
    unified_path.write_text("store_id,sales\n1,100.0\n", encoding="utf-8")

    insert_preflight_run(
        {
            "run_id": run_id,
            "source_name": source_name,
            "created_at": created_at or (datetime.now(timezone.utc) - timedelta(hours=1)),
            "mode": "enforce",
            "validation_status": "PASS",
            "semantic_status": final_status,
            "final_status": final_status,
            "used_input_path": str(unified_path.resolve()),
            "used_unified": True,
            "artifact_dir": str(artifact_dir.resolve()),
            "validation_report_path": None,
            "manifest_path": None,
            "summary_json": {"mode": "enforce"},
            "blocked": blocked,
            "block_reason": "semantic_fail" if blocked else None,
        },
        database_url=database_url,
    )


def test_auth_and_scope_requirements_for_alert_endpoints(monkeypatch, tmp_path: Path):
    database_url, artifact_root, policy_path = _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)
    read_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read"],
        name="diag-read-only",
    )
    operate_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read", "diagnostics:operate"],
        name="diag-operator",
    )
    admin_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:admin"],
        name="diag-admin",
    )

    _seed_preflight_record(
        database_url=database_url,
        artifact_root=artifact_root,
        run_id="run_alert_001",
        source_name="train",
        blocked=True,
        final_status="FAIL",
    )

    _write_policy(
        policy_path,
        [
            {
                "id": "blocked_runs_any",
                "enabled": True,
                "severity": "HIGH",
                "window_days": 30,
                "metric_type": "blocked_count",
                "operator": ">=",
                "threshold": 1,
                "pending_evaluations": 1,
                "description": "Blocked preflight runs detected in window.",
            }
        ],
    )

    active_response = client.get(
        "/api/v1/diagnostics/preflight/alerts/active?auto_evaluate=true",
        headers=read_headers,
    )
    assert active_response.status_code == 200
    assert active_response.json()["total_active"] == 1

    missing_key_response = client.get("/api/v1/diagnostics/preflight/alerts/active?auto_evaluate=true")
    assert missing_key_response.status_code == 401
    assert "x-api-key" in missing_key_response.json()["detail"].lower()

    invalid_key_response = client.get(
        "/api/v1/diagnostics/preflight/alerts/active?auto_evaluate=true",
        headers={"X-API-Key": "invalid-key"},
    )
    assert invalid_key_response.status_code == 401

    read_scope_silence = client.post(
        "/api/v1/diagnostics/preflight/alerts/silences",
        headers=read_headers,
        json={
            "ends_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "reason": "test",
            "policy_id": "blocked_runs_any",
        },
    )
    assert read_scope_silence.status_code == 403

    operate_scope_ack = client.post(
        "/api/v1/diagnostics/preflight/alerts/blocked_runs_any/ack",
        headers=operate_headers,
        json={"note": "test"},
    )
    assert operate_scope_ack.status_code == 200

    no_admin_evaluate = client.post("/api/v1/diagnostics/preflight/alerts/evaluate", headers=operate_headers)
    assert no_admin_evaluate.status_code == 403

    monkeypatch.setenv("PREFLIGHT_ALERTS_ALLOW_EVALUATE", "1")
    admin_evaluate = client.post("/api/v1/diagnostics/preflight/alerts/evaluate", headers=admin_headers)
    assert admin_evaluate.status_code == 200


def test_alert_silence_ack_unack_and_audit_endpoints(monkeypatch, tmp_path: Path):
    database_url, artifact_root, policy_path = _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)
    operator_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read", "diagnostics:operate"],
        name="ops-api-client",
    )

    _seed_preflight_record(
        database_url=database_url,
        artifact_root=artifact_root,
        run_id="run_alert_002",
        source_name="train",
        blocked=True,
        final_status="FAIL",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
    )

    _write_policy(
        policy_path,
        [
            {
                "id": "blocked_runs_any",
                "enabled": True,
                "severity": "HIGH",
                "window_days": 30,
                "metric_type": "blocked_count",
                "operator": ">=",
                "threshold": 1,
                "pending_evaluations": 1,
                "description": "Blocked preflight runs detected in window.",
            }
        ],
    )

    active_before = client.get(
        "/api/v1/diagnostics/preflight/alerts/active?auto_evaluate=true",
        headers=operator_headers,
    )
    assert active_before.status_code == 200
    assert active_before.json()["total_active"] == 1

    silence_response = client.post(
        "/api/v1/diagnostics/preflight/alerts/silences",
        headers=operator_headers,
        json={
            "ends_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            "reason": "Suppress during incident triage",
            "policy_id": "blocked_runs_any",
            "severity": "HIGH",
        },
    )
    assert silence_response.status_code == 200
    silence_payload = silence_response.json()
    silence_id = silence_payload["silence_id"]

    ack_response = client.post(
        "/api/v1/diagnostics/preflight/alerts/blocked_runs_any/ack",
        headers=operator_headers,
        json={"note": "Investigating root cause"},
    )
    assert ack_response.status_code == 200
    assert ack_response.json()["acknowledged_by"] == "ops-api-client"

    active_after = client.get(
        "/api/v1/diagnostics/preflight/alerts/active?auto_evaluate=false",
        headers=operator_headers,
    )
    assert active_after.status_code == 200
    active_payload = active_after.json()
    item = active_payload["items"][0]
    assert item["is_silenced"] is True
    assert item["silence"]["silence_id"] == silence_id
    assert item["is_acknowledged"] is True
    assert item["acknowledgement"]["alert_id"] == "blocked_runs_any"

    silences_list = client.get(
        "/api/v1/diagnostics/preflight/alerts/silences?limit=20&include_expired=true",
        headers=operator_headers,
    )
    assert silences_list.status_code == 200
    assert len(silences_list.json()["items"]) >= 1

    expire_response = client.post(
        f"/api/v1/diagnostics/preflight/alerts/silences/{silence_id}/expire",
        headers=operator_headers,
    )
    assert expire_response.status_code == 200
    assert expire_response.json()["expired_at"] is not None

    unack_response = client.post(
        "/api/v1/diagnostics/preflight/alerts/blocked_runs_any/unack",
        headers=operator_headers,
    )
    assert unack_response.status_code == 200
    assert unack_response.json()["cleared_at"] is not None

    audit_response = client.get("/api/v1/diagnostics/preflight/alerts/audit?limit=50", headers=operator_headers)
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    event_types = {item["event_type"] for item in audit_payload["items"]}
    assert all("api_key" not in str(item).lower() for item in audit_payload["items"])
    assert any(item["actor"] == "ops-api-client" for item in audit_payload["items"])
    assert "SILENCED" in event_types
    assert "UNSILENCED" in event_types
    assert "ACKED" in event_types
    assert "UNACKED" in event_types


def test_active_endpoint_default_is_non_mutating(monkeypatch, tmp_path: Path):
    database_url, artifact_root, policy_path = _prepare_env(monkeypatch, tmp_path)
    client = TestClient(app)
    read_headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read"],
        name="diag-reader",
    )

    _seed_preflight_record(
        database_url=database_url,
        artifact_root=artifact_root,
        run_id="run_alert_default_behavior",
        source_name="train",
        blocked=True,
        final_status="FAIL",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )

    _write_policy(
        policy_path,
        [
            {
                "id": "blocked_runs_any",
                "enabled": True,
                "severity": "HIGH",
                "window_days": 30,
                "metric_type": "blocked_count",
                "operator": ">=",
                "threshold": 1,
                "pending_evaluations": 1,
                "description": "Blocked preflight runs detected in window.",
            }
        ],
    )

    default_response = client.get("/api/v1/diagnostics/preflight/alerts/active", headers=read_headers)
    assert default_response.status_code == 200
    assert default_response.json()["total_active"] == 0

    explicit_eval_response = client.get(
        "/api/v1/diagnostics/preflight/alerts/active?auto_evaluate=true",
        headers=read_headers,
    )
    assert explicit_eval_response.status_code == 200
    assert explicit_eval_response.json()["total_active"] == 1
