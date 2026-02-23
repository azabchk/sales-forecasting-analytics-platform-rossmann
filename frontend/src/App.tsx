import React from "react";
import { Route, Routes } from "react-router-dom";

import { API_BASE_SOURCE, API_BASE_URL, extractApiError } from "./api/client";
import { fetchHealth } from "./api/endpoints";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";
import LoadingBlock from "./components/LoadingBlock";
import { useI18n } from "./lib/i18n";
import { useThemeMode } from "./lib/theme";

const Overview = React.lazy(async () => import("./pages/Overview"));
const StoreAnalytics = React.lazy(async () => import("./pages/StoreAnalytics"));
const ForecastPage = React.lazy(async () => import("./pages/Forecast"));
const PortfolioPlanner = React.lazy(async () => import("./pages/PortfolioPlanner"));
const ModelIntelligence = React.lazy(async () => import("./pages/ModelIntelligence"));
const ScenarioLab = React.lazy(async () => import("./pages/ScenarioLab"));
const PreflightDiagnostics = React.lazy(async () => import("./pages/PreflightDiagnostics"));
const AIAssistant = React.lazy(async () => import("./pages/AIAssistant"));
const DataSources = React.lazy(async () => import("./pages/DataSources"));
const Contracts = React.lazy(async () => import("./pages/Contracts"));
const NotificationsAlerts = React.lazy(async () => import("./pages/NotificationsAlerts"));

function NotFound() {
  const { t } = useI18n();
  return (
    <section className="page">
      <div className="panel">
        <h2 className="page-title">{t("not_found_title", "Page not found")}</h2>
        <p className="page-note">
          {t("not_found_note", "Use the left navigation to open any analytics module.")}
        </p>
      </div>
    </section>
  );
}

export default function App() {
  const { locale, localeTag, setLocale, t } = useI18n();
  const { theme, toggleTheme } = useThemeMode();

  const sidebarSections = React.useMemo(
    () => [
      {
        title: t("nav_section_overview", "Overview"),
        items: [
          { to: "/", label: t("nav_overview", "Overview") },
          { to: "/store-analytics", label: t("nav_store_analytics", "Store Analytics") },
          { to: "/forecast", label: t("nav_forecast", "Forecast") },
          { to: "/portfolio-planner", label: t("nav_portfolio_planner", "Portfolio Planner") },
          { to: "/scenario-lab", label: t("nav_scenario_lab", "Scenario Lab") },
        ],
      },
      {
        title: t("nav_section_ops", "Data & Ops"),
        items: [
          { to: "/data-sources", label: t("nav_data_sources", "Data Sources") },
          { to: "/contracts", label: t("nav_contracts", "Contracts") },
          { to: "/model-intelligence", label: t("nav_model_intelligence", "Model Intelligence") },
          { to: "/notifications", label: t("nav_notifications", "Notifications & Alerts") },
          { to: "/preflight-diagnostics", label: t("nav_preflight_diagnostics", "Preflight Diagnostics") },
        ],
      },
      {
        title: t("nav_section_tools", "Tools"),
        items: [{ to: "/ai-assistant", label: t("nav_ai_assistant", "AI Assistant") }],
      },
    ],
    [t]
  );

  const [apiStatus, setApiStatus] = React.useState<"checking" | "online" | "offline">("checking");
  const [statusMessage, setStatusMessage] = React.useState(t("status_checking", "Checking API..."));
  const [lastSeen, setLastSeen] = React.useState<string>("-");

  React.useEffect(() => {
    if (apiStatus === "online") {
      setStatusMessage(t("status_online", "API online"));
      return;
    }
    if (apiStatus === "offline") {
      setStatusMessage(t("status_offline", "API unreachable"));
      return;
    }
    setStatusMessage(t("status_checking", "Checking API..."));
  }, [apiStatus, t]);

  React.useEffect(() => {
    let active = true;

    async function checkApi() {
      try {
        const health = await fetchHealth();
        if (!active) {
          return;
        }

        const online = health.status === "ok";
        setApiStatus(online ? "online" : "offline");
        setStatusMessage(online ? t("status_online", "API online") : t("status_offline", "API unreachable"));
        setLastSeen(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
      } catch (error) {
        if (!active) {
          return;
        }
        setApiStatus("offline");
        setStatusMessage(extractApiError(error, t("status_offline", "API unreachable")));
      }
    }

    checkApi();
    const intervalId = window.setInterval(checkApi, 30000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [localeTag, t]);

  return (
    <div className="ecosystem-shell">
      <a className="skip-link" href="#main-content">
        {t("skip_to_content", "Skip to main content")}
      </a>

      <Sidebar sections={sidebarSections} />

      <div className="ecosystem-main">
        <TopBar
          statusLabel={statusMessage}
          statusKind={apiStatus}
          lastSeen={lastSeen}
          onToggleTheme={toggleTheme}
          themeLabel={theme === "dark" ? t("theme_dark", "Dark") : t("theme_light", "Light")}
          locale={locale}
          onLocaleChange={setLocale}
        />

        <main id="main-content" className="app-main">
          <React.Suspense
            fallback={
              <section className="page">
                <div className="panel">
                  <LoadingBlock lines={5} className="loading-stack" />
                </div>
              </section>
            }
          >
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/store-analytics" element={<StoreAnalytics />} />
              <Route path="/forecast" element={<ForecastPage />} />
              <Route path="/portfolio-planner" element={<PortfolioPlanner />} />
              <Route path="/scenario-lab" element={<ScenarioLab />} />
              <Route path="/model-intelligence" element={<ModelIntelligence />} />
              <Route path="/preflight-diagnostics" element={<PreflightDiagnostics />} />
              <Route path="/ai-assistant" element={<AIAssistant />} />
              <Route path="/data-sources" element={<DataSources />} />
              <Route path="/contracts" element={<Contracts />} />
              <Route path="/notifications" element={<NotificationsAlerts />} />
              <Route path="/notifications-alerts" element={<NotificationsAlerts />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </React.Suspense>
        </main>

        <footer className="footer">
          <p>{t("shell_title", "Aqiq Analytics Platform")}</p>
          <p>{t("footer_credit", "Created by Azab and Adam.")}</p>
          {import.meta.env.DEV ? (
            <p className="footer-meta">
              API: <code>{API_BASE_URL}</code> ({API_BASE_SOURCE})
            </p>
          ) : null}
        </footer>
      </div>
    </div>
  );
}
