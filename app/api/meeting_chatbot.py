# app/api/meeting_chatbot.py

from datetime import datetime
import sys
sys.path.append("../..")

import json
from typing import Dict, List, Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from app.services.learning_chatbot.service import answer  # TODO: 회의용 답변 로직으로 분리할지 검토
from app.core.mongodb import get_mongo_db

router = APIRouter()

# team_chat과 동일한 컬렉션 사용
mongo_db = get_mongo_db()
collection = mongo_db["team_chat_messages"]

# 메모리 세션 (필요하면 제거 가능)
CHAT_SESSIONS: Dict[str, List[Dict]] = {}


# ===========================
# Pydantic Schemas (REST용)
# ===========================
class MeetingChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    createdAt: str  # ISO8601 string


class ChatHistoryResponse(BaseModel):
    sessionId: str
    userId: int
    messages: List[MeetingChatMessage]


# ===========================
# WebSocket: 회의 미팅 도우미 채팅
# ===========================
@router.websocket("/")
async def meeting_chatbot_ws(websocket: WebSocket):
    """
    회의 미팅 도우미용 WebSocket
    - event: "start_chat" / "query" / "end_chat"
    - 메시지는 team_chat_messages 컬렉션에 type="ai" 으로 저장
    """
    print(f"[MeetingChat] client connected : {websocket.client}")
    await websocket.accept()
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
                session_id = str(data.get("sessionId"))
                user_id = data.get("userId")
                user_name = data.get("userName", "")

                if not session_id:
                    await websocket.send_json(
                        {"event": "error", "message": "sessionId is required"}
                    )
                    continue

                CHAT_SESSIONS[session_id] = []
                print(f"[MeetingChat] 세션 시작 : sessionId-{session_id} userId-{user_id}")

                await websocket.send_json(
                    {
                        "event": "chat_started",
                        "sessionId": session_id,
                        "userId": user_id,
                        "userName": user_name,
                        "message": "회의 미팅 도우미 세션이 시작되었습니다.",
                    }
                )

            # -------------------------
            # 2) query (user → AI)
            # -------------------------
            elif event == "query":
                session_id = str(data.get("sessionId"))
                user_id = data.get("userId")
                user_name = data.get("userName", "")
                query_text = data.get("query")

                if not session_id:
                    await websocket.send_json(
                        {"event": "error", "message": "sessionId is required"}
                    )
                    continue

                if session_id not in CHAT_SESSIONS:
                    CHAT_SESSIONS[session_id] = []
                    print(f"[MeetingChat] 세션 자동 생성 : sessionId-{session_id} userId-{user_id}")

                # 1) user 메시지 MongoDB 저장 (type="ai", role="user")
                user_doc = {
                    "roomId": session_id,
                    "type": "ai",
                    "role": "user",
                    "userId": user_id,
                    "userName": user_name,
                    "message": query_text,
                    "createdAt": datetime.utcnow().isoformat(),
                }
                collection.insert_one(user_doc)
                CHAT_SESSIONS[session_id].append(user_doc)

                print(
                    f"[MeetingChat] 쿼리 요청 : sessionId-{session_id} userId-{user_id} query-{query_text}"
                )

                # 2) AI 답변 생성
                # TODO: 회의 전용 answer 로직으로 교체
                assistant_reply = "테스트 답변입니다."

                # 3) assistant 메시지 MongoDB 저장 (type="ai", role="assistant")
                assistant_doc = {
                    "roomId": session_id,
                    "type": "ai",
                    "role": "assistant",
                    "userId": None,
                    "userName": "AI",
                    "message": assistant_reply,
                    "createdAt": datetime.utcnow().isoformat(),
                }
                collection.insert_one(assistant_doc)
                CHAT_SESSIONS[session_id].append(assistant_doc)

                # 4) 클라이언트로 전송
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
                session_id = str(data.get("sessionId"))
                print(
                    f"[MeetingChat] 세션 종료 : sessionId-{session_id} userId-{data.get('userId')}"
                )

                await websocket.send_json(
                    {
                        "event": "chat_ended",
                        "sessionId": session_id,
                        "message": "회의 미팅 도우미 세션이 종료되었습니다.",
                    }
                )
                await websocket.close()
                break

            # -------------------------
            # 4) unknown event
            # -------------------------
            else:
                await websocket.send_json(
                    {"event": "error", "message": f"Unknown event: {event}"}
                )

    except WebSocketDisconnect:
        print("[MeetingChat] client disconnected")
        pass


# ===========================
# REST: 히스토리 조회 API
# ===========================
@router.get(
    "/history/{user_id}/{session_id}",
    response_model=ChatHistoryResponse,
)
def get_meeting_chat_history(user_id: int, session_id: str):
    """
    회의 미팅 도우미 채팅 기록 조회 (HTTP)
    - team_chat_messages 컬렉션에서 type="ai" 인 메시지만 가져옴
    - roomId = session_id
    """

    cursor = (
        collection.find(
            {
                "roomId": str(session_id),
                "type": "ai",
                # user 기준으로 필터링하고 싶지 않으면 이 조건은 빼도 됨
                # "userId": user_id
            }
        )
        .sort("createdAt", 1)
    )

    messages: List[MeetingChatMessage] = []
    for doc in cursor:
        messages.append(
            MeetingChatMessage(
                role=doc.get("role", "user"),
                content=doc.get("message", ""),
                createdAt=doc.get("createdAt", datetime.utcnow().isoformat()),
            )
        )

    if not messages:
        raise HTTPException(
            status_code=404,
            detail={
                "errorCode": "SESSION_NOT_FOUND",
                "message": "해당 세션의 회의 미팅 도우미 기록을 찾을 수 없습니다.",
            },
        )

    return ChatHistoryResponse(
        sessionId=str(session_id),
        userId=user_id,
        messages=messages,
    )
