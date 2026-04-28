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

// Restore JWT token from localStorage on cold load
const _storedToken = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
if (_storedToken) {
  apiClient.defaults.headers.common["Authorization"] = `Bearer ${_storedToken}`;
}

apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    // Diagnostics API key (existing behaviour)
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

// On 401 → try refresh token once, then clear session
let _isRefreshing = false;
let _refreshQueue: Array<(token: string) => void> = [];

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const path = String(originalRequest?.url ?? "");

    // Don't retry auth endpoints themselves
    if (
      !axios.isAxiosError(error) ||
      error.response?.status !== 401 ||
      path.includes("/auth/login") ||
      path.includes("/auth/refresh") ||
      originalRequest._retried
    ) {
      return Promise.reject(error);
    }

    if (typeof window === "undefined") return Promise.reject(error);

    const refreshToken = localStorage.getItem("auth_refresh_token");
    if (!refreshToken) {
      localStorage.removeItem("auth_token");
      delete apiClient.defaults.headers.common["Authorization"];
      return Promise.reject(error);
    }

    if (_isRefreshing) {
      // Queue this request until refresh completes
      return new Promise((resolve) => {
        _refreshQueue.push((newToken: string) => {
          originalRequest.headers["Authorization"] = `Bearer ${newToken}`;
          resolve(apiClient(originalRequest));
        });
      });
    }

    _isRefreshing = true;
    originalRequest._retried = true;

    try {
      const { data } = await apiClient.post<{ access_token: string; refresh_token: string }>(
        "/auth/refresh",
        { refresh_token: refreshToken }
      );
      localStorage.setItem("auth_token", data.access_token);
      localStorage.setItem("auth_refresh_token", data.refresh_token);
      apiClient.defaults.headers.common["Authorization"] = `Bearer ${data.access_token}`;
      _refreshQueue.forEach((cb) => cb(data.access_token));
      _refreshQueue = [];
      originalRequest.headers["Authorization"] = `Bearer ${data.access_token}`;
      return apiClient(originalRequest);
    } catch {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_refresh_token");
      delete apiClient.defaults.headers.common["Authorization"];
      _refreshQueue = [];
      return Promise.reject(error);
    } finally {
      _isRefreshing = false;
    }
  }
);

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
