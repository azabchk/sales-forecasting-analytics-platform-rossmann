import React, { useState } from "react";
import { AuthUser } from "../../contexts/AuthContext";
import { apiClient, extractApiError } from "../../api/client";

type TopBarProps = {
  statusLabel: string;
  statusKind: "checking" | "online" | "offline";
  lastSeen: string;
  onToggleTheme: () => void;
  themeLabel: string;
  locale: "en" | "ru";
  onLocaleChange: (locale: "en" | "ru") => void;
  onMenuToggle: () => void;
  isSidebarOpen: boolean;
  user?: AuthUser | null;
  onLogout?: () => void;
};

export default function TopBar({
  statusLabel,
  statusKind,
  lastSeen,
  onToggleTheme,
  themeLabel,
  locale,
  onLocaleChange,
  onMenuToggle,
  isSidebarOpen,
  user,
  onLogout,
}: TopBarProps) {
  const isDark = themeLabel === "Dark" || themeLabel === "Темная";

  const [showPwModal, setShowPwModal] = useState(false);
  const [pwForm, setPwForm] = useState({ current: "", next: "", confirm: "" });
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwLoading, setPwLoading] = useState(false);

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwError(null);
    if (pwForm.next !== pwForm.confirm) { setPwError("New passwords do not match."); return; }
    if (pwForm.next.length < 8) { setPwError("New password must be at least 8 characters."); return; }
    setPwLoading(true);
    try {
      await apiClient.patch("/auth/me/password", {
        current_password: pwForm.current,
        new_password: pwForm.next,
      });
      setPwSuccess(true);
      setPwForm({ current: "", next: "", confirm: "" });
      setTimeout(() => { setShowPwModal(false); setPwSuccess(false); }, 1500);
    } catch (err) {
      setPwError(extractApiError(err, "Failed to change password"));
    } finally {
      setPwLoading(false);
    }
  }

  return (
    <>
    <header className="app-topbar">
      {/* Hamburger — only visible on mobile */}
      <button
        className="topbar-hamburger"
        type="button"
        aria-label={isSidebarOpen ? "Close navigation" : "Open navigation"}
        aria-expanded={isSidebarOpen}
        onClick={onMenuToggle}
      >
        {isSidebarOpen ? (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M3 3L17 17M17 3L3 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M3 5H17M3 10H17M3 15H17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        )}
      </button>

      <div className="app-topbar-title">
        <h2>Sales Forecasting &amp; Analytics</h2>
        <p>Forecasting, diagnostics, contracts, MLOps, and what-if planning</p>
      </div>

      <div className="app-topbar-actions">
        <div className={`topbar-status ${statusKind}`} title={`Last check: ${lastSeen}`}>
          <span className={`topbar-status-dot${statusKind === "checking" ? " pulsing" : ""}`} aria-hidden="true" />
          <div className="topbar-status-text">
            <p>{statusLabel}</p>
            <small>Last check: {lastSeen}</small>
          </div>
        </div>

        <button
          className="button ghost topbar-theme-btn"
          type="button"
          onClick={onToggleTheme}
          aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
          title={`Switch to ${isDark ? "light" : "dark"} theme`}
        >
          <span aria-hidden="true">{isDark ? "☀" : "☾"}</span>
          <span className="topbar-theme-label">{themeLabel}</span>
        </button>

        <div className="topbar-locale" role="group" aria-label="Language selection">
          <button
            type="button"
            className={`button ${locale === "en" ? "primary" : "ghost"}`}
            onClick={() => onLocaleChange("en")}
            aria-pressed={locale === "en"}
          >
            EN
          </button>
          <button
            type="button"
            className={`button ${locale === "ru" ? "primary" : "ghost"}`}
            onClick={() => onLocaleChange("ru")}
            aria-pressed={locale === "ru"}
          >
            RU
          </button>
        </div>

        {user && (
          <div className="topbar-user">
            <div className="topbar-user-info">
              <span className="topbar-user-name">{user.username}</span>
              <span className="topbar-user-role">{user.role}</span>
            </div>
            <button
              type="button"
              className="topbar-logout-btn"
              onClick={() => { setShowPwModal(true); setPwError(null); setPwSuccess(false); }}
              title="Change password"
              aria-label="Change password"
              style={{ marginRight: 4 }}
            >
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
                <rect x="3" y="7" width="9" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M5 7V5a3 3 0 0 1 6 0v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              Password
            </button>
            <button
              type="button"
              className="topbar-logout-btn"
              onClick={onLogout}
              title="Sign out"
              aria-label="Sign out"
            >
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
                <path d="M6 2H3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h3M10 10l3-3-3-3M13 7H6"
                  stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>

    {/* Change Password Modal — rendered as sibling to header via Fragment */}
    {showPwModal && (
      <div className="modal-overlay" onClick={() => setShowPwModal(false)}>
        <div className="modal-card" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2 className="modal-title">Change Password</h2>
            <button className="modal-close" onClick={() => setShowPwModal(false)}>✕</button>
          </div>
          {pwSuccess ? (
            <div style={{ textAlign: "center", padding: "24px 0", color: "var(--status-pass)", fontWeight: 600 }}>
              ✓ Password changed successfully!
            </div>
          ) : (
            <form onSubmit={handleChangePassword} className="login-form" style={{ gap: 14 }}>
              {pwError && <div className="login-error">{pwError}</div>}
              <div className="login-field">
                <label className="login-label">Current Password</label>
                <input className="login-input" type="password" required
                  value={pwForm.current} onChange={(e) => setPwForm((f) => ({ ...f, current: e.target.value }))}
                  placeholder="••••••••" disabled={pwLoading} />
              </div>
              <div className="login-field">
                <label className="login-label">New Password</label>
                <input className="login-input" type="password" required minLength={8}
                  value={pwForm.next} onChange={(e) => setPwForm((f) => ({ ...f, next: e.target.value }))}
                  placeholder="Min 8 characters" disabled={pwLoading} />
              </div>
              <div className="login-field">
                <label className="login-label">Confirm New Password</label>
                <input className="login-input" type="password" required
                  value={pwForm.confirm} onChange={(e) => setPwForm((f) => ({ ...f, confirm: e.target.value }))}
                  placeholder="Repeat new password" disabled={pwLoading} />
              </div>
              <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                <button type="button" className="button ghost" style={{ flex: 1 }}
                  onClick={() => setShowPwModal(false)} disabled={pwLoading}>Cancel</button>
                <button type="submit" className="login-btn" style={{ flex: 2, marginTop: 0 }}
                  disabled={pwLoading || !pwForm.current || !pwForm.next || !pwForm.confirm}>
                  {pwLoading ? <><span className="login-spinner" /> Saving…</> : "Save Password"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    )}
    </>
  );
}
