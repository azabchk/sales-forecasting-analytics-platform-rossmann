import React from "react";
import { ErrorBoundary as ReactErrorBoundary, FallbackProps } from "react-error-boundary";

function ErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  return (
    <section className="page">
      <div className="panel error-boundary-panel">
        <div className="error-boundary-icon" aria-hidden="true">⚠</div>
        <h3 className="error-boundary-title">Something went wrong</h3>
        <p className="error-boundary-message">
          {error instanceof Error ? error.message : "An unexpected error occurred on this page."}
        </p>
        <div className="error-boundary-actions">
          <button className="button primary" type="button" onClick={resetErrorBoundary}>
            Try again
          </button>
          <button
            className="button ghost"
            type="button"
            onClick={() => {
              window.location.href = "/";
            }}
          >
            Go to Overview
          </button>
        </div>
        {import.meta.env.DEV && error instanceof Error && error.stack && (
          <details className="error-boundary-stack">
            <summary>Stack trace (dev only)</summary>
            <pre>{error.stack}</pre>
          </details>
        )}
      </div>
    </section>
  );
}

type RouteErrorBoundaryProps = {
  children: React.ReactNode;
};

export default function RouteErrorBoundary({ children }: RouteErrorBoundaryProps) {
  return (
    <ReactErrorBoundary
      FallbackComponent={ErrorFallback}
      onReset={() => {
        // Clear any stale state if needed
      }}
    >
      {children}
    </ReactErrorBoundary>
  );
}
