import React from "react";

type TopBarProps = {
  statusLabel: string;
  statusKind: "checking" | "online" | "offline";
  lastSeen: string;
  onToggleTheme: () => void;
  themeLabel: string;
  locale: "en" | "ru";
  onLocaleChange: (locale: "en" | "ru") => void;
};

export default function TopBar({
  statusLabel,
  statusKind,
  lastSeen,
  onToggleTheme,
  themeLabel,
  locale,
  onLocaleChange,
}: TopBarProps) {
  return (
    <header className="app-topbar">
      <div className="app-topbar-title">
        <h2>Sales Forecasting & Analytics Ecosystem</h2>
        <p>Forecasting, diagnostics, contracts, MLOps, and what-if planning</p>
      </div>
      <div className="app-topbar-actions">
        <div className={`topbar-status ${statusKind}`}>
          <span className="topbar-status-dot" />
          <div>
            <p>{statusLabel}</p>
            <small>Last check: {lastSeen}</small>
          </div>
        </div>
        <button className="button ghost" type="button" onClick={onToggleTheme}>
          Theme: {themeLabel}
        </button>
        <div className="topbar-locale">
          <button
            type="button"
            className={`button ${locale === "en" ? "primary" : "ghost"}`}
            onClick={() => onLocaleChange("en")}
          >
            EN
          </button>
          <button
            type="button"
            className={`button ${locale === "ru" ? "primary" : "ghost"}`}
            onClick={() => onLocaleChange("ru")}
          >
            RU
          </button>
        </div>
      </div>
    </header>
  );
}
