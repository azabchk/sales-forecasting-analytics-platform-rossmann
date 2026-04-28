import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { ToastProvider } from "./components/ui/Toast";
import { AuthProvider } from "./contexts/AuthContext";
import { I18nProvider } from "./lib/i18n";
import { ThemeProvider } from "./lib/theme";
import "./styles/index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <I18nProvider>
          <ToastProvider>
            <BrowserRouter>
              <AuthProvider>
                <App />
              </AuthProvider>
            </BrowserRouter>
          </ToastProvider>
        </I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
