import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiClient } from "../api/client";

export type UserRole = "admin" | "analyst";

export type AuthUser = {
  id: number;
  email: string;
  username: string;
  role: UserRole;
  is_active: boolean;
};

type AuthState = {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
};

type AuthContextValue = AuthState & {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
  isAuthenticated: boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = "auth_token";
const REFRESH_KEY = "auth_refresh_token";

function setAxiosToken(token: string | null) {
  if (token) {
    apiClient.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common["Authorization"];
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: localStorage.getItem(TOKEN_KEY),
    isLoading: true,
  });

  // On mount: restore session — try refresh token if access token missing/expired
  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    const storedRefresh = localStorage.getItem(REFRESH_KEY);

    if (!storedToken && !storedRefresh) {
      setState({ user: null, token: null, isLoading: false });
      return;
    }

    const tryRestore = async () => {
      if (storedToken) {
        setAxiosToken(storedToken);
        try {
          const { data } = await apiClient.get<AuthUser>("/auth/me");
          setState({ user: data, token: storedToken, isLoading: false });
          return;
        } catch {
          // Access token expired — try refresh
        }
      }

      if (storedRefresh) {
        try {
          const { data } = await apiClient.post<{ access_token: string; refresh_token: string }>(
            "/auth/refresh",
            { refresh_token: storedRefresh }
          );
          localStorage.setItem(TOKEN_KEY, data.access_token);
          localStorage.setItem(REFRESH_KEY, data.refresh_token);
          setAxiosToken(data.access_token);
          const { data: user } = await apiClient.get<AuthUser>("/auth/me");
          setState({ user, token: data.access_token, isLoading: false });
          return;
        } catch {
          // Refresh also expired
        }
      }

      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
      setAxiosToken(null);
      setState({ user: null, token: null, isLoading: false });
    };

    tryRestore();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await apiClient.post<{ access_token: string; refresh_token: string; user: AuthUser }>(
      "/auth/login",
      { email, password }
    );
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    setAxiosToken(data.access_token);
    setState({ user: data.user, token: data.access_token, isLoading: false });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    setAxiosToken(null);
    setState({ user: null, token: null, isLoading: false });
  }, []);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        logout,
        isAdmin: state.user?.role === "admin",
        isAuthenticated: !!state.user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
