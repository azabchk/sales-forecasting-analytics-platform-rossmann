import React from "react";
import { NavLink, Route, Routes } from "react-router-dom";

import { extractApiError } from "./api/client";
import { fetchHealth } from "./api/endpoints";
import LoadingBlock from "./components/LoadingBlock";

const Overview = React.lazy(async () => import("./pages/Overview"));
const StoreAnalytics = React.lazy(async () => import("./pages/StoreAnalytics"));
const ForecastPage = React.lazy(async () => import("./pages/Forecast"));
const ModelIntelligence = React.lazy(async () => import("./pages/ModelIntelligence"));
const ScenarioLab = React.lazy(async () => import("./pages/ScenarioLab"));

const NAV_ITEMS = [
  { to: "/", label: "Overview" },
  { to: "/store-analytics", label: "Store Analytics" },
  { to: "/forecast", label: "Forecast" },
  { to: "/scenario-lab", label: "Scenario Lab" },
  { to: "/model-intelligence", label: "Model Intelligence" },
];

function NotFound() {
  return (
    <section className="page">
      <div className="panel">
        <h2 className="page-title">Page not found</h2>
        <p className="page-note">Use the navigation above to open Overview, Store Analytics, Forecast, Scenario Lab, or Model Intelligence.</p>
      </div>
    </section>
  );
}

export default function App() {
  const [apiStatus, setApiStatus] = React.useState<"checking" | "online" | "offline">("checking");
  const [statusMessage, setStatusMessage] = React.useState("Checking API...");
  const [lastSeen, setLastSeen] = React.useState<string>("-");

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
        setStatusMessage(online ? "API online" : "API unreachable");
        setLastSeen(new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }));
      } catch (error) {
        if (!active) {
          return;
        }
        setApiStatus("offline");
        setStatusMessage(extractApiError(error, "API unreachable"));
      }
    }

    checkApi();
    const intervalId = window.setInterval(checkApi, 30000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="title-row">
            <div>
              <p className="eyebrow">Retail Intelligence Suite</p>
              <h1 className="app-title">Rossmann Analytics Platform</h1>
              <p className="app-subtitle">Decision cockpit for sales performance, promo impact, and forecasting reliability</p>
            </div>
            <div className={`api-status ${apiStatus}`}>
              <span className="status-dot" />
              <div>
                <p className="status-title">{statusMessage}</p>
                <p className="status-meta">Last check: {lastSeen}</p>
              </div>
            </div>
          </div>

          <nav className="nav" aria-label="Main">
            {NAV_ITEMS.map((item) => (
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

      <main className="app-main">
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
            <Route path="/scenario-lab" element={<ScenarioLab />} />
            <Route path="/model-intelligence" element={<ModelIntelligence />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </React.Suspense>
      </main>

      <footer className="footer">
        <p>Rossmann Forecasting Platform</p>
        <p>Built for operations teams and decision support.</p>
      </footer>
    </div>
  );
}
