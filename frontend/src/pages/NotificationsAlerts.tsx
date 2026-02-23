import React from "react";

import { extractApiError } from "../api/client";
import {
  fetchNotificationDeliveries,
  fetchNotificationEndpoints,
  fetchPreflightActiveAlerts,
  NotificationDeliveryPage,
  NotificationEndpointsResponse,
  PreflightActiveAlertsResponse,
} from "../api/endpoints";
import PageLayout from "../components/layout/PageLayout";
import Card from "../components/ui/Card";
import DataTable from "../components/ui/DataTable";
import { ErrorState, LoadingState } from "../components/ui/States";
import StatusBadge from "../components/StatusBadge";
import { useI18n } from "../lib/i18n";

function formatDateTime(value: string | null | undefined, localeTag: string): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(localeTag, { dateStyle: "medium", timeStyle: "short" });
}

const DELIVERY_STATUS_OPTIONS = ["", "SENT", "DEAD", "FAILED", "RETRY", "STARTED"];

export default function NotificationsAlertsPage() {
  const { locale, localeTag } = useI18n();
  const [alerts, setAlerts] = React.useState<PreflightActiveAlertsResponse | null>(null);
  const [endpoints, setEndpoints] = React.useState<NotificationEndpointsResponse | null>(null);
  const [deliveries, setDeliveries] = React.useState<NotificationDeliveryPage | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [status, setStatus] = React.useState("");

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [alertsResponse, endpointsResponse, deliveriesResponse] = await Promise.all([
        fetchPreflightActiveAlerts(),
        fetchNotificationEndpoints(),
        fetchNotificationDeliveries({ page, page_size: 20, status: status || undefined }),
      ]);
      setAlerts(alertsResponse);
      setEndpoints(endpointsResponse);
      setDeliveries(deliveriesResponse);
    } catch (errorResponse) {
      setError(
        extractApiError(
          errorResponse,
          locale === "ru"
            ? "Не удалось загрузить раздел уведомлений. Проверьте diagnostics API key."
            : "Failed to load notifications. Check diagnostics API key and permissions."
        )
      );
    } finally {
      setLoading(false);
    }
  }, [locale, page, status]);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  const totalPages = deliveries ? Math.max(1, Math.ceil(deliveries.total / deliveries.page_size)) : 1;

  return (
    <PageLayout
      title={locale === "ru" ? "Уведомления и алерты" : "Notifications & Alerts"}
      subtitle={
        locale === "ru"
          ? "Активные алерты, webhook-конфигурации и история доставок."
          : "Active alerts, webhook endpoint registry, and delivery telemetry."
      }
      actions={
        <button className="button primary" type="button" onClick={loadData} disabled={loading}>
          {loading ? (locale === "ru" ? "Обновление..." : "Refreshing...") : locale === "ru" ? "Обновить" : "Refresh"}
        </button>
      }
    >
      {error ? <ErrorState message={error} /> : null}
      {loading && !alerts && !endpoints && !deliveries ? <LoadingState lines={4} /> : null}

      <Card
        title={locale === "ru" ? "Активные алерты" : "Active Alerts"}
        subtitle={locale === "ru" ? "Текущие firing/pending алерты" : "Current firing and pending alerts"}
      >
        <DataTable>
          <thead>
            <tr>
              <th>{locale === "ru" ? "Alert ID" : "Alert ID"}</th>
              <th>{locale === "ru" ? "Severity" : "Severity"}</th>
              <th>{locale === "ru" ? "Статус" : "Status"}</th>
              <th>{locale === "ru" ? "Источник" : "Source"}</th>
              <th>{locale === "ru" ? "Последний триггер" : "Last Trigger"}</th>
            </tr>
          </thead>
          <tbody>
            {(alerts?.items ?? []).map((item) => (
              <tr key={item.alert_id}>
                <td className="mono-small">{item.alert_id}</td>
                <td><StatusBadge status={item.severity} /></td>
                <td><StatusBadge status={item.status} /></td>
                <td>{item.source_name ?? "-"}</td>
                <td>{formatDateTime(item.last_seen_at, localeTag)}</td>
              </tr>
            ))}
            {(alerts?.items ?? []).length === 0 ? (
              <tr>
                <td colSpan={5}>
                  {locale === "ru" ? "Активных алертов нет." : "No active alerts."}
                </td>
              </tr>
            ) : null}
          </tbody>
        </DataTable>
      </Card>

      <Card
        title={locale === "ru" ? "Webhook endpoints" : "Webhook Endpoints"}
        subtitle={locale === "ru" ? "Санитизированный список каналов доставки" : "Sanitized channel endpoints list"}
      >
        <DataTable>
          <thead>
            <tr>
              <th>ID</th>
              <th>{locale === "ru" ? "Канал" : "Channel"}</th>
              <th>{locale === "ru" ? "Включен" : "Enabled"}</th>
              <th>{locale === "ru" ? "Endpoint" : "Endpoint"}</th>
              <th>{locale === "ru" ? "Попытки" : "Attempts"}</th>
            </tr>
          </thead>
          <tbody>
            {(endpoints?.items ?? []).map((endpoint) => (
              <tr key={endpoint.id}>
                <td className="mono-small">{endpoint.id}</td>
                <td>{endpoint.channel_type}</td>
                <td><StatusBadge status={endpoint.enabled ? "PASS" : "SKIPPED"} /></td>
                <td>{endpoint.target_hint ?? "-"}</td>
                <td>{endpoint.max_attempts}</td>
              </tr>
            ))}
            {(endpoints?.items ?? []).length === 0 ? (
              <tr>
                <td colSpan={5}>
                  {locale === "ru" ? "Каналы не настроены." : "No channels configured."}
                </td>
              </tr>
            ) : null}
          </tbody>
        </DataTable>
      </Card>

      <Card
        title={locale === "ru" ? "История доставок" : "Delivery History"}
        subtitle={locale === "ru" ? "Immutable ledger попыток доставки" : "Immutable delivery attempt ledger"}
        actions={
          <div className="controls compact">
            <div className="field">
              <label htmlFor="delivery-status">{locale === "ru" ? "Статус" : "Status"}</label>
              <select
                id="delivery-status"
                className="select"
                value={status}
                onChange={(event) => {
                  setPage(1);
                  setStatus(event.target.value);
                }}
              >
                {DELIVERY_STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option || (locale === "ru" ? "Все" : "All")}
                  </option>
                ))}
              </select>
            </div>
          </div>
        }
      >
        <DataTable>
          <thead>
            <tr>
              <th>{locale === "ru" ? "Attempt ID" : "Attempt ID"}</th>
              <th>{locale === "ru" ? "Канал" : "Channel"}</th>
              <th>{locale === "ru" ? "Статус" : "Status"}</th>
              <th>{locale === "ru" ? "HTTP" : "HTTP"}</th>
              <th>{locale === "ru" ? "Ошибка" : "Error"}</th>
              <th>{locale === "ru" ? "Время" : "Started"}</th>
            </tr>
          </thead>
          <tbody>
            {(deliveries?.items ?? []).map((item) => (
              <tr key={item.attempt_id}>
                <td className="mono-small">{item.attempt_id}</td>
                <td>{item.channel_target}</td>
                <td><StatusBadge status={item.attempt_status} /></td>
                <td>{item.http_status ?? "-"}</td>
                <td>{item.error_message_safe ?? "-"}</td>
                <td>{formatDateTime(item.started_at, localeTag)}</td>
              </tr>
            ))}
            {(deliveries?.items ?? []).length === 0 ? (
              <tr>
                <td colSpan={6}>
                  {locale === "ru" ? "История доставок пуста." : "No delivery attempts found."}
                </td>
              </tr>
            ) : null}
          </tbody>
        </DataTable>
        <div className="pagination-row">
          <button
            type="button"
            className="button ghost"
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            disabled={page <= 1 || loading}
          >
            {locale === "ru" ? "Назад" : "Prev"}
          </button>
          <p className="muted">
            {locale === "ru" ? "Страница" : "Page"} {page} / {totalPages}
          </p>
          <button
            type="button"
            className="button ghost"
            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
            disabled={page >= totalPages || loading}
          >
            {locale === "ru" ? "Вперед" : "Next"}
          </button>
        </div>
      </Card>
    </PageLayout>
  );
}
