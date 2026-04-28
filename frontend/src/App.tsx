import React from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { API_BASE_SOURCE, API_BASE_URL, extractApiError } from "./api/client";
import { fetchHealth } from "./api/endpoints";
import RouteErrorBoundary from "./components/ErrorBoundary";
import ProtectedRoute from "./components/ProtectedRoute";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";
import LoadingBlock from "./components/LoadingBlock";
import { useAuth } from "./contexts/AuthContext";
import { useI18n } from "./lib/i18n";
import { useThemeMode } from "./lib/theme";

const LoginPage = React.lazy(async () => import("./pages/Login"));

// Nav icons
const Icons = {
  overview: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  storeAnalytics: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2 13V7l6-5 6 5v6H10V9H6v4H2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  ),
  forecast: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2 12L6 7l3 3 5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M11 5h3v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  portfolio: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="5" width="4" height="9" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="6" y="3" width="4" height="11" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11" y="1" width="4" height="13" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  scenario: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 4v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  dataSources: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <ellipse cx="8" cy="4" rx="6" ry="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2 4v4c0 1.38 2.69 2.5 6 2.5s6-1.12 6-2.5V4" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2 8v4c0 1.38 2.69 2.5 6 2.5s6-1.12 6-2.5V8" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  contracts: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="3" y="1" width="10" height="14" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M6 5h4M6 8h4M6 11h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  model: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.22 3.22l1.41 1.41M11.37 11.37l1.41 1.41M3.22 12.78l1.41-1.41M11.37 4.63l1.41-1.41" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  notifications: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8 1a5 5 0 0 1 5 5v3l1 2H2l1-2V6a5 5 0 0 1 5-5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M6.5 12.5a1.5 1.5 0 0 0 3 0" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  preflight: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8 2L14 5v4c0 3-2.5 5-6 6C2.5 14 0 12 0 9V5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" transform="translate(1,0)" />
      <path d="M5 8l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  aiAssistant: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="3" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5 7h6M5 9.5h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M5 12v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M11 12v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  storeComparison: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="6" width="3" height="8" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="5" y="3" width="3" height="11" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="9" y="5" width="3" height="9" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="13" y="1" width="3" height="13" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
};

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
const StoreComparison   = React.lazy(async () => import("./pages/StoreComparison"));
const UserManagement    = React.lazy(async () => import("./pages/UserManagement"));
const DataPipeline      = React.lazy(async () => import("./pages/DataPipeline"));

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

function PageFallback() {
  return (
    <section className="page">
      <div className="panel">
        <LoadingBlock lines={5} className="loading-stack" />
      </div>
    </section>
  );
}

export default function App() {
  // ── ALL hooks at the top — unconditionally ────────────────────────────────
  const { locale, localeTag, setLocale, t } = useI18n();
  const { theme, toggleTheme } = useThemeMode();
  const { isAuthenticated, isLoading: authLoading, user, logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const [apiStatus, setApiStatus] = React.useState<"checking" | "online" | "offline">("checking");
  const [statusMessage, setStatusMessage] = React.useState(t("status_checking", "Checking API..."));
  const [lastSeen, setLastSeen] = React.useState<string>("-");

  // Close sidebar on route change (mobile)
  React.useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  const sidebarSections = React.useMemo(
    () => [
      {
        title: t("nav_section_overview", "Overview"),
        items: [
          { to: "/", label: t("nav_overview", "Overview"), icon: Icons.overview },
          { to: "/store-analytics", label: t("nav_store_analytics", "Store Analytics"), icon: Icons.storeAnalytics },
          { to: "/store-comparison", label: t("nav_store_comparison", "Store Comparison"), icon: Icons.storeComparison },
          { to: "/forecast", label: t("nav_forecast", "Forecast"), icon: Icons.forecast },
          { to: "/portfolio-planner", label: t("nav_portfolio_planner", "Portfolio Planner"), icon: Icons.portfolio },
          { to: "/scenario-lab", label: t("nav_scenario_lab", "Scenario Lab"), icon: Icons.scenario },
        ],
      },
      {
        title: t("nav_section_ops", "Data & Ops"),
        items: [
          { to: "/data-sources", label: t("nav_data_sources", "Data Sources"), icon: Icons.dataSources },
          { to: "/contracts", label: t("nav_contracts", "Contracts"), icon: Icons.contracts },
          { to: "/model-intelligence", label: t("nav_model_intelligence", "Model Intelligence"), icon: Icons.model },
          { to: "/notifications", label: t("nav_notifications", "Notifications & Alerts"), icon: Icons.notifications },
          { to: "/preflight-diagnostics", label: t("nav_preflight_diagnostics", "Preflight Diagnostics"), icon: Icons.preflight },
        ],
      },
      {
        title: t("nav_section_tools", "Tools"),
        items: [
          { to: "/ai-assistant", label: t("nav_ai_assistant", "AI Assistant"), icon: Icons.aiAssistant },
          { to: "/data-pipeline", label: t("nav_data_pipeline", "Data Pipeline"), icon: Icons.dataSources },
          ...(user?.role === "admin"
            ? [{ to: "/users", label: t("nav_users", "User Management"), icon: Icons.contracts }]
            : []),
        ],
      },
    ],
    [t]
  );

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
        if (!active) return;
        const online = health.status === "ok";
        setApiStatus(online ? "online" : "offline");
        setStatusMessage(online ? t("status_online", "API online") : t("status_offline", "API unreachable"));
        setLastSeen(new Date().toLocaleTimeString(localeTag, { hour: "2-digit", minute: "2-digit" }));
      } catch (error) {
        if (!active) return;
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

  // ── Conditional renders AFTER all hooks ──────────────────────────────────

  // Still verifying stored token
  if (authLoading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <LoadingBlock lines={3} />
      </div>
    );
  }

  // Not logged in → login page only
  if (!isAuthenticated) {
    return (
      <React.Suspense fallback={<div />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </React.Suspense>
    );
  }

  return (
    <div className={`ecosystem-shell${sidebarOpen ? " sidebar-is-open" : ""}`}>
      <a className="skip-link" href="#main-content">
        {t("skip_to_content", "Skip to main content")}
      </a>

      <Sidebar
        sections={sidebarSections}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="ecosystem-main">
        <TopBar
          statusLabel={statusMessage}
          statusKind={apiStatus}
          lastSeen={lastSeen}
          onToggleTheme={toggleTheme}
          themeLabel={theme === "dark" ? t("theme_dark", "Dark") : t("theme_light", "Light")}
          locale={locale}
          onLocaleChange={setLocale}
          onMenuToggle={() => setSidebarOpen((prev) => !prev)}
          isSidebarOpen={sidebarOpen}
          user={user}
          onLogout={logout}
        />

        <main id="main-content" className="app-main">
          <React.Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/login" element={<Navigate to="/" replace />} />
              <Route path="/" element={<ProtectedRoute><RouteErrorBoundary><Overview /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/store-analytics" element={<ProtectedRoute><RouteErrorBoundary><StoreAnalytics /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/store-comparison" element={<ProtectedRoute><RouteErrorBoundary><StoreComparison /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/forecast" element={<ProtectedRoute><RouteErrorBoundary><ForecastPage /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/portfolio-planner" element={<ProtectedRoute><RouteErrorBoundary><PortfolioPlanner /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/scenario-lab" element={<ProtectedRoute><RouteErrorBoundary><ScenarioLab /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/model-intelligence" element={<ProtectedRoute><RouteErrorBoundary><ModelIntelligence /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/preflight-diagnostics" element={<ProtectedRoute><RouteErrorBoundary><PreflightDiagnostics /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/ai-assistant" element={<ProtectedRoute><RouteErrorBoundary><AIAssistant /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/data-sources" element={<ProtectedRoute><RouteErrorBoundary><DataSources /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/contracts" element={<ProtectedRoute><RouteErrorBoundary><Contracts /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/notifications" element={<ProtectedRoute><RouteErrorBoundary><NotificationsAlerts /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/notifications-alerts" element={<ProtectedRoute><RouteErrorBoundary><NotificationsAlerts /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/users" element={<ProtectedRoute><RouteErrorBoundary><UserManagement /></RouteErrorBoundary></ProtectedRoute>} />
              <Route path="/data-pipeline" element={<ProtectedRoute><RouteErrorBoundary><DataPipeline /></RouteErrorBoundary></ProtectedRoute>} />
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
