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
import { SmartColumn, SmartTable } from "../components/ui/DataTable";
import { ErrorState, LoadingState } from "../components/ui/States";
import StatusBadge from "../components/StatusBadge";
import { useI18n } from "../lib/i18n";

function formatDateTime(value: string | null | undefined, localeTag: string): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
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
  const [statusFilter, setStatusFilter] = React.useState("");

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [alertsRes, endpointsRes, deliveriesRes] = await Promise.all([
        fetchPreflightActiveAlerts(),
        fetchNotificationEndpoints(),
        fetchNotificationDeliveries({ page: 1, page_size: 200, status: statusFilter || undefined }),
      ]);
      setAlerts(alertsRes);
      setEndpoints(endpointsRes);
      setDeliveries(deliveriesRes);
    } catch (err) {
      setError(extractApiError(err, locale === "ru"
        ? "Не удалось загрузить уведомления. Проверьте diagnostics API key."
        : "Failed to load notifications. Check diagnostics API key and permissions."));
    } finally {
      setLoading(false);
    }
  }, [locale, statusFilter]);

  React.useEffect(() => { loadData(); }, [loadData]);

  const alertColumns: SmartColumn<Record<string, unknown>>[] = [
    { key: "alert_id", label: "Alert ID", sortable: true, searchable: true, render: (v) => <span className="mono-small">{String(v ?? "")}</span> },
    { key: "severity", label: "Severity", sortable: true, render: (v) => <StatusBadge status={String(v ?? "")} /> },
    { key: "status", label: locale === "ru" ? "Статус" : "Status", sortable: true, render: (v) => <StatusBadge status={String(v ?? "")} /> },
    { key: "source_name", label: locale === "ru" ? "Источник" : "Source", sortable: true, render: (v) => String(v ?? "-") },
    { key: "last_seen_at", label: locale === "ru" ? "Последний триггер" : "Last Trigger", sortable: true, render: (v) => formatDateTime(v as string, localeTag) },
  ];

  const endpointColumns: SmartColumn<Record<string, unknown>>[] = [
    { key: "id", label: "ID", sortable: true, render: (v) => <span className="mono-small">{String(v ?? "")}</span> },
    { key: "channel_type", label: locale === "ru" ? "Канал" : "Channel", sortable: true },
    { key: "enabled", label: locale === "ru" ? "Включен" : "Enabled", render: (v) => <StatusBadge status={v ? "PASS" : "SKIPPED"} /> },
    { key: "target_hint", label: "Endpoint", render: (v) => String(v ?? "-") },
    { key: "max_attempts", label: locale === "ru" ? "Попытки" : "Attempts", sortable: true },
  ];

  const deliveryColumns: SmartColumn<Record<string, unknown>>[] = [
    { key: "attempt_id", label: "Attempt ID", searchable: true, render: (v) => <span className="mono-small">{String(v ?? "")}</span> },
    { key: "channel_target", label: locale === "ru" ? "Канал" : "Channel", sortable: true },
    { key: "attempt_status", label: locale === "ru" ? "Статус" : "Status", sortable: true, render: (v) => <StatusBadge status={String(v ?? "")} /> },
    { key: "http_status", label: "HTTP", sortable: true, render: (v) => String(v ?? "-") },
    { key: "error_message_safe", label: locale === "ru" ? "Ошибка" : "Error", render: (v) => String(v ?? "-") },
    { key: "started_at", label: locale === "ru" ? "Время" : "Started", sortable: true, render: (v) => formatDateTime(v as string, localeTag) },
  ];

  return (
    <PageLayout
      title={locale === "ru" ? "Уведомления и алерты" : "Notifications & Alerts"}
      subtitle={locale === "ru"
        ? "Активные алерты, webhook-конфигурации и история доставок."
        : "Active alerts, webhook endpoint registry, and delivery telemetry."}
      actions={
        <button className="button primary" type="button" onClick={loadData} disabled={loading}>
          {loading ? (locale === "ru" ? "Обновление..." : "Refreshing...") : locale === "ru" ? "Обновить" : "Refresh"}
        </button>
      }
    >
      {error ? <ErrorState message={error} onRetry={loadData} /> : null}
      {loading && !alerts ? <LoadingState lines={4} /> : null}

      <Card
        title={locale === "ru" ? "Активные алерты" : "Active Alerts"}
        subtitle={locale === "ru" ? "Текущие firing/pending алерты" : "Current firing and pending alerts"}
      >
        <SmartTable
          columns={alertColumns}
          data={(alerts?.items ?? []) as Record<string, unknown>[]}
          pageSize={20}
          searchable
          rowKeyField="alert_id"
          emptyMessage={locale === "ru" ? "Активных алертов нет." : "No active alerts."}
        />
      </Card>

      <Card
        title={locale === "ru" ? "Webhook endpoints" : "Webhook Endpoints"}
        subtitle={locale === "ru" ? "Санитизированный список каналов доставки" : "Sanitized channel endpoints list"}
      >
        <SmartTable
          columns={endpointColumns}
          data={(endpoints?.items ?? []) as Record<string, unknown>[]}
          pageSize={10}
          rowKeyField="id"
          emptyMessage={locale === "ru" ? "Каналы не настроены." : "No channels configured."}
        />
      </Card>

      <Card
        title={locale === "ru" ? "История доставок" : "Delivery History"}
        subtitle={locale === "ru" ? "Immutable ledger попыток доставки" : "Immutable delivery attempt ledger"}
        actions={
          <div className="controls compact">
            <label htmlFor="delivery-status-filter">{locale === "ru" ? "Статус:" : "Status:"}</label>
            <select
              id="delivery-status-filter"
              className="select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              {DELIVERY_STATUS_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>{opt || (locale === "ru" ? "Все" : "All")}</option>
              ))}
            </select>
          </div>
        }
      >
        <SmartTable
          columns={deliveryColumns}
          data={(deliveries?.items ?? []) as Record<string, unknown>[]}
          pageSize={25}
          searchable
          searchPlaceholder={locale === "ru" ? "Поиск по attempt ID..." : "Search by attempt ID…"}
          rowKeyField="attempt_id"
          emptyMessage={locale === "ru" ? "История доставок пуста." : "No delivery attempts found."}
        />
      </Card>
    </PageLayout>
  );
}
