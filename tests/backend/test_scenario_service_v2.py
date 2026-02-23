from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_PATH = PROJECT_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.services import scenario_service  # noqa: E402


def _fake_forecast_for_store(store_id: int, horizon_days: int) -> dict:
    points = []
    for idx in range(horizon_days):
        baseline = float((store_id * 10) + idx)
        scenario = baseline * 1.1
        points.append(
            {
                "date": f"2026-01-{idx + 1:02d}",
                "baseline_sales": baseline,
                "scenario_sales": scenario,
                "delta_sales": scenario - baseline,
                "scenario_lower": scenario * 0.9,
                "scenario_upper": scenario * 1.1,
            }
        )
    total_baseline = sum(item["baseline_sales"] for item in points)
    total_scenario = sum(item["scenario_sales"] for item in points)
    total_delta = total_scenario - total_baseline
    return {
        "summary": {
            "total_baseline_sales": total_baseline,
            "total_scenario_sales": total_scenario,
            "total_delta_sales": total_delta,
            "uplift_pct": (total_delta / total_baseline) * 100.0 if total_baseline else 0.0,
            "avg_daily_delta": total_delta / horizon_days if horizon_days else 0.0,
            "max_delta_date": points[0]["date"],
            "max_delta_value": max(item["delta_sales"] for item in points),
        },
        "points": points,
    }


@pytest.fixture(autouse=True)
def _patch_common_dependencies(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(scenario_service, "resolve_data_source_id", lambda data_source_id: int(data_source_id or 1))
    monkeypatch.setattr(scenario_service, "upsert_forecast_run", lambda *_args, **_kwargs: None)


def test_scenario_v2_store_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        scenario_service,
        "forecast_scenario_for_store",
        lambda **kwargs: _fake_forecast_for_store(kwargs["store_id"], kwargs["horizon_days"]),
    )

    payload = scenario_service.run_scenario_v2(
        store_id=7,
        segment=None,
        price_change_pct=5.0,
        promo_mode="as_is",
        weekend_open=True,
        school_holiday=0,
        demand_shift_pct=0.0,
        confidence_level=0.8,
        horizon_days=3,
        data_source_id=None,
    )

    assert payload["target"]["mode"] == "store"
    assert payload["target"]["store_id"] == 7
    assert len(payload["points"]) == 3
    assert "uplift_pct" in payload["summary"]


def test_scenario_v2_segment_mode_aggregates(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(scenario_service, "_resolve_segment_store_ids", lambda **_kwargs: [1, 2])
    monkeypatch.setattr(
        scenario_service,
        "forecast_scenario_for_store",
        lambda **kwargs: _fake_forecast_for_store(kwargs["store_id"], kwargs["horizon_days"]),
    )

    payload = scenario_service.run_scenario_v2(
        store_id=None,
        segment={"store_type": "a"},
        price_change_pct=0.0,
        promo_mode="as_is",
        weekend_open=True,
        school_holiday=0,
        demand_shift_pct=0.0,
        confidence_level=0.8,
        horizon_days=2,
        data_source_id=None,
    )

    assert payload["target"]["mode"] == "segment"
    assert payload["target"]["stores_count"] == 2
    assert len(payload["points"]) == 2
    assert payload["summary"]["total_baseline_sales"] > 0


def test_scenario_v2_requires_exactly_one_target():
    with pytest.raises(ValueError, match="Use either store_id or segment"):
        scenario_service.run_scenario_v2(
            store_id=1,
            segment={"store_type": "a"},
            price_change_pct=0.0,
            promo_mode="as_is",
            weekend_open=True,
            school_holiday=0,
            demand_shift_pct=0.0,
            confidence_level=0.8,
            horizon_days=2,
            data_source_id=None,
        )
