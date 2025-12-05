from datetime import datetime, timedelta
from typing import Any, Dict, List

from bson import ObjectId
from pymongo.database import Database
from requests import Session
from app.core.db import get_db
from app.core.mongodb import CurriculumInsights, LearningChatLog, get_mongo_db
from app.services.db_service.camp import get_camp_by_id

mongo_db: Database = get_mongo_db()
chat_col = mongo_db["learning_chat_logs"]

db = get_db()

def get_week_range_by_index(db: Session, camp_id: int, week_index: int) -> tuple[datetime, datetime]:
    """
    camp_id, week_index로부터 해당 주차의 시작/끝 날짜를 계산하는 헬퍼.
    여기서는 예시로만 두고, 실제 로직은 캠프 시작일 기준으로 구현.
    """
    camp = get_camp_by_id(db, camp_id)
    
    camp_start = camp.start_date
    week_start = camp_start + timedelta(weeks=week_index - 1)
    week_end = week_start + timedelta(weeks=1)
    return week_start, week_end


def fetch_weekly_logs(db: Session, camp_id: int, week_index: int) -> List[Dict[str, Any]]:
    """
    주어진 캠프 / 주차에 해당하는 채팅 로그를 MongoDB에서 모두 조회
    """

    week_start, week_end = get_week_range_by_index(db, camp_id, week_index)

    query = {
        "camp_id": camp_id,
        "created_at": {"$gte": week_start, "$lt": week_end},
    }
    docs = list(chat_col.find(query))
    return docs

def fetch_weekly_logs_no_insights(db: Session, camp_id: int, week_index: int) -> List[Dict[str, Any]]:
    """
    주어진 캠프 / 주차에 해당하는 채팅 로그를 MongoDB에서 모두 조회
    """

    week_start, week_end = get_week_range_by_index(db, camp_id, week_index)

    query = {
        "camp_id": camp_id,
        "created_at": {"$gte": week_start, "$lt": week_end},
        "$or": [
            {"curriculum_insights": {"$eq": None}},
            {"curriculum_insights": {"$exists": False}},
            ]
    }
    docs = list(chat_col.find(query))
    return docs

def update_weekly_log(log_id: Any, update_data: Dict[str, Any]) -> None:
    """
    특정 로그 문서를 업데이트한다.
    """
    chat_col.update_one({"_id": log_id}, {"$set": update_data})

def update_insights_for_logs(insights: List[CurriculumInsights]) -> None:
    """
    특정 로그 문서에 curriculum_insights 필드를 업데이트한다.
    """
    for insight in insights:
        id = ObjectId(insight.id)
        chat_col.update_one(
            {"_id": id},
            {
                "$set": {
                    "curriculum_insights": {
                        "id": id,
                        "topic": insight.topic,
                        "scope": insight.scope,
                        "intent": insight.intent,
                        "pattern_tags": insight.pattern_tags,
                    }
                }
            },
        )