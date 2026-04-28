import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { extractApiError } from "../api/client";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(extractApiError(err, "Login failed. Please check your credentials."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        {/* Logo / header */}
        <div className="login-header">
          <div className="login-logo" aria-hidden="true">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <rect width="40" height="40" rx="10" fill="var(--color-accent)" />
              <path
                d="M8 28L16 18l6 6 10-14"
                stroke="white"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M24 12h7v7"
                stroke="white"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h1 className="login-title">Aqiq Analytics</h1>
          <p className="login-subtitle">Sales Forecasting Platform</p>
        </div>

        {/* Form */}
        <form className="login-form" onSubmit={handleSubmit} noValidate>
          {error && (
            <div className="login-error" role="alert">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
                <path d="M8 5v4M8 11v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              {error}
            </div>
          )}

          <div className="login-field">
            <label htmlFor="login-email" className="login-label">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              className="login-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              autoFocus
              required
              disabled={loading}
            />
          </div>

          <div className="login-field">
            <label htmlFor="login-password" className="login-label">
              Password
            </label>
            <div className="login-password-wrap">
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                className="login-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
                disabled={loading}
              />
              <button
                type="button"
                className="login-password-toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                tabIndex={-1}
              >
                {showPassword ? (
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                    <path d="M2 9s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5Z" stroke="currentColor" strokeWidth="1.5" />
                    <circle cx="9" cy="9" r="2" stroke="currentColor" strokeWidth="1.5" />
                    <path d="M3 3l12 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                    <path d="M2 9s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5Z" stroke="currentColor" strokeWidth="1.5" />
                    <circle cx="9" cy="9" r="2" stroke="currentColor" strokeWidth="1.5" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="login-btn"
            disabled={loading || !email || !password}
          >
            {loading ? (
              <>
                <span className="login-spinner" aria-hidden="true" />
                Signing in…
              </>
            ) : (
              "Sign in"
            )}
          </button>
        </form>

        <p className="login-footer">
          Contact your admin to create an account.
        </p>
      </div>
    </div>
  );
}
