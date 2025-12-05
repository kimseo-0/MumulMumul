from datetime import datetime
from typing import Dict, List
from app.core.mongodb import LearningChatLog, get_mongo_db, ChatMessage
from pymongo.database import Database
from app.core.db import get_db

mongo_db: Database = get_mongo_db()
chat_col = mongo_db["learning_chat_logs"]


# ===========================
# In-Memory Chat Sessions
# ===========================
CHAT_SESSIONS: Dict[str, List[ChatMessage]] = {}

# ===========================
# DB Service Functions
# ===========================
def get_learning_chatbot_log(userId: int, sessionId: int) -> List[ChatMessage]:
    learning_chat_logs = chat_col.find({"user_id": userId, "session_id": sessionId})
    chat_messages = [ChatMessage(
        role=log['role'],
        content=log['content'],
        created_at=log['created_at'],
    ) for log in learning_chat_logs]
    print(chat_messages)
    CHAT_SESSIONS[sessionId] = chat_messages

    return chat_messages

def save_learning_chatbot_log(userId: int, sessionId: int, records: list[ChatMessage]):
    learning_chat_logs = [
        LearningChatLog(
            user_id=userId,
            session_id=sessionId,
            role=record.role,
            content=record.content,
            created_at=record.created_at,
        )   for record in records
    ]
    chat_col.insert_many([log.model_dump() for log in learning_chat_logs])