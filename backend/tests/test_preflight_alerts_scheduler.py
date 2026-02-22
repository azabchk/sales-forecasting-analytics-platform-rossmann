from __future__ import annotations

from app.services.preflight_alerts_scheduler import PreflightAlertsScheduler


def test_scheduler_disabled_via_env(monkeypatch):
    monkeypatch.setenv("PREFLIGHT_ALERTS_SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("PREFLIGHT_ALERTS_SCHEDULER_AUTO_START", "1")

    scheduler = PreflightAlertsScheduler.from_env()
    started = scheduler.start()
    assert started is False
    assert scheduler.is_running is False
    scheduler.shutdown()


def test_scheduler_handles_missing_apscheduler(monkeypatch):
    monkeypatch.setenv("PREFLIGHT_ALERTS_SCHEDULER_ENABLED", "1")
    monkeypatch.setenv("PREFLIGHT_ALERTS_SCHEDULER_AUTO_START", "1")
    monkeypatch.setenv("PREFLIGHT_ALERTS_SCHEDULER_INTERVAL_SECONDS", "10")

    scheduler = PreflightAlertsScheduler.from_env()
    started = scheduler.start()
    assert started is False
    assert scheduler.is_running is False
    scheduler.shutdown()
