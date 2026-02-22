import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

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
