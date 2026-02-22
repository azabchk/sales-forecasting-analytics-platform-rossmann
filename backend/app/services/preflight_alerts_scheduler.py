from __future__ import annotations

import logging
import os
import socket
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.preflight_alerts_service import AUDIT_ACTOR_SCHEDULER, run_alert_evaluation
from app.services.preflight_notifications_service import run_notification_dispatch

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except Exception:  # noqa: BLE001
    AsyncIOScheduler = None  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.preflight_alert_registry import (  # noqa: E402
    acquire_scheduler_lease,
    release_scheduler_lease,
)

logger = logging.getLogger("preflight.alerts.scheduler")

DEFAULT_LEASE_NAME = "preflight_alerts_scheduler"
DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_NOTIFICATIONS_INTERVAL_SECONDS = 30


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, min_value: int = 1) -> int:
    raw = str(os.getenv(name, str(default))).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(min_value, value)


def _default_owner_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


@dataclass
class PreflightAlertsScheduler:
    enabled: bool
    auto_start: bool
    interval_seconds: int
    notifications_enabled: bool
    notifications_interval_seconds: int
    lease_enabled: bool
    lease_name: str
    owner_id: str

    def __post_init__(self) -> None:
        self._scheduler: Any | None = None
        self._is_running = False

    @classmethod
    def from_env(cls) -> "PreflightAlertsScheduler":
        return cls(
            enabled=_env_bool("PREFLIGHT_ALERTS_SCHEDULER_ENABLED", True),
            auto_start=_env_bool("PREFLIGHT_ALERTS_SCHEDULER_AUTO_START", True),
            interval_seconds=_env_int(
                "PREFLIGHT_ALERTS_SCHEDULER_INTERVAL_SECONDS",
                DEFAULT_INTERVAL_SECONDS,
                min_value=1,
            ),
            notifications_enabled=_env_bool("PREFLIGHT_NOTIFICATIONS_SCHEDULER_ENABLED", True),
            notifications_interval_seconds=_env_int(
                "PREFLIGHT_NOTIFICATIONS_INTERVAL_SECONDS",
                DEFAULT_NOTIFICATIONS_INTERVAL_SECONDS,
                min_value=1,
            ),
            lease_enabled=_env_bool("PREFLIGHT_ALERTS_SCHEDULER_LEASE_ENABLED", True),
            lease_name=str(os.getenv("PREFLIGHT_ALERTS_SCHEDULER_LEASE_NAME", DEFAULT_LEASE_NAME)).strip()
            or DEFAULT_LEASE_NAME,
            owner_id=_default_owner_id(),
        )

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> bool:
        if self._is_running:
            return True

        if not self.enabled:
            logger.info("Preflight alerts scheduler disabled (PREFLIGHT_ALERTS_SCHEDULER_ENABLED=0).")
            return False

        if not self.auto_start:
            logger.info("Preflight alerts scheduler auto-start disabled (PREFLIGHT_ALERTS_SCHEDULER_AUTO_START=0).")
            return False

        if AsyncIOScheduler is None:
            logger.warning(
                "APScheduler not installed; preflight alerts scheduler is disabled. "
                "Install APScheduler to enable periodic evaluation."
            )
            return False

        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(
            self._run_tick,
            trigger="interval",
            seconds=self.interval_seconds,
            id="preflight_alerts_scheduler_tick",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=max(15, self.interval_seconds),
        )
        if self.notifications_enabled:
            scheduler.add_job(
                self._run_notifications_tick,
                trigger="interval",
                seconds=self.notifications_interval_seconds,
                id="preflight_notifications_scheduler_tick",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=max(15, self.notifications_interval_seconds),
            )
        scheduler.start()

        self._scheduler = scheduler
        self._is_running = True
        logger.info(
            "Preflight alerts scheduler started interval_seconds=%s notifications_enabled=%s notifications_interval_seconds=%s "
            "lease_enabled=%s lease_name=%s owner_id=%s",
            self.interval_seconds,
            self.notifications_enabled,
            self.notifications_interval_seconds,
            self.lease_enabled,
            self.lease_name,
            self.owner_id,
        )
        return True

    def shutdown(self) -> None:
        if self._scheduler is not None:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to shutdown preflight alerts scheduler cleanly: %s", exc)
            finally:
                self._scheduler = None

        if self.lease_enabled and self.lease_name:
            for lease_name in (f"{self.lease_name}:alerts", f"{self.lease_name}:notifications"):
                try:
                    release_scheduler_lease(lease_name=lease_name, owner_id=self.owner_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to release scheduler lease lease_name=%s: %s", lease_name, exc)

        if self._is_running:
            logger.info("Preflight alerts scheduler stopped owner_id=%s", self.owner_id)
        self._is_running = False

    def _try_acquire_lease(self, *, lease_name: str, tick_started_at: datetime, interval_seconds: int) -> bool:
        if not self.lease_enabled:
            return True

        lease_ttl_seconds = max(interval_seconds * 2, 30)
        try:
            return acquire_scheduler_lease(
                lease_name=lease_name,
                owner_id=self.owner_id,
                lease_ttl_seconds=lease_ttl_seconds,
                now=tick_started_at,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scheduler lease check failed lease_name=%s: %s", self.lease_name, exc)
            return False

    def _run_tick(self) -> None:
        tick_started_at = datetime.now(timezone.utc)
        if not self._try_acquire_lease(
            lease_name=f"{self.lease_name}:alerts",
            tick_started_at=tick_started_at,
            interval_seconds=self.interval_seconds,
        ):
            logger.debug(
                "Preflight alerts scheduler tick skipped (lease not acquired) lease_name=%s owner_id=%s",
                self.lease_name,
                self.owner_id,
            )
            return

        try:
            summary = run_alert_evaluation(audit_actor=AUDIT_ACTOR_SCHEDULER)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Preflight alerts scheduler tick failed: %s", exc)
            return

        logger.info(
            "Preflight alerts scheduler tick completed evaluated_at=%s total_policies=%s active_count=%s",
            summary.get("evaluated_at"),
            summary.get("total_policies"),
            summary.get("active_count"),
        )

    def _run_notifications_tick(self) -> None:
        tick_started_at = datetime.now(timezone.utc)
        if not self._try_acquire_lease(
            lease_name=f"{self.lease_name}:notifications",
            tick_started_at=tick_started_at,
            interval_seconds=self.notifications_interval_seconds,
        ):
            logger.debug(
                "Preflight notifications scheduler tick skipped (lease not acquired) lease_name=%s owner_id=%s",
                f"{self.lease_name}:notifications",
                self.owner_id,
            )
            return

        try:
            summary = run_notification_dispatch(
                limit=_env_int("PREFLIGHT_NOTIFICATIONS_DISPATCH_BATCH_SIZE", 50, min_value=1),
                actor=AUDIT_ACTOR_SCHEDULER,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Preflight notifications scheduler tick failed: %s", exc)
            return

        logger.info(
            "Preflight notifications scheduler tick completed processed=%s sent=%s retrying=%s dead=%s",
            summary.get("processed_count"),
            summary.get("sent_count"),
            summary.get("retrying_count"),
            summary.get("dead_count"),
        )
