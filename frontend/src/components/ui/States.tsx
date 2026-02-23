import React from "react";

import LoadingBlock from "../LoadingBlock";

export function LoadingState({ lines = 4 }: { lines?: number }) {
  return (
    <div className="panel">
      <LoadingBlock lines={lines} className="loading-stack" />
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="panel">
      <p className="error">{message}</p>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="panel">
      <p className="muted">{message}</p>
    </div>
  );
}

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
    <div className="panel">
      <p className="muted">{message}</p>
      <p className="meta-text">{filtersLabel}</p>
      <p className="meta-text">
        API: <code>{apiBaseUrl}</code>
      </p>
      <p className="meta-text">{hint}</p>
      {onReset ? (
        <button className="button ghost" type="button" onClick={onReset}>
          {resetLabel ?? "Reset filters"}
        </button>
      ) : null}
    </div>
  );
}
