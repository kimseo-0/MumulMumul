# app/api/learning_chatbot_router.py

import sys
sys.path.append("../..")

import json
from typing import Dict, List, Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

router = APIRouter()

# 아주 단순한 in-memory 세션 저장소 (실서비스면 Redis/DB 등으로 교체)
# key: sessionId, value: list of {"role": "user"/"assistant", "content": str}
CHAT_SESSIONS: Dict[str, List[Dict]] = {}


# ===========================
# Pydantic Schemas (REST용)
# ===========================
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatHistoryResponse(BaseModel):
    sessionId: str
    messages: List[ChatMessage]


# ===========================
# WebSocket: 실시간 채팅
# ===========================
@router.websocket("/")
async def learning_chatbot_ws(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"event": "error", "message": "Invalid JSON payload"}
                )
                continue

            event = data.get("event")

            # -------------------------
            # 1) start_chat
            # -------------------------
            if event == "start_chat":
                session_id = data.get("sessionId")
                user_id = data.get("userId")

                if not session_id:
                    await websocket.send_json(
                        {"event": "error", "message": "sessionId is required"}
                    )
                    continue

                # 새 세션 초기화
                CHAT_SESSIONS[session_id] = []
                await websocket.send_json(
                    {
                        "event": "chat_started",
                        "sessionId": session_id,
                        "userId": user_id,
                        "message": "학습 세션이 시작되었습니다.",
                    }
                )

            # -------------------------
            # 2) query
            # -------------------------
            elif event == "query":
                session_id = data.get("sessionId")
                query_text = data.get("query")

                if not session_id or session_id not in CHAT_SESSIONS:
                    await websocket.send_json(
                        {
                            "event": "error",
                            "message": "Invalid or unknown sessionId. 먼저 start_chat을 호출하세요.",
                        }
                    )
                    continue

                # 최소한의 기록 (메모리)
                CHAT_SESSIONS[session_id].append(
                    {"role": "user", "content": query_text}
                )

                # TODO: 실제 학습 도우미 로직 (LLM/RAG 등) 으로 대체
                assistant_reply = f"질문에 대한 예시 답변입니다: {query_text}"

                CHAT_SESSIONS[session_id].append(
                    {"role": "assistant", "content": assistant_reply}
                )

                await websocket.send_json(
                    {
                        "event": "answer",
                        "sessionId": session_id,
                        "answer": assistant_reply,
                    }
                )

            # -------------------------
            # 3) end_chat
            # -------------------------
            elif event == "end_chat":
                session_id = data.get("sessionId")
                if session_id in CHAT_SESSIONS:
                    # 필요하다면 여기서 세션 정리/저장 로직 추가
                    pass

                await websocket.send_json(
                    {
                        "event": "chat_ended",
                        "sessionId": session_id,
                        "message": "학습 세션이 종료되었습니다.",
                    }
                )

            # -------------------------
            # 4) unknown event
            # -------------------------
            else:
                await websocket.send_json(
                    {"event": "error", "message": f"Unknown event: {event}"}
                )

    except WebSocketDisconnect:
        # 클라이언트가 연결 끊었을 때 처리 (필요시)
        pass


# ===========================
# REST: 히스토리 조회 API
# ===========================
@router.get("/history/{session_id}",
    response_model=ChatHistoryResponse,
)
def get_chat_history(session_id: str):
    """
    이전 채팅 기록 조회용 GET API
    - 단순히 메모리에 저장된 CHAT_SESSIONS 에서 가져옴
    - 추후 DB/Redis 저장으로 교체 가능
    """
    messages = CHAT_SESSIONS.get(session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return ChatHistoryResponse(
        sessionId=session_id,
        messages=[ChatMessage(**m) for m in messages],
    )
