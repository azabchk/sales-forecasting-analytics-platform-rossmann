import React from "react";

export default function FilterBar({ children }: { children: React.ReactNode }) {
  return <div className="panel filter-bar">{children}</div>;
}
