from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from backend.tests.diagnostics_auth_helpers import create_auth_headers

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_registry import insert_preflight_run  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _insert_registry_record(
    *,
    database_url: str,
    run_id: str,
    source_name: str,
    created_at: datetime,
    mode: str,
    final_status: str,
    blocked: bool,
    used_unified: bool,
    artifact_dir: Path,
) -> None:
    insert_preflight_run(
        {
            "run_id": run_id,
            "source_name": source_name,
            "created_at": created_at,
            "mode": mode,
            "validation_status": "PASS",
            "semantic_status": final_status if final_status in {"PASS", "WARN", "FAIL"} else "PASS",
            "final_status": final_status,
            "used_input_path": str((artifact_dir / "unified.csv").resolve()),
            "used_unified": used_unified,
            "artifact_dir": str(artifact_dir.resolve()),
            "validation_report_path": str((artifact_dir / "validation_report.json").resolve()),
            "manifest_path": str((artifact_dir / "manifest.json").resolve()),
            "summary_json": {"mode": mode},
            "blocked": blocked,
            "block_reason": "semantic_fail" if blocked else None,
        },
        database_url=database_url,
    )


def _seed_registry(monkeypatch, tmp_path: Path) -> tuple[TestClient, Path, dict[str, str]]:
    db_path = tmp_path / "diagnostics_analytics.db"
    database_url = f"sqlite+pysqlite:///{db_path.resolve()}"
    artifact_root = (tmp_path / "preflight_root").resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PREFLIGHT_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("DIAGNOSTICS_AUTH_ENABLED", "1")
    headers, _, _ = create_auth_headers(
        database_url=database_url,
        scopes=["diagnostics:read"],
        name="analytics-reader",
    )

    fixtures = [
        {
            "run_id": "run_001",
            "source_name": "train",
            "created_at": datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
            "mode": "report_only",
            "final_status": "PASS",
            "blocked": False,
            "used_unified": False,
            "rules": [
                {
                    "rule_id": "sales_non_negative",
                    "rule_type": "between",
                    "severity": "FAIL",
                    "status": "PASS",
                    "message": "Sales are non-negative.",
                    "target": ["sales"],
                    "observed": {"violation_count": 0},
                }
            ],
        },
        {
            "run_id": "run_002",
            "source_name": "train",
            "created_at": datetime(2026, 2, 21, 11, 0, tzinfo=timezone.utc),
            "mode": "enforce",
            "final_status": "WARN",
            "blocked": False,
            "used_unified": True,
            "rules": [
                {
                    "rule_id": "customers_null_ratio",
                    "rule_type": "max_null_ratio",
                    "severity": "WARN",
                    "status": "WARN",
                    "message": "Customers null ratio is above threshold.",
                    "target": ["customers"],
                    "observed": {"null_ratio": 0.2},
                }
            ],
        },
        {
            "run_id": "run_003",
            "source_name": "store",
            "created_at": datetime(2026, 2, 21, 12, 0, tzinfo=timezone.utc),
            "mode": "enforce",
            "final_status": "FAIL",
            "blocked": True,
            "used_unified": True,
            "rules": [
                {
                    "rule_id": "store_pk_unique",
                    "rule_type": "composite_unique",
                    "severity": "FAIL",
                    "status": "FAIL",
                    "message": "Store key duplicates found.",
                    "target": ["store_id"],
                    "observed": {"duplicate_row_count": 2},
                }
            ],
        },
        {
            "run_id": "run_004",
            "source_name": "train",
            "created_at": datetime(2026, 2, 22, 9, 30, tzinfo=timezone.utc),
            "mode": "report_only",
            "final_status": "FAIL",
            "blocked": False,
            "used_unified": True,
            "rules": [
                {
                    "rule_id": "day_of_week_allowed",
                    "rule_type": "accepted_values",
                    "severity": "FAIL",
                    "status": "FAIL",
                    "message": "day_of_week contains unsupported values.",
                    "target": ["day_of_week"],
                    "observed": {"invalid_count": 1},
                }
            ],
        },
    ]

    for fixture in fixtures:
        run_id = fixture["run_id"]
        source_name = fixture["source_name"]
        artifact_dir = artifact_root / run_id / source_name
        artifact_dir.mkdir(parents=True, exist_ok=True)
        _write_json(artifact_dir / "validation_report.json", {"status": "PASS", "checks": {}, "errors": [], "warnings": [], "metadata": {}})
        _write_json(
            artifact_dir / "semantic_report.json",
            {
                "status": fixture["final_status"] if fixture["final_status"] in {"PASS", "WARN", "FAIL"} else "PASS",
                "summary": "Semantic quality checks completed.",
                "counts": {"total": len(fixture["rules"]), "passed": 0, "warned": 0, "failed": 0},
                "rules": fixture["rules"],
            },
        )
        _write_json(
            artifact_dir / "manifest.json",
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
        (artifact_dir / "unified.csv").write_text("col\n1\n", encoding="utf-8")

        _insert_registry_record(
            database_url=database_url,
            run_id=run_id,
            source_name=source_name,
            created_at=fixture["created_at"],
            mode=fixture["mode"],
            final_status=fixture["final_status"],
            blocked=fixture["blocked"],
            used_unified=fixture["used_unified"],
            artifact_dir=artifact_dir,
        )

    return TestClient(app), artifact_root, headers


def test_stats_endpoint_returns_expected_aggregates(monkeypatch, tmp_path: Path):
    client, _, headers = _seed_registry(monkeypatch, tmp_path)
    response = client.get(
        "/api/v1/diagnostics/preflight/stats?date_from=2026-02-20&date_to=2026-02-22",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["total_runs"] == 4
    assert payload["pass_count"] == 1
    assert payload["warn_count"] == 1
    assert payload["fail_count"] == 2
    assert payload["blocked_count"] == 1
    assert payload["used_unified_count"] == 3
    assert payload["by_source"]["train"]["total_runs"] == 3
    assert payload["by_source"]["store"]["total_runs"] == 1


def test_stats_endpoint_filters(monkeypatch, tmp_path: Path):
    client, _, headers = _seed_registry(monkeypatch, tmp_path)
    response = client.get(
        "/api/v1/diagnostics/preflight/stats?source_name=train&mode=report_only",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_runs"] == 2
    assert payload["pass_count"] == 1
    assert payload["fail_count"] == 1
    assert payload["blocked_count"] == 0

    response_fail_only = client.get("/api/v1/diagnostics/preflight/stats?final_status=FAIL", headers=headers)
    assert response_fail_only.status_code == 200
    assert response_fail_only.json()["total_runs"] == 2


def test_trends_endpoint_groups_by_day(monkeypatch, tmp_path: Path):
    client, _, headers = _seed_registry(monkeypatch, tmp_path)
    response = client.get(
        "/api/v1/diagnostics/preflight/trends?date_from=2026-02-20&date_to=2026-02-22&bucket=day",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["bucket"] == "day"

    items = {item["bucket_start"][:10]: item for item in payload["items"]}
    assert items["2026-02-20"]["pass_count"] == 1
    assert items["2026-02-21"]["warn_count"] == 1
    assert items["2026-02-21"]["fail_count"] == 1
    assert items["2026-02-21"]["blocked_count"] == 1
    assert items["2026-02-22"]["fail_count"] == 1


def test_rules_top_endpoint_returns_frequency(monkeypatch, tmp_path: Path):
    client, _, headers = _seed_registry(monkeypatch, tmp_path)
    response = client.get(
        "/api/v1/diagnostics/preflight/rules/top?date_from=2026-02-20&date_to=2026-02-22&limit=5",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 5
    assert len(payload["items"]) >= 3

    by_rule = {item["rule_id"]: item for item in payload["items"]}
    assert by_rule["customers_null_ratio"]["warn_count"] == 1
    assert by_rule["customers_null_ratio"]["fail_count"] == 0
    assert by_rule["store_pk_unique"]["fail_count"] == 1
    assert by_rule["day_of_week_allowed"]["fail_count"] == 1
    assert by_rule["day_of_week_allowed"]["last_seen_at"].startswith("2026-02-22")


def test_invalid_analytics_query_params(monkeypatch, tmp_path: Path):
    client, _, headers = _seed_registry(monkeypatch, tmp_path)

    invalid_days_response = client.get(
        "/api/v1/diagnostics/preflight/stats?days=7&date_from=2026-02-01",
        headers=headers,
    )
    assert invalid_days_response.status_code == 400
    assert "days" in invalid_days_response.json()["detail"]

    invalid_bucket_response = client.get("/api/v1/diagnostics/preflight/trends?bucket=week", headers=headers)
    assert invalid_bucket_response.status_code == 422
