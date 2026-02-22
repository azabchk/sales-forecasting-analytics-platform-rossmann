from fastapi import APIRouter, HTTPException

from app.schemas import ChatQueryRequest, ChatResponse
from app.services.chat_service import answer_chat_query

router = APIRouter()


@router.post("/chat/query", response_model=ChatResponse)
def chat_query(payload: ChatQueryRequest) -> ChatResponse:
    try:
        return answer_chat_query(payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Chat error: {exc}") from exc
