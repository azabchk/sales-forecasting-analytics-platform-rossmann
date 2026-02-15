import React from "react";
import { Link, Route, Routes } from "react-router-dom";

import ForecastPage from "./pages/Forecast";
import Overview from "./pages/Overview";
import StoreAnalytics from "./pages/StoreAnalytics";

const linkStyle: React.CSSProperties = {
  color: "#1e2a44",
  textDecoration: "none",
  fontWeight: 600
};

export default function App() {
  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(180deg, #f9fbff 0%, #eef4ff 100%)" }}>
      <header style={{ padding: "16px 20px", borderBottom: "1px solid #dbe3f5", background: "#ffffff" }}>
        <h1 style={{ margin: 0, color: "#1e2a44", fontSize: 22 }}>Rossmann Analytics Dashboard</h1>
        <nav style={{ marginTop: 10, display: "flex", gap: 16 }}>
          <Link to="/" style={linkStyle}>Overview</Link>
          <Link to="/store-analytics" style={linkStyle}>Store Analytics</Link>
          <Link to="/forecast" style={linkStyle}>Forecast</Link>
        </nav>
      </header>

      <main style={{ maxWidth: 1200, margin: "0 auto", padding: 20 }}>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/store-analytics" element={<StoreAnalytics />} />
          <Route path="/forecast" element={<ForecastPage />} />
        </Routes>
      </main>
    </div>
  );
}
