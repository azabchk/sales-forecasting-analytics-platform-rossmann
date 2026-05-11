import React from "react";

import { extractApiError } from "../api/client";
import { ChatResponse, postChatQuery } from "../api/endpoints";
import LoadingBlock from "../components/LoadingBlock";
import { useI18n } from "../lib/i18n";

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  insights?: ChatResponse["insights"];
  suggestions?: string[];
  detected_intent?: string | null;
  confidence_score?: number | null;
};

const SESSION_KEY = "ai_assistant_messages";

const DEFAULT_PROMPTS = [
  "What is the system data coverage?",
  "Show top 5 stores by total sales",
  "Forecast store 1 for 30 days",
  "Compare store 1 and store 2",
  "What is the data pipeline status?",
  "What is the model accuracy?",
];

const DEFAULT_PROMPTS_RU = [
  "Какое покрытие данных в системе?",
  "Покажи топ 5 магазинов по продажам",
  "Спрогнозируй магазин 1 на 30 дней",
];

function getWelcomeMessage(locale: string): ChatMessage {
  return {
    role: "assistant",
    text: locale === "ru"
      ? "Спросите меня о KPI, прогнозах, влиянии промо, качестве модели или лидирующих магазинах."
      : "Ask me about KPIs, forecasts, promo impact, model quality, or top stores.",
    suggestions: locale === "ru" ? DEFAULT_PROMPTS_RU : DEFAULT_PROMPTS,
  };
}

function loadMessages(locale: string): ChatMessage[] {
  try {
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as ChatMessage[];
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch { /* quota or parse error */ }
  return [getWelcomeMessage(locale)];
}

export default function AIAssistant() {
  const { locale } = useI18n();
  const isDebug = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("debug") === "1";

  const [messages, setMessages] = React.useState<ChatMessage[]>(() => loadMessages(locale));
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const bottomRef = React.useRef<HTMLDivElement>(null);

  // Persist on every change
  React.useEffect(() => {
    try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(messages)); } catch { /* ignore */ }
  }, [messages]);

  // Update welcome message text when locale changes (only the first message)
  React.useEffect(() => {
    setMessages((prev) => {
      if (prev.length === 0 || prev[0].role !== "assistant") return prev;
      return [{ ...prev[0], text: getWelcomeMessage(locale).text, suggestions: getWelcomeMessage(locale).suggestions }, ...prev.slice(1)];
    });
  }, [locale]);

  // Scroll to bottom on new message
  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function clearConversation() {
    const fresh = [getWelcomeMessage(locale)];
    setMessages(fresh);
    try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(fresh)); } catch { /* ignore */ }
  }

  async function sendMessage(rawMessage: string) {
    const message = rawMessage.trim();
    if (!message || loading) return;
    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setInput("");
    setError("");
    setLoading(true);
    try {
      const response = await postChatQuery({ message });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: response.answer,
          insights: response.insights,
          suggestions: response.suggestions,
          detected_intent: response.detected_intent,
          confidence_score: response.confidence_score,
        },
      ]);
    } catch (err) {
      setError(extractApiError(err, locale === "ru" ? "Не удалось получить ответ от API чата." : "Failed to get chat response from API."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">AI Assistant</h2>
          <p className="page-note">
            {locale === "ru"
              ? "Диалоговый аналитический ассистент для KPI, прогнозирования и диагностики модели."
              : "Conversational analytics assistant for KPI, forecasting, and model diagnostics."}
          </p>
        </div>
        <button className="button ghost" type="button" onClick={clearConversation}>
          {locale === "ru" ? "Очистить диалог" : "Clear conversation"}
        </button>
      </div>

      <div className="panel">
        <div className="chat-stream">
          {messages.map((message, index) => (
            <article key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>
              <p className="chat-role">
                {message.role === "assistant"
                  ? (locale === "ru" ? "Ассистент" : "Assistant")
                  : (locale === "ru" ? "Вы" : "You")}
              </p>
              <p className="chat-text">{message.text}</p>

              {isDebug && message.role === "assistant" && message.detected_intent && (
                <span className="chat-intent-badge">
                  {message.detected_intent}
                  {message.confidence_score != null && ` (${(message.confidence_score * 100).toFixed(0)}%)`}
                </span>
              )}

              {message.insights && message.insights.length > 0 && (
                <div className="chat-insights">
                  {message.insights.map((item) => (
                    <div className="chat-insight" key={`${item.label}-${item.value}`}>
                      <p className="chat-insight-label">{item.label}</p>
                      <p className="chat-insight-value">{item.value}</p>
                    </div>
                  ))}
                </div>
              )}

              {message.suggestions && message.suggestions.length > 0 && (
                <div className="chat-suggestions">
                  {message.suggestions.map((prompt) => (
                    <button key={prompt} className="button ghost" onClick={() => sendMessage(prompt)} type="button" disabled={loading}>
                      {prompt}
                    </button>
                  ))}
                </div>
              )}
            </article>
          ))}

          {loading && (
            <div className="chat-loading">
              <LoadingBlock lines={2} className="loading-stack" />
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="panel">
        <form className="chat-form" onSubmit={(e) => { e.preventDefault(); sendMessage(input); }}>
          <div className="field chat-input-wrap">
            <label htmlFor="chat-message">{locale === "ru" ? "Задайте вопрос" : "Ask a question"}</label>
            <textarea
              id="chat-message"
              className="input chat-input"
              placeholder={locale === "ru" ? "Пример: Forecast store 1 for 60 days" : "Example: Forecast store 1 for 60 days"}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              rows={3}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
            />
          </div>
          <button className="button primary" type="submit" disabled={loading || input.trim().length === 0}>
            {loading ? (locale === "ru" ? "Думаю..." : "Thinking...") : locale === "ru" ? "Отправить" : "Send"}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>
    </section>
  );
}
