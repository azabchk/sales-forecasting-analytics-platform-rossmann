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
