from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse

from app.security.diagnostics_auth import (
    SCOPE_ADMIN,
    SCOPE_READ,
    DiagnosticsPrincipal,
    authenticate_diagnostics_principal,
    require_scope,
)
from app.services.metrics_export_service import render_prometheus_metrics
from app.schemas import (
    NotificationDeliveryPageResponse,
    NotificationEndpointsResponse,
    PreflightAcknowledgeAlertRequest,
    PreflightActiveAlertsResponse,
    PreflightAlertAcknowledgementResponse,
    PreflightAlertAuditResponse,
    PreflightAlertEvaluationResponse,
    PreflightAlertHistoryResponse,
    PreflightAlertPoliciesResponse,
    PreflightAlertSilenceResponse,
    PreflightCreateSilenceRequest,
    PreflightArtifactType,
    PreflightManifestArtifactResponse,
    PreflightNotificationChannelsResponse,
    PreflightNotificationDispatchResponse,
    PreflightNotificationAttemptItemResponse,
    PreflightNotificationAttemptsResponse,
    PreflightNotificationReplayResponse,
    PreflightNotificationStatsResponse,
    PreflightNotificationTrendsResponse,
    PreflightNotificationOutboxResponse,
    PreflightSilencesResponse,
    PreflightRunDetailResponse,
    PreflightRunsListResponse,
    PreflightRunSummary,
    PreflightSemanticArtifactResponse,
    PreflightSourceArtifactsResponse,
    PreflightStatsResponse,
    PreflightTopRulesResponse,
    PreflightTrendsResponse,
    PreflightValidationArtifactResponse,
)
from app.services.diagnostics_service import (
    DiagnosticsAccessError,
    DiagnosticsNotFoundError,
    DiagnosticsPayloadError,
    get_latest_preflight_for_source,
    get_latest_preflight_run,
    get_preflight_stats,
    get_preflight_source_artifact_download,
    get_preflight_source_artifacts,
    get_preflight_source_manifest,
    get_preflight_source_semantic,
    get_preflight_source_validation,
    get_preflight_top_rules,
    get_preflight_trends,
    get_preflight_run_details,
    list_preflight_run_summaries,
)
from app.services.preflight_alerts_service import (
    acknowledge_alert,
    create_silence,
    expire_silence_by_id,
    get_active_alerts,
    get_alert_history,
    list_alert_audit,
    list_alert_policies,
    list_silences,
    run_alert_evaluation,
    unacknowledge_alert,
)
from app.services.preflight_notifications_service import (
    get_notification_attempt_details,
    get_notification_attempts,
    get_notification_channels,
    get_notification_deliveries,
    get_notification_endpoints,
    get_notification_history,
    get_notification_outbox,
    get_notification_stats,
    get_notification_trends,
    replay_dead_notification_outbox,
    replay_notification_outbox_item,
    run_notification_dispatch,
)

router = APIRouter()


def _metrics_auth_disabled() -> bool:
    raw = str(os.getenv("DIAGNOSTICS_METRICS_AUTH_DISABLED", "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


async def _require_metrics_scope(request: Request) -> DiagnosticsPrincipal | None:
    if _metrics_auth_disabled():
        return None

    principal = await authenticate_diagnostics_principal(
        request,
        api_key=request.headers.get("X-API-Key"),
    )
    scopes = {str(scope).strip() for scope in principal.scopes}
    if SCOPE_READ in scopes or SCOPE_ADMIN in scopes:
        return principal

    raise HTTPException(
        status_code=403,
        detail=f"Insufficient scope. Required '{SCOPE_READ}' for diagnostics metrics endpoint.",
    )


@router.get("/diagnostics/metrics")
async def diagnostics_metrics(
    _principal: DiagnosticsPrincipal | None = Depends(_require_metrics_scope),
) -> Response:
    payload = render_prometheus_metrics()
    return Response(
        content=payload,
        media_type="text/plain",
        headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
    )


@router.get("/diagnostics/preflight/runs", response_model=PreflightRunsListResponse)
def diagnostics_preflight_runs(
    limit: int = Query(20, ge=1, le=100),
    source_name: Literal["train", "store"] | None = Query(default=None),
    data_source_id: int | None = Query(default=None, gt=0),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightRunsListResponse:
    try:
        items = list_preflight_run_summaries(limit=limit, source_name=source_name, data_source_id=data_source_id)
        return PreflightRunsListResponse(items=items, limit=limit, source_name=source_name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc


@router.get("/diagnostics/preflight/runs/{run_id}", response_model=PreflightRunDetailResponse)
def diagnostics_preflight_run_details(
    run_id: str,
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightRunDetailResponse:
    try:
        payload = get_preflight_run_details(run_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc

    if payload is None:
        raise HTTPException(status_code=404, detail=f"Preflight run not found: {run_id}")
    return PreflightRunDetailResponse.model_validate(payload)


@router.get("/diagnostics/preflight/latest", response_model=PreflightRunDetailResponse)
def diagnostics_preflight_latest(
    data_source_id: int | None = Query(default=None, gt=0),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightRunDetailResponse:
    try:
        payload = get_latest_preflight_run(data_source_id=data_source_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc

    if payload is None:
        raise HTTPException(status_code=404, detail="No preflight runs found")
    return PreflightRunDetailResponse.model_validate(payload)


@router.get("/diagnostics/preflight/latest/{source_name}", response_model=PreflightRunSummary)
def diagnostics_preflight_latest_by_source(
    source_name: Literal["train", "store"],
    data_source_id: int | None = Query(default=None, gt=0),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightRunSummary:
    try:
        payload = get_latest_preflight_for_source(source_name, data_source_id=data_source_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc

    if payload is None:
        raise HTTPException(status_code=404, detail=f"No preflight runs found for source '{source_name}'")
    return PreflightRunSummary.model_validate(payload)


@router.get("/diagnostics/preflight/stats", response_model=PreflightStatsResponse)
def diagnostics_preflight_stats(
    source_name: Literal["train", "store"] | None = Query(default=None),
    data_source_id: int | None = Query(default=None, gt=0),
    mode: Literal["off", "report_only", "enforce"] | None = Query(default=None),
    final_status: Literal["PASS", "WARN", "FAIL"] | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=3650),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightStatsResponse:
    try:
        payload = get_preflight_stats(
            source_name=source_name,
            data_source_id=data_source_id,
            mode=mode,
            final_status=final_status,
            date_from=date_from,
            date_to=date_to,
            days=days,
        )
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightStatsResponse.model_validate(payload)


@router.get("/diagnostics/preflight/trends", response_model=PreflightTrendsResponse)
def diagnostics_preflight_trends(
    source_name: Literal["train", "store"] | None = Query(default=None),
    data_source_id: int | None = Query(default=None, gt=0),
    mode: Literal["off", "report_only", "enforce"] | None = Query(default=None),
    final_status: Literal["PASS", "WARN", "FAIL"] | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=3650),
    bucket: Literal["day", "hour"] = Query(default="day"),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightTrendsResponse:
    try:
        payload = get_preflight_trends(
            source_name=source_name,
            data_source_id=data_source_id,
            mode=mode,
            final_status=final_status,
            date_from=date_from,
            date_to=date_to,
            days=days,
            bucket=bucket,
        )
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightTrendsResponse.model_validate(payload)


@router.get("/diagnostics/preflight/rules/top", response_model=PreflightTopRulesResponse)
def diagnostics_preflight_rules_top(
    source_name: Literal["train", "store"] | None = Query(default=None),
    data_source_id: int | None = Query(default=None, gt=0),
    mode: Literal["off", "report_only", "enforce"] | None = Query(default=None),
    final_status: Literal["PASS", "WARN", "FAIL"] | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=3650),
    limit: int = Query(default=10, ge=1, le=100),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightTopRulesResponse:
    try:
        payload = get_preflight_top_rules(
            source_name=source_name,
            data_source_id=data_source_id,
            mode=mode,
            final_status=final_status,
            date_from=date_from,
            date_to=date_to,
            days=days,
            limit=limit,
        )
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightTopRulesResponse.model_validate(payload)


@router.get("/diagnostics/preflight/alerts/active", response_model=PreflightActiveAlertsResponse)
def diagnostics_preflight_alerts_active(
    auto_evaluate: bool = Query(default=False),
    principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightActiveAlertsResponse:
    try:
        payload = get_active_alerts(auto_evaluate=auto_evaluate, evaluation_actor=principal.actor)
    except (DiagnosticsPayloadError, DiagnosticsNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightActiveAlertsResponse.model_validate(payload)


@router.get("/diagnostics/preflight/alerts/history", response_model=PreflightAlertHistoryResponse)
def diagnostics_preflight_alerts_history(
    limit: int = Query(default=50, ge=1, le=500),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightAlertHistoryResponse:
    try:
        payload = get_alert_history(limit=limit)
    except (DiagnosticsPayloadError, DiagnosticsNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightAlertHistoryResponse.model_validate(payload)


@router.get("/diagnostics/preflight/alerts/policies", response_model=PreflightAlertPoliciesResponse)
def diagnostics_preflight_alerts_policies(
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightAlertPoliciesResponse:
    try:
        payload = list_alert_policies()
    except (DiagnosticsPayloadError, DiagnosticsNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightAlertPoliciesResponse.model_validate(payload)


@router.get("/diagnostics/preflight/alerts/silences", response_model=PreflightSilencesResponse)
def diagnostics_preflight_alerts_silences(
    limit: int = Query(default=100, ge=1, le=1000),
    include_expired: bool = Query(default=False),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightSilencesResponse:
    try:
        payload = list_silences(limit=limit, include_expired=include_expired)
    except (DiagnosticsPayloadError, DiagnosticsNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightSilencesResponse.model_validate(payload)


@router.post("/diagnostics/preflight/alerts/silences", response_model=PreflightAlertSilenceResponse)
def diagnostics_preflight_alerts_create_silence(
    payload: PreflightCreateSilenceRequest,
    principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:operate")),
) -> PreflightAlertSilenceResponse:
    try:
        response_payload = create_silence(
            actor=principal.actor,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            reason=payload.reason,
            policy_id=payload.policy_id,
            source_name=payload.source_name,
            severity=payload.severity,
            rule_id=payload.rule_id,
        )
    except (DiagnosticsPayloadError, DiagnosticsNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightAlertSilenceResponse.model_validate(response_payload)


@router.post("/diagnostics/preflight/alerts/silences/{silence_id}/expire", response_model=PreflightAlertSilenceResponse)
def diagnostics_preflight_alerts_expire_silence(
    silence_id: str,
    principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:operate")),
) -> PreflightAlertSilenceResponse:
    try:
        response_payload = expire_silence_by_id(silence_id=silence_id, actor=principal.actor)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightAlertSilenceResponse.model_validate(response_payload)


@router.post("/diagnostics/preflight/alerts/{alert_id}/ack", response_model=PreflightAlertAcknowledgementResponse)
def diagnostics_preflight_alerts_ack(
    alert_id: str,
    payload: PreflightAcknowledgeAlertRequest,
    principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:operate")),
) -> PreflightAlertAcknowledgementResponse:
    try:
        response_payload = acknowledge_alert(alert_id=alert_id, actor=principal.actor, note=payload.note)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightAlertAcknowledgementResponse.model_validate(response_payload)


@router.post("/diagnostics/preflight/alerts/{alert_id}/unack", response_model=PreflightAlertAcknowledgementResponse)
def diagnostics_preflight_alerts_unack(
    alert_id: str,
    principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:operate")),
) -> PreflightAlertAcknowledgementResponse:
    try:
        response_payload = unacknowledge_alert(alert_id=alert_id, actor=principal.actor)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightAlertAcknowledgementResponse.model_validate(response_payload)


@router.get("/diagnostics/preflight/alerts/audit", response_model=PreflightAlertAuditResponse)
def diagnostics_preflight_alerts_audit(
    limit: int = Query(default=50, ge=1, le=500),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightAlertAuditResponse:
    try:
        payload = list_alert_audit(limit=limit)
    except (DiagnosticsPayloadError, DiagnosticsNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightAlertAuditResponse.model_validate(payload)


@router.post("/diagnostics/preflight/alerts/evaluate", response_model=PreflightAlertEvaluationResponse)
def diagnostics_preflight_alerts_evaluate(
    principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:admin")),
) -> PreflightAlertEvaluationResponse:
    if str(os.getenv("PREFLIGHT_ALERTS_ALLOW_EVALUATE", "0")).strip().lower() not in {"1", "true", "yes"}:
        raise HTTPException(
            status_code=403,
            detail="Manual alert evaluation is disabled. Set PREFLIGHT_ALERTS_ALLOW_EVALUATE=1 for local demo usage.",
        )
    try:
        payload = run_alert_evaluation(audit_actor=principal.actor)
    except (DiagnosticsPayloadError, DiagnosticsNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightAlertEvaluationResponse.model_validate(payload)


@router.get("/diagnostics/preflight/notifications/outbox", response_model=PreflightNotificationOutboxResponse)
def diagnostics_preflight_notifications_outbox(
    limit: int = Query(default=50, ge=1, le=1000),
    status: str | None = Query(default=None),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightNotificationOutboxResponse:
    try:
        payload = get_notification_outbox(limit=limit, status=status)
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightNotificationOutboxResponse.model_validate(payload)


@router.get("/diagnostics/preflight/notifications/history", response_model=PreflightNotificationOutboxResponse)
def diagnostics_preflight_notifications_history(
    limit: int = Query(default=50, ge=1, le=1000),
    status: str | None = Query(default=None),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightNotificationOutboxResponse:
    try:
        payload = get_notification_history(limit=limit, status=status)
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightNotificationOutboxResponse.model_validate(payload)


@router.get("/diagnostics/preflight/notifications/stats", response_model=PreflightNotificationStatsResponse)
def diagnostics_preflight_notifications_stats(
    days: int | None = Query(default=None, ge=1, le=3650),
    event_type: str | None = Query(default=None),
    channel_target: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightNotificationStatsResponse:
    try:
        payload = get_notification_stats(
            days=days,
            event_type=event_type,
            channel_target=channel_target,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightNotificationStatsResponse.model_validate(payload)


@router.get("/diagnostics/preflight/notifications/trends", response_model=PreflightNotificationTrendsResponse)
def diagnostics_preflight_notifications_trends(
    days: int | None = Query(default=None, ge=1, le=3650),
    event_type: str | None = Query(default=None),
    channel_target: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    bucket: Literal["day", "hour"] = Query(default="day"),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightNotificationTrendsResponse:
    try:
        payload = get_notification_trends(
            days=days,
            event_type=event_type,
            channel_target=channel_target,
            status=status,
            date_from=date_from,
            date_to=date_to,
            bucket=bucket,
        )
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightNotificationTrendsResponse.model_validate(payload)


@router.get("/diagnostics/preflight/notifications/channels", response_model=PreflightNotificationChannelsResponse)
def diagnostics_preflight_notifications_channels(
    days: int | None = Query(default=None, ge=1, le=3650),
    event_type: str | None = Query(default=None),
    channel_target: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightNotificationChannelsResponse:
    try:
        payload = get_notification_channels(
            days=days,
            event_type=event_type,
            channel_target=channel_target,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightNotificationChannelsResponse.model_validate(payload)


@router.get(
    "/diagnostics/preflight/notifications/endpoints",
    response_model=NotificationEndpointsResponse,
)
def diagnostics_preflight_notifications_endpoints(
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> NotificationEndpointsResponse:
    try:
        payload = get_notification_endpoints()
    except (DiagnosticsPayloadError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return NotificationEndpointsResponse.model_validate(payload)


@router.get(
    "/diagnostics/preflight/notifications/deliveries",
    response_model=NotificationDeliveryPageResponse,
)
def diagnostics_preflight_notifications_deliveries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    status: str | None = Query(default=None),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> NotificationDeliveryPageResponse:
    try:
        payload = get_notification_deliveries(page=page, page_size=page_size, status=status)
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return NotificationDeliveryPageResponse.model_validate(payload)


@router.get("/diagnostics/preflight/notifications/attempts", response_model=PreflightNotificationAttemptsResponse)
def diagnostics_preflight_notifications_attempts(
    limit: int = Query(default=100, ge=1, le=1000),
    days: int | None = Query(default=None, ge=1, le=3650),
    event_type: str | None = Query(default=None),
    channel_target: str | None = Query(default=None),
    attempt_status: str | None = Query(default=None),
    alert_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightNotificationAttemptsResponse:
    try:
        payload = get_notification_attempts(
            limit=limit,
            days=days,
            event_type=event_type,
            channel_target=channel_target,
            attempt_status=attempt_status,
            alert_id=alert_id,
            date_from=date_from,
            date_to=date_to,
        )
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightNotificationAttemptsResponse.model_validate(payload)


@router.get(
    "/diagnostics/preflight/notifications/attempts/{attempt_id}",
    response_model=PreflightNotificationAttemptItemResponse,
)
def diagnostics_preflight_notifications_attempt_detail(
    attempt_id: str,
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightNotificationAttemptItemResponse:
    try:
        payload = get_notification_attempt_details(attempt_id)
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc

    if payload is None:
        raise HTTPException(status_code=404, detail=f"Notification attempt not found: {attempt_id}")
    return PreflightNotificationAttemptItemResponse.model_validate(payload)


@router.post("/diagnostics/preflight/notifications/dispatch", response_model=PreflightNotificationDispatchResponse)
def diagnostics_preflight_notifications_dispatch(
    limit: int = Query(default=50, ge=1, le=1000),
    principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:admin")),
) -> PreflightNotificationDispatchResponse:
    try:
        payload = run_notification_dispatch(limit=limit, actor=principal.actor)
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightNotificationDispatchResponse.model_validate(payload)


@router.post(
    "/diagnostics/preflight/notifications/outbox/{item_id}/replay",
    response_model=PreflightNotificationReplayResponse,
)
def diagnostics_preflight_notifications_replay_item(
    item_id: str,
    principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:admin")),
) -> PreflightNotificationReplayResponse:
    try:
        payload = replay_notification_outbox_item(item_id=item_id, actor=principal.actor)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightNotificationReplayResponse.model_validate(payload)


@router.post(
    "/diagnostics/preflight/notifications/outbox/replay-dead",
    response_model=PreflightNotificationReplayResponse,
)
def diagnostics_preflight_notifications_replay_dead(
    limit: int = Query(default=50, ge=1, le=1000),
    principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:admin")),
) -> PreflightNotificationReplayResponse:
    try:
        payload = replay_dead_notification_outbox(limit=limit, actor=principal.actor)
    except (DiagnosticsPayloadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightNotificationReplayResponse.model_validate(payload)


@router.get(
    "/diagnostics/preflight/runs/{run_id}/sources/{source_name}/artifacts",
    response_model=PreflightSourceArtifactsResponse,
)
def diagnostics_preflight_source_artifacts(
    run_id: str,
    source_name: Literal["train", "store"],
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightSourceArtifactsResponse:
    try:
        payload = get_preflight_source_artifacts(run_id=run_id, source_name=source_name)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiagnosticsAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightSourceArtifactsResponse.model_validate(payload)


@router.get(
    "/diagnostics/preflight/runs/{run_id}/sources/{source_name}/validation",
    response_model=PreflightValidationArtifactResponse,
)
def diagnostics_preflight_source_validation(
    run_id: str,
    source_name: Literal["train", "store"],
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightValidationArtifactResponse:
    try:
        payload = get_preflight_source_validation(run_id=run_id, source_name=source_name)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiagnosticsAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightValidationArtifactResponse.model_validate(payload)


@router.get(
    "/diagnostics/preflight/runs/{run_id}/sources/{source_name}/semantic",
    response_model=PreflightSemanticArtifactResponse,
)
def diagnostics_preflight_source_semantic(
    run_id: str,
    source_name: Literal["train", "store"],
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightSemanticArtifactResponse:
    try:
        payload = get_preflight_source_semantic(run_id=run_id, source_name=source_name)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiagnosticsAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightSemanticArtifactResponse.model_validate(payload)


@router.get(
    "/diagnostics/preflight/runs/{run_id}/sources/{source_name}/manifest",
    response_model=PreflightManifestArtifactResponse,
)
def diagnostics_preflight_source_manifest(
    run_id: str,
    source_name: Literal["train", "store"],
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> PreflightManifestArtifactResponse:
    try:
        payload = get_preflight_source_manifest(run_id=run_id, source_name=source_name)
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiagnosticsAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc
    return PreflightManifestArtifactResponse.model_validate(payload)


@router.get("/diagnostics/preflight/runs/{run_id}/sources/{source_name}/download/{artifact_type}")
def diagnostics_preflight_source_download(
    run_id: str,
    source_name: Literal["train", "store"],
    artifact_type: PreflightArtifactType,
    _principal: DiagnosticsPrincipal = Depends(require_scope("diagnostics:read")),
) -> FileResponse:
    try:
        payload = get_preflight_source_artifact_download(
            run_id=run_id,
            source_name=source_name,
            artifact_type=artifact_type,
        )
    except DiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiagnosticsAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiagnosticsPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostics error: {exc}") from exc

    return FileResponse(
        path=payload["path"],
        media_type=payload["content_type"],
        filename=payload["file_name"],
    )
