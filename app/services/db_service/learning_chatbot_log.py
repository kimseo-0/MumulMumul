from datetime import datetime
from app.core.mongodb import LearningChatLog, get_mongo_db

def get_learning_chatbot_log(userId: int, sessionId: str) -> str:
    db_mongo = get_mongo_db()
    coll = db_mongo["learning_chat_logs"]

    messages = coll.find_all({"user_id": userId, "session_id": sessionId})
    return messages

def save_learning_chatbot_log(records: list[LearningChatLog]):
    db_mongo = get_mongo_db()
    coll = db_mongo["learning_chat_logs"]

    coll.insert_all([record.model_dump() for record in records])