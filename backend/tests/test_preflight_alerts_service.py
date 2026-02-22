from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.preflight_alerts_service import evaluate_alert_policies, load_alert_policies
from app.services.preflight_alerts_service import (
    acknowledge_alert,
    create_silence,
    expire_silence_by_id,
    get_active_alerts,
    list_alert_audit,
    list_silences,
    run_alert_evaluation,
    unacknowledge_alert,
)
from app.services.preflight_notifications_service import EVENT_ALERT_FIRING, EVENT_ALERT_RESOLVED
from src.etl.preflight_alert_registry import (
    acquire_scheduler_lease,
    get_alert_state,
    get_scheduler_lease,
    list_alert_history,
    release_scheduler_lease,
)
from src.etl.preflight_notification_outbox_registry import list_outbox_history
from src.etl.preflight_registry import insert_preflight_run


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _write_policy_file(path: Path, policies: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": "v1", "policies": policies}
    with open(path, "w", encoding="utf-8") as file:
        yaml.safe_dump(payload, file, sort_keys=False)


def _write_notification_channels(path: Path) -> None:
    payload = {
        "version": "v1",
        "channels": [
            {
                "id": "default_webhook",
                "type": "webhook",
                "enabled": True,
                "target_url_env": "PREFLIGHT_ALERTS_WEBHOOK_URL",
                "timeout_seconds": 5,
                "max_attempts": 5,
                "backoff_seconds": 10,
                "enabled_event_types": ["ALERT_FIRING", "ALERT_RESOLVED"],
            }
        ],
    }
    with open(path, "w", encoding="utf-8") as file:
        yaml.safe_dump(payload, file, sort_keys=False)


def _seed_preflight_record(
    *,
    database_url: str,
    artifact_root: Path,
    run_id: str,
    source_name: str,
    created_at: datetime,
    final_status: str,
    blocked: bool = False,
    used_unified: bool = True,
    semantic_rules: list[dict] | None = None,
) -> None:
    artifact_dir = artifact_root / run_id / source_name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    validation_path = artifact_dir / "validation_report.json"
    manifest_path = artifact_dir / "manifest.json"
    semantic_path = artifact_dir / "semantic_report.json"
    unified_path = artifact_dir / "unified.csv"

    _write_json(
        validation_path,
        {
            "status": "PASS",
            "checks": {"required_columns": "PASS"},
            "errors": [],
            "warnings": [],
            "metadata": {},
        },
    )
    _write_json(
        manifest_path,
        {
            "contract_version": "v1",
            "profile": f"rossmann_{source_name}",
            "validation_status": "PASS",
            "renamed_columns": {},
            "extra_columns_dropped": [],
            "coercion_stats": {},
            "final_canonical_columns": [],
            "retained_extra_columns": [],
            "output_row_count": 1,
            "output_column_count": 1,
        },
    )

    if semantic_rules is not None:
        warned = sum(1 for rule in semantic_rules if str(rule.get("status", "")).upper() == "WARN")
        failed = sum(1 for rule in semantic_rules if str(rule.get("status", "")).upper() == "FAIL")
        passed = sum(1 for rule in semantic_rules if str(rule.get("status", "")).upper() == "PASS")
        _write_json(
            semantic_path,
            {
                "status": "FAIL" if failed > 0 else "WARN" if warned > 0 else "PASS",
                "summary": "Semantic quality checks completed.",
                "counts": {
                    "total": len(semantic_rules),
                    "passed": passed,
                    "warned": warned,
                    "failed": failed,
                },
                "rules": semantic_rules,
            },
        )

    unified_path.write_text("store_id,sales\n1,100.0\n", encoding="utf-8")

    insert_preflight_run(
        {
            "run_id": run_id,
            "source_name": source_name,
            "created_at": created_at,
            "mode": "enforce",
            "validation_status": "PASS",
            "semantic_status": final_status,
            "final_status": final_status,
            "used_input_path": str(unified_path.resolve()),
            "used_unified": used_unified,
            "artifact_dir": str(artifact_dir.resolve()),
            "validation_report_path": str(validation_path.resolve()),
            "manifest_path": str(manifest_path.resolve()),
            "summary_json": {
                "mode": "enforce",
                "paths": {
                    "semantic_report_path": str(semantic_path.resolve()),
                    "manifest_path": str(manifest_path.resolve()),
                    "validation_report_path": str(validation_path.resolve()),
                },
            },
            "blocked": blocked,
            "block_reason": "semantic_fail" if blocked else None,
        },
        database_url=database_url,
    )


def _configure_env(monkeypatch, tmp_path: Path) -> tuple[str, Path]:
    db_path = tmp_path / "alerts_service.db"
    database_url = f"sqlite+pysqlite:///{db_path.resolve()}"
    artifact_root = (tmp_path / "artifacts").resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PREFLIGHT_ARTIFACT_ROOT", str(artifact_root))
    return database_url, artifact_root


def test_load_alert_policies_parses_rule_based_metric(tmp_path: Path):
    policy_file = tmp_path / "policies.yaml"
    _write_policy_file(
        policy_file,
        [
            {
                "id": "day_of_week_rule_fail",
                "enabled": True,
                "severity": "MEDIUM",
                "source_name": "train",
                "window_days": 7,
                "metric_type": "semantic_rule_fail_count",
                "rule_id": "day_of_week_allowed",
                "operator": ">",
                "threshold": 0,
                "pending_evaluations": 2,
                "description": "Rule failure threshold",
            }
        ],
    )

    payload = load_alert_policies(policy_file)
    assert payload["version"] == "v1"
    assert len(payload["policies"]) == 1
    policy = payload["policies"][0]
    assert policy.metric_type == "semantic_rule_fail_count"
    assert policy.rule_id == "day_of_week_allowed"
    assert policy.pending_evaluations == 2


def test_alert_pending_to_firing_transition(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _configure_env(monkeypatch, tmp_path)
    policy_file = tmp_path / "policies.yaml"

    _write_policy_file(
        policy_file,
        [
            {
                "id": "fail_count_train",
                "enabled": True,
                "severity": "HIGH",
                "source_name": "train",
                "window_days": 7,
                "metric_type": "fail_count",
                "operator": ">",
                "threshold": 0,
                "pending_evaluations": 2,
                "description": "Train fail count is above zero.",
            }
        ],
    )

    created_at = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    _seed_preflight_record(
        database_url=database_url,
        artifact_root=artifact_root,
        run_id="run_fail_001",
        source_name="train",
        created_at=created_at,
        final_status="FAIL",
    )

    first_eval = evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(hours=1))
    first_item = first_eval["items"][0]
    assert first_item["status"] == "PENDING"

    state_after_first = get_alert_state("fail_count_train", database_url=database_url)
    assert state_after_first is not None
    assert state_after_first["status"] == "PENDING"
    assert int(state_after_first["consecutive_breaches"]) == 1

    second_eval = evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(hours=2))
    second_item = second_eval["items"][0]
    assert second_item["status"] == "FIRING"

    state_after_second = get_alert_state("fail_count_train", database_url=database_url)
    assert state_after_second is not None
    assert state_after_second["status"] == "FIRING"
    assert int(state_after_second["consecutive_breaches"]) == 2

    history_rows = list_alert_history(limit=10, policy_id="fail_count_train", database_url=database_url)
    statuses = [row["status"] for row in history_rows]
    assert "PENDING" in statuses
    assert "FIRING" in statuses


def test_alert_resolve_transition(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _configure_env(monkeypatch, tmp_path)
    policy_file = tmp_path / "policies.yaml"

    _write_policy_file(
        policy_file,
        [
            {
                "id": "blocked_count_any",
                "enabled": True,
                "severity": "HIGH",
                "window_days": 1,
                "metric_type": "blocked_count",
                "operator": ">",
                "threshold": 0,
                "pending_evaluations": 1,
                "description": "Blocked runs detected.",
            }
        ],
    )

    created_at = datetime(2026, 2, 10, 9, 0, tzinfo=timezone.utc)
    _seed_preflight_record(
        database_url=database_url,
        artifact_root=artifact_root,
        run_id="run_blocked_001",
        source_name="store",
        created_at=created_at,
        final_status="FAIL",
        blocked=True,
    )

    fired_eval = evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(hours=1))
    assert fired_eval["items"][0]["status"] == "FIRING"

    resolved_eval = evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(days=4))
    assert resolved_eval["items"][0]["status"] == "OK"

    state = get_alert_state("blocked_count_any", database_url=database_url)
    assert state is None

    history_rows = list_alert_history(limit=20, policy_id="blocked_count_any", database_url=database_url)
    statuses = [row["status"] for row in history_rows]
    assert "FIRING" in statuses
    assert "RESOLVED" in statuses


def test_semantic_rule_fail_count_metric(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _configure_env(monkeypatch, tmp_path)
    policy_file = tmp_path / "policies.yaml"

    _write_policy_file(
        policy_file,
        [
            {
                "id": "day_of_week_rule_fail",
                "enabled": True,
                "severity": "MEDIUM",
                "source_name": "train",
                "window_days": 30,
                "metric_type": "semantic_rule_fail_count",
                "rule_id": "day_of_week_allowed",
                "operator": ">",
                "threshold": 0,
                "pending_evaluations": 1,
                "description": "day_of_week_allowed rule must not fail.",
            }
        ],
    )

    created_at = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    _seed_preflight_record(
        database_url=database_url,
        artifact_root=artifact_root,
        run_id="run_semantic_001",
        source_name="train",
        created_at=created_at,
        final_status="FAIL",
        semantic_rules=[
            {
                "rule_id": "day_of_week_allowed",
                "rule_type": "accepted_values",
                "severity": "FAIL",
                "status": "FAIL",
                "message": "Invalid day_of_week value.",
                "target": ["day_of_week"],
                "observed": {"invalid_count": 1},
            }
        ],
    )

    payload = evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(hours=1))
    assert payload["items"][0]["status"] == "FIRING"
    assert float(payload["items"][0]["current_value"]) == 1.0


def test_active_alerts_include_ack_and_silence_overlays(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _configure_env(monkeypatch, tmp_path)
    policy_file = tmp_path / "policies.yaml"
    _write_policy_file(
        policy_file,
        [
            {
                "id": "blocked_runs_any",
                "enabled": True,
                "severity": "HIGH",
                "window_days": 7,
                "metric_type": "blocked_count",
                "operator": ">",
                "threshold": 0,
                "pending_evaluations": 1,
                "description": "Blocked runs detected.",
            }
        ],
    )

    created_at = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    _seed_preflight_record(
        database_url=database_url,
        artifact_root=artifact_root,
        run_id="run_overlay_001",
        source_name="train",
        created_at=created_at,
        final_status="FAIL",
        blocked=True,
    )

    evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(minutes=10))
    now = datetime.now(timezone.utc)
    silence = create_silence(
        actor="qa_user",
        starts_at=now - timedelta(minutes=5),
        ends_at=now + timedelta(hours=4),
        reason="Known upstream issue",
        policy_id="blocked_runs_any",
        severity="HIGH",
    )
    assert silence["silence_id"]

    acknowledgement = acknowledge_alert(alert_id="blocked_runs_any", actor="qa_user", note="Investigating")
    assert acknowledgement["alert_id"] == "blocked_runs_any"
    assert acknowledgement["cleared_at"] is None

    active_payload = get_active_alerts(policy_path=policy_file, auto_evaluate=False)
    assert active_payload["total_active"] == 1
    item = active_payload["items"][0]
    assert item["is_silenced"] is True
    assert item["silence"]["silence_id"] == silence["silence_id"]
    assert item["is_acknowledged"] is True
    assert item["acknowledgement"]["acknowledged_by"] == "qa_user"


def test_silence_expiry_and_ack_unack_generate_audit(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _configure_env(monkeypatch, tmp_path)
    policy_file = tmp_path / "policies.yaml"
    _write_policy_file(
        policy_file,
        [
            {
                "id": "fail_count_train",
                "enabled": True,
                "severity": "HIGH",
                "source_name": "train",
                "window_days": 7,
                "metric_type": "fail_count",
                "operator": ">",
                "threshold": 0,
                "pending_evaluations": 1,
                "description": "Train fail count is above zero.",
            }
        ],
    )

    created_at = datetime(2026, 2, 22, 9, 0, tzinfo=timezone.utc)
    _seed_preflight_record(
        database_url=database_url,
        artifact_root=artifact_root,
        run_id="run_overlay_002",
        source_name="train",
        created_at=created_at,
        final_status="FAIL",
    )
    evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(minutes=15))

    silence = create_silence(
        actor="ops_user",
        starts_at=created_at,
        ends_at=created_at + timedelta(hours=2),
        reason="Maintenance window",
        policy_id="fail_count_train",
    )
    assert silence["expired_at"] is None

    expired = expire_silence_by_id(silence_id=silence["silence_id"], actor="ops_user")
    assert expired["expired_at"] is not None

    ack = acknowledge_alert(alert_id="fail_count_train", actor="ops_user", note="Will monitor")
    assert ack["cleared_at"] is None

    unacked = unacknowledge_alert(alert_id="fail_count_train", actor="ops_user")
    assert unacked["cleared_at"] is not None

    silences_payload = list_silences(limit=10, include_expired=True)
    assert silences_payload["items"][0]["silence_id"] == silence["silence_id"]
    assert silences_payload["items"][0]["is_active"] is False

    audit_payload = list_alert_audit(limit=100)
    event_types = {item["event_type"] for item in audit_payload["items"]}
    assert "SILENCED" in event_types
    assert "UNSILENCED" in event_types
    assert "ACKED" in event_types
    assert "UNACKED" in event_types


def test_run_alert_evaluation_records_scheduler_actor(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _configure_env(monkeypatch, tmp_path)
    policy_file = tmp_path / "policies.yaml"
    _write_policy_file(
        policy_file,
        [
            {
                "id": "blocked_runs_any",
                "enabled": True,
                "severity": "HIGH",
                "window_days": 7,
                "metric_type": "blocked_count",
                "operator": ">",
                "threshold": 0,
                "pending_evaluations": 1,
                "description": "Blocked runs detected.",
            }
        ],
    )

    created_at = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    _seed_preflight_record(
        database_url=database_url,
        artifact_root=artifact_root,
        run_id="run_scheduler_actor_001",
        source_name="train",
        created_at=created_at,
        final_status="FAIL",
        blocked=True,
    )

    summary = run_alert_evaluation(
        policy_path=policy_file,
        evaluated_at=created_at + timedelta(minutes=20),
        audit_actor="system:scheduler",
    )
    assert summary["active_count"] == 1

    audit_rows = list_alert_audit(limit=20)
    evaluated_events = [item for item in audit_rows["items"] if item["event_type"] == "EVALUATED"]
    assert evaluated_events
    assert any(event["actor"] == "system:scheduler" for event in evaluated_events)


def test_scheduler_lease_acquire_renew_and_release(monkeypatch, tmp_path: Path):
    database_url, _ = _configure_env(monkeypatch, tmp_path)
    lease_name = "preflight_alerts_scheduler"
    owner_a = "instance-a"
    owner_b = "instance-b"
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)

    assert acquire_scheduler_lease(
        lease_name=lease_name,
        owner_id=owner_a,
        lease_ttl_seconds=30,
        now=now,
        database_url=database_url,
    )

    assert not acquire_scheduler_lease(
        lease_name=lease_name,
        owner_id=owner_b,
        lease_ttl_seconds=30,
        now=now + timedelta(seconds=5),
        database_url=database_url,
    )

    assert acquire_scheduler_lease(
        lease_name=lease_name,
        owner_id=owner_a,
        lease_ttl_seconds=30,
        now=now + timedelta(seconds=10),
        database_url=database_url,
    )

    lease_row = get_scheduler_lease(lease_name=lease_name, database_url=database_url)
    assert lease_row is not None
    assert lease_row["owner_id"] == owner_a

    assert release_scheduler_lease(
        lease_name=lease_name,
        owner_id=owner_a,
        released_at=now + timedelta(seconds=11),
        database_url=database_url,
    )

    assert acquire_scheduler_lease(
        lease_name=lease_name,
        owner_id=owner_b,
        lease_ttl_seconds=30,
        now=now + timedelta(seconds=12),
        database_url=database_url,
    )


def test_alert_transitions_enqueue_notifications_without_duplicates(monkeypatch, tmp_path: Path):
    database_url, artifact_root = _configure_env(monkeypatch, tmp_path)
    policy_file = tmp_path / "policies.yaml"
    notifications_path = tmp_path / "channels.yaml"

    monkeypatch.setenv("PREFLIGHT_NOTIFICATION_CHANNELS_PATH", str(notifications_path.resolve()))
    monkeypatch.setenv("PREFLIGHT_ALERTS_WEBHOOK_URL", "https://example.local/webhook")
    _write_notification_channels(notifications_path)

    _write_policy_file(
        policy_file,
        [
            {
                "id": "blocked_runs_any",
                "enabled": True,
                "severity": "HIGH",
                "source_name": "train",
                "window_days": 1,
                "metric_type": "blocked_count",
                "operator": ">",
                "threshold": 0,
                "pending_evaluations": 2,
                "description": "Blocked runs detected.",
            }
        ],
    )

    created_at = datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc)
    _seed_preflight_record(
        database_url=database_url,
        artifact_root=artifact_root,
        run_id="run_notify_001",
        source_name="train",
        created_at=created_at,
        final_status="FAIL",
        blocked=True,
    )

    first_eval = evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(hours=1))
    assert first_eval["items"][0]["status"] == "PENDING"
    assert list_outbox_history(limit=20) == []

    second_eval = evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(hours=2))
    assert second_eval["items"][0]["status"] == "FIRING"
    outbox_after_firing = list_outbox_history(limit=20)
    assert len(outbox_after_firing) == 1
    assert outbox_after_firing[0]["event_type"] == EVENT_ALERT_FIRING

    third_eval = evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(hours=3))
    assert third_eval["items"][0]["status"] == "FIRING"
    outbox_after_repeat = list_outbox_history(limit=20)
    assert len(outbox_after_repeat) == 1

    resolved_eval = evaluate_alert_policies(policy_path=policy_file, evaluated_at=created_at + timedelta(days=3))
    assert resolved_eval["items"][0]["status"] == "OK"
    outbox_after_resolved = list_outbox_history(limit=20)
    event_types = [row["event_type"] for row in outbox_after_resolved]
    assert event_types.count(EVENT_ALERT_FIRING) == 1
    assert event_types.count(EVENT_ALERT_RESOLVED) == 1
