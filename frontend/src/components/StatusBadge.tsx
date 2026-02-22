import React from "react";

type StatusBadgeProps = {
  status: string | null | undefined;
  className?: string;
};

function normalizeStatus(status: string | null | undefined): string {
  return (status ?? "UNKNOWN").toString().trim().toUpperCase();
}

function statusClass(status: string): string {
  switch (status) {
    case "PASS":
    case "OK":
    case "RESOLVED":
    case "LOW":
    case "ACKED":
      return "pass";
    case "WARN":
    case "PENDING":
    case "MEDIUM":
    case "SILENCED":
      return "warn";
    case "FAIL":
    case "FIRING":
    case "HIGH":
      return "fail";
    case "SKIPPED":
    case "EVALUATED":
      return "skipped";
    default:
      return "unknown";
  }
}

export default function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  const normalized = normalizeStatus(status);
  return <span className={`status-badge ${statusClass(normalized)} ${className}`.trim()}>{normalized}</span>;
}
