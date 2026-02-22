import React from "react";
import { NavLink, Route, Routes } from "react-router-dom";

import { extractApiError } from "./api/client";
import { fetchHealth } from "./api/endpoints";
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

function NotFound() {
  const { t } = useI18n();
  return (
    <section className="page">
      <div className="panel">
        <h2 className="page-title">{t("not_found_title", "Page not found")}</h2>
        <p className="page-note">{t("not_found_note", "Use the navigation above to open any analytics module.")}</p>
      </div>
    </section>
  );
}

export default function App() {
  const { locale, localeTag, setLocale, t } = useI18n();
  const { theme, toggleTheme } = useThemeMode();

  const navItems = React.useMemo(
    () => [
      { to: "/", label: t("nav_overview", "Overview") },
      { to: "/store-analytics", label: t("nav_store_analytics", "Store Analytics") },
      { to: "/forecast", label: t("nav_forecast", "Forecast") },
      { to: "/portfolio-planner", label: t("nav_portfolio_planner", "Portfolio Planner") },
      { to: "/scenario-lab", label: t("nav_scenario_lab", "Scenario Lab") },
      { to: "/model-intelligence", label: t("nav_model_intelligence", "Model Intelligence") },
      { to: "/preflight-diagnostics", label: t("nav_preflight_diagnostics", "Preflight Diagnostics") },
      { to: "/ai-assistant", label: t("nav_ai_assistant", "AI Assistant") },
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
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {t("skip_to_content", "Skip to main content")}
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="title-row">
            <div>
              <p className="eyebrow">{t("shell_eyebrow", "Retail Intelligence Suite")}</p>
              <h1 className="app-title">{t("shell_title", "Aqiq Analytics Platform")}</h1>
              <p className="app-subtitle">{t("shell_subtitle", "Decision cockpit for sales performance, promo impact, and forecasting reliability")}</p>
            </div>
            <div className={`api-status ${apiStatus}`}>
              <span className="status-dot" />
              <div>
                <p className="status-title">{statusMessage}</p>
                <p className="status-meta">{t("status_last_check", "Last check")}: {lastSeen}</p>
              </div>
            </div>
          </div>

          <div className="topbar-actions">
            <button className="button ghost" type="button" onClick={toggleTheme} aria-label={t("toggle_theme", "Theme")}>
              {t("toggle_theme", "Theme")}: {theme === "dark" ? t("theme_dark", "Dark") : t("theme_light", "Light")}
            </button>
            <div className="locale-switch">
              <span>{t("toggle_language", "Language")}:</span>
              <button className={`button ${locale === "en" ? "primary" : ""}`} type="button" onClick={() => setLocale("en")} aria-label="Switch language to English">
                EN
              </button>
              <button className={`button ${locale === "ru" ? "primary" : ""}`} type="button" onClick={() => setLocale("ru")} aria-label="Переключить язык на русский">
                RU
              </button>
            </div>
          </div>

          <nav className="nav" aria-label="Main">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

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
            <Route path="*" element={<NotFound />} />
          </Routes>
        </React.Suspense>
      </main>

      <footer className="footer">
        <p>{t("shell_title", "Aqiq Analytics Platform")}</p>
        <p>{t("footer_credit", "Created by Azab and Adam.")}</p>
      </footer>
    </div>
  );
}
