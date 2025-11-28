# app/api/learning_chatbot_router.py

from datetime import datetime
import sys
sys.path.append("../..")

import json
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from app.services.learning_chatbot.service import answer

from app.core.mongodb import LearningChatLog
from app.services.db_service.learning_chatbot_log import get_learning_chatbot_log, save_learning_chatbot_log

router = APIRouter()

# 아주 단순한 in-memory 세션 저장소 (실서비스면 Redis/DB 등으로 교체)
# key: sessionId, value: list of {"role": "user"/"assistant", "content": str}
CHAT_SESSIONS: Dict[str, List[Dict]] = {}


# ===========================
# Pydantic Schemas (REST용)
# ===========================
class ChatMessage(BaseModel):
    user_id: int
    session_id: Optional[int] = None

    role: Literal["user", "assistant"]
    content: str

    created_at: datetime = datetime.utcnow()


class ChatHistoryResponse(BaseModel):
    sessionId: int
    userId: int
    messages: List[ChatMessage]


# ===========================
# WebSocket: 실시간 채팅
# ===========================
@router.websocket("/")
async def learning_chatbot_ws(websocket: WebSocket):
    print(f"client connected : {websocket.client}")
    await websocket.accept() # client의 websocket접속 허용
    await websocket.send_text(f"Welcome client : {websocket.client}")

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
                print(f"학습 세션 시작 : sessionid-{session_id} userid-{user_id}")
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
                user_id = data.get("userId")
                query_text = data.get("query")

                if not session_id or session_id not in CHAT_SESSIONS:
                    CHAT_SESSIONS[session_id] = []
                    print(f"학습 세션 시작 : sessionId-{session_id} userId-{user_id}")

                user_record = LearningChatLog(
                    user_id=user_id,
                    session_id=session_id,
                    role="user",
                    content= query_text,
                    created_at=datetime.now(),
                )
                save_learning_chatbot_log([user_record])
                CHAT_SESSIONS[session_id].append(
                    {"role": "user", "content": query_text}
                )
                
                print(f"학습 쿼리 요청 : sessionId-{session_id} userId-{user_id} query-{query_text}")
                assistant_reply = answer(query_text)

                assistant_record = LearningChatLog(
                    user_id=user_id,
                    session_id=session_id,
                    role="assistant",
                    content= assistant_reply,
                    created_at=datetime.now(),
                )
                save_learning_chatbot_log([assistant_record])
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
                # if session_id in CHAT_SESSIONS:
                #     # 필요하다면 여기서 세션 정리/저장 로직 추가
                #     pass

                print(f"학습 세션 종료 : sessionId-{session_id} userId-{data.get('userId')}")
                await websocket.send_json(
                    {
                        "event": "chat_ended",
                        "sessionId": session_id,
                        "message": "학습 세션이 종료되었습니다.",
                    }
                )
                await websocket.close()  # 서버에서 웹소켓 연결 종료
                break

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
@router.get("/history/{user_id}/{session_id}",
    response_model=ChatHistoryResponse,
)
def get_chat_history(user_id: int, session_id: str):
    """
    이전 채팅 기록 조회용 GET API
    """
    messages = get_learning_chatbot_log(userId=user_id, sessionId=session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return ChatHistoryResponse(
        sessionId=session_id,
        userId=user_id,
        messages=[ChatMessage(**m) for m in messages],
    )
