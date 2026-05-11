from fastapi.testclient import TestClient

import app.routers.chat as chat_router
from app.main import app
from app.schemas import ChatInsight, ChatResponse


def test_chat_query_route_returns_expected_shape(monkeypatch):
    client = TestClient(app)

    def fake_answer(_: str) -> ChatResponse:
        return ChatResponse(
            answer="ok",
            insights=[ChatInsight(label="KPI", value="123")],
            suggestions=["Show top stores"],
        )

    monkeypatch.setattr(chat_router, "answer_chat_query", fake_answer)
    response = client.post("/api/v1/chat/query", json={"message": "hello"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "ok"
    assert payload["insights"] == [{"label": "KPI", "value": "123"}]
    assert payload["suggestions"] == ["Show top stores"]


def test_chat_query_route_validates_message():
    client = TestClient(app)

    response = client.post("/api/v1/chat/query", json={"message": ""})

    assert response.status_code == 422


def test_chat_query_exposes_detected_intent(monkeypatch):
    def fake_answer(_: str) -> ChatResponse:
        return ChatResponse(
            answer="Forecast result",
            insights=[],
            suggestions=[],
            detected_intent="forecast",
            confidence_score=0.92,
        )

    monkeypatch.setattr(chat_router, "answer_chat_query", fake_answer)
    client = TestClient(app)
    resp = client.post("/api/v1/chat/query", json={"message": "forecast store 1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["detected_intent"] == "forecast"
    assert abs(body["confidence_score"] - 0.92) < 0.001


def test_chat_query_intent_is_none_for_heuristic_fallback(monkeypatch):
    def fake_answer(_: str) -> ChatResponse:
        return ChatResponse(
            answer="Help text",
            insights=[],
            suggestions=[],
            detected_intent="help",
            confidence_score=None,
        )

    monkeypatch.setattr(chat_router, "answer_chat_query", fake_answer)
    client = TestClient(app)
    resp = client.post("/api/v1/chat/query", json={"message": "help me"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["detected_intent"] == "help"
    assert body["confidence_score"] is None
