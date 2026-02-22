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
};

const DEFAULT_PROMPTS = [
  "What is the system data coverage?",
  "Show top 5 stores by total sales",
  "Forecast store 1 for 30 days",
];

const DEFAULT_PROMPTS_RU = [
  "Какое покрытие данных в системе?",
  "Покажи топ 5 магазинов по продажам",
  "Спрогнозируй магазин 1 на 30 дней",
];

export default function AIAssistant() {
  const { locale } = useI18n();
  const [messages, setMessages] = React.useState<ChatMessage[]>([
    {
      role: "assistant",
      text:
        locale === "ru"
          ? "Спросите меня о KPI, прогнозах, влиянии промо, качестве модели или лидирующих магазинах."
          : "Ask me about KPIs, forecasts, promo impact, model quality, or top stores.",
      suggestions: locale === "ru" ? DEFAULT_PROMPTS_RU : DEFAULT_PROMPTS,
    },
  ]);
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    setMessages((prev) => {
      if (prev.length === 0 || prev[0].role !== "assistant") {
        return prev;
      }
      const first = prev[0];
      return [
        {
          ...first,
          text:
            locale === "ru"
              ? "Спросите меня о KPI, прогнозах, влиянии промо, качестве модели или лидирующих магазинах."
              : "Ask me about KPIs, forecasts, promo impact, model quality, or top stores.",
          suggestions: locale === "ru" ? DEFAULT_PROMPTS_RU : DEFAULT_PROMPTS,
        },
        ...prev.slice(1),
      ];
    });
  }, [locale]);

  async function sendMessage(rawMessage: string) {
    const message = rawMessage.trim();
    if (!message || loading) {
      return;
    }

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
        },
      ]);
    } catch (errorResponse) {
      setError(
        extractApiError(
          errorResponse,
          locale === "ru" ? "Не удалось получить ответ от API чата." : "Failed to get chat response from API."
        )
      );
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
      </div>

      <div className="panel">
        <div className="chat-stream">
          {messages.map((message, index) => (
            <article key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>
              <p className="chat-role">
                {message.role === "assistant"
                  ? locale === "ru"
                    ? "Ассистент"
                    : "Assistant"
                  : locale === "ru"
                    ? "Вы"
                    : "You"}
              </p>
              <p className="chat-text">{message.text}</p>

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
                    <button
                      key={prompt}
                      className="button ghost"
                      onClick={() => sendMessage(prompt)}
                      type="button"
                      disabled={loading}
                    >
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
        </div>
      </div>

      <div className="panel">
        <form
          className="chat-form"
          onSubmit={(event) => {
            event.preventDefault();
            sendMessage(input);
          }}
        >
          <div className="field chat-input-wrap">
            <label htmlFor="chat-message">{locale === "ru" ? "Задайте вопрос" : "Ask a question"}</label>
            <textarea
              id="chat-message"
              className="input chat-input"
              placeholder={locale === "ru" ? "Пример: Forecast store 1 for 60 days" : "Example: Forecast store 1 for 60 days"}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              rows={3}
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
