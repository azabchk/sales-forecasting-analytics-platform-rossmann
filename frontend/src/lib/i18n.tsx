import React from "react";

export type Locale = "en" | "ru";

type Dictionary = Record<string, string>;

const EN: Dictionary = {
  nav_overview: "Overview",
  nav_store_analytics: "Store Analytics",
  nav_forecast: "Forecast",
  nav_portfolio_planner: "Portfolio Planner",
  nav_scenario_lab: "Scenario Lab",
  nav_model_intelligence: "Model Intelligence",
  nav_preflight_diagnostics: "Preflight Diagnostics",
  nav_ai_assistant: "AI Assistant",
  shell_eyebrow: "Retail Intelligence Suite",
  shell_title: "Aqiq Analytics Platform",
  shell_subtitle: "Decision cockpit for sales performance, promo impact, and forecasting reliability",
  status_checking: "Checking API...",
  status_online: "API online",
  status_offline: "API unreachable",
  status_last_check: "Last check",
  toggle_theme: "Theme",
  theme_light: "Light",
  theme_dark: "Dark",
  toggle_language: "Language",
  footer_credit: "Created by Azab and Adam.",
  not_found_title: "Page not found",
  not_found_note: "Use the navigation above to open any analytics module.",
  skip_to_content: "Skip to main content",
};

const RU: Dictionary = {
  nav_overview: "Обзор",
  nav_store_analytics: "Аналитика магазинов",
  nav_forecast: "Прогноз",
  nav_portfolio_planner: "Портфельный планировщик",
  nav_scenario_lab: "Сценарии",
  nav_model_intelligence: "Интеллект модели",
  nav_preflight_diagnostics: "Диагностика Preflight",
  nav_ai_assistant: "AI Ассистент",
  shell_eyebrow: "Платформа розничной аналитики",
  shell_title: "Aqiq Analytics Platform",
  shell_subtitle: "Центр принятия решений по продажам, акциям и качеству прогноза",
  status_checking: "Проверка API...",
  status_online: "API доступен",
  status_offline: "API недоступен",
  status_last_check: "Последняя проверка",
  toggle_theme: "Тема",
  theme_light: "Светлая",
  theme_dark: "Темная",
  toggle_language: "Язык",
  footer_credit: "Создано Azab и Adam.",
  not_found_title: "Страница не найдена",
  not_found_note: "Используйте навигацию выше, чтобы открыть нужный модуль.",
  skip_to_content: "Перейти к основному содержимому",
};

const dictionaries: Record<Locale, Dictionary> = { en: EN, ru: RU };

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, fallback?: string) => string;
  localeTag: string;
};

const I18nContext = React.createContext<I18nContextValue | null>(null);

const STORAGE_KEY = "aqiq_locale";

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocale] = React.useState<Locale>(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return saved === "ru" ? "ru" : "en";
  });

  React.useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, locale);
    document.documentElement.lang = locale;
    document.title = dictionaries[locale].shell_title ?? "Aqiq Analytics Platform";
  }, [locale]);

  const t = React.useCallback((key: string, fallback?: string) => {
    return dictionaries[locale][key] ?? fallback ?? key;
  }, [locale]);

  const value = React.useMemo<I18nContextValue>(
    () => ({ locale, setLocale, t, localeTag: locale === "ru" ? "ru-RU" : "en-US" }),
    [locale, t]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = React.useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return context;
}
