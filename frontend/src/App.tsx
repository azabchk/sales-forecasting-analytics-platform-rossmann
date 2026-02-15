import React from "react";
import { NavLink, Route, Routes } from "react-router-dom";

import ForecastPage from "./pages/Forecast";
import Overview from "./pages/Overview";
import StoreAnalytics from "./pages/StoreAnalytics";

const NAV_ITEMS = [
  { to: "/", label: "Overview" },
  { to: "/store-analytics", label: "Store Analytics" },
  { to: "/forecast", label: "Forecast" },
];

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="title-row">
            <div>
              <h1 className="app-title">Rossmann Analytics Platform</h1>
              <p className="app-subtitle">Sales intelligence, KPI monitoring, and demand forecasting</p>
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
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/store-analytics" element={<StoreAnalytics />} />
          <Route path="/forecast" element={<ForecastPage />} />
        </Routes>
      </main>
    </div>
  );
}
