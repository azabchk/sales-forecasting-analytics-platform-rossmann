import axios from "axios";

function normalizeBaseUrl(raw: string): string {
  return raw.replace(/\/+$/, "");
}

function resolveApiBaseUrl(): { baseUrl: string; source: string } {
  const configured = String(import.meta.env.VITE_API_BASE_URL ?? "").trim();
  if (configured.length > 0) {
    return { baseUrl: normalizeBaseUrl(configured), source: "VITE_API_BASE_URL" };
  }

  const backendPort = String(import.meta.env.VITE_BACKEND_PORT ?? "8000").trim() || "8000";
  const host = typeof window !== "undefined" ? window.location.hostname || "localhost" : "localhost";
  const protocol = typeof window !== "undefined" ? window.location.protocol : "http:";
  return {
    baseUrl: normalizeBaseUrl(`${protocol}//${host}:${backendPort}/api/v1`),
    source: "fallback(VITE_BACKEND_PORT)",
  };
}

const resolved = resolveApiBaseUrl();
export const API_BASE_URL = resolved.baseUrl;
export const API_BASE_SOURCE = resolved.source;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
});

apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const apiKey = window.sessionStorage.getItem("diagnostics_api_key");
    const normalized = typeof apiKey === "string" ? apiKey.trim() : "";
    const requestPath = String(config.url ?? "");
    if (normalized && requestPath.includes("/diagnostics/")) {
      config.headers = config.headers ?? {};
      config.headers["X-API-Key"] = normalized;
    }
  }
  return config;
});

export function extractApiError(error: unknown, fallbackMessage: string): string {
  if (!axios.isAxiosError(error)) {
    return fallbackMessage;
  }

  const responseData = error.response?.data as { detail?: unknown; message?: unknown } | undefined;
  const detail = responseData?.detail;
  if (typeof detail === "string" && detail.trim().length > 0) {
    return detail;
  }

  const message = responseData?.message;
  if (typeof message === "string" && message.trim().length > 0) {
    return message;
  }

  if (typeof error.message === "string" && error.message.trim().length > 0) {
    return error.message;
  }

  return fallbackMessage;
}
