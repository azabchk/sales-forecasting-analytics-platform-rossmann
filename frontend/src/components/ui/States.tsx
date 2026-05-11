import React from "react";

// ─── Skeleton loader (multi-line shimmer) ─────────────────────────────────────

type SkeletonProps = {
  lines?: number;
  className?: string;
  heights?: number[];
};

export function SkeletonBlock({ lines = 4, className = "", heights }: SkeletonProps) {
  const defaultHeights = [14, 14, 14, 14, 14];
  const h = heights ?? defaultHeights;
  return (
    <div className={`loading-stack ${className}`.trim()} aria-busy="true" aria-label="Loading content…">
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{ height: h[i % h.length] ?? 14, width: i === lines - 1 ? "68%" : "100%" }}
        />
      ))}
    </div>
  );
}

export function LoadingState({ lines = 4 }: { lines?: number }) {
  return (
    <div className="panel">
      <SkeletonBlock lines={lines} />
    </div>
  );
}

// ─── Error state with retry ───────────────────────────────────────────────────

type ErrorStateProps = {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
};

export function ErrorState({ message, onRetry, retryLabel = "Try again" }: ErrorStateProps) {
  return (
    <div className="panel state-panel state-error">
      <div className="state-icon" aria-hidden="true">⚠</div>
      <p className="error state-message">{message}</p>
      {onRetry && (
        <button className="button ghost state-retry-btn" type="button" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

export function EmptyState({ message, icon }: { message: string; icon?: React.ReactNode }) {
  return (
    <div className="panel state-panel state-empty">
      {icon ? <div className="state-icon" aria-hidden="true">{icon}</div> : null}
      <p className="muted state-message">{message}</p>
    </div>
  );
}

// ─── No-data state with filters summary + reset ───────────────────────────────

export function NoDataState(props: {
  message: string;
  filtersLabel: string;
  apiBaseUrl: string;
  hint: string;
  onReset?: () => void;
  resetLabel?: string;
}) {
  const { message, filtersLabel, apiBaseUrl, hint, onReset, resetLabel } = props;

  return (
    <div className="panel state-panel state-empty">
      <div className="state-icon" aria-hidden="true">
        <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
          <rect x="4" y="4" width="28" height="28" rx="6" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.35" />
          <path d="M12 18h12M18 12v12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.35" />
        </svg>
      </div>
      <p className="muted state-message">{message}</p>
      <p className="meta-text state-filters">{filtersLabel}</p>
      <p className="meta-text state-api">
        API: <code>{apiBaseUrl}</code>
      </p>
      <p className="meta-text">{hint}</p>
      {onReset ? (
        <button className="button ghost state-reset-btn" type="button" onClick={onReset}>
          {resetLabel ?? "Reset filters"}
        </button>
      ) : null}
    </div>
  );
}
