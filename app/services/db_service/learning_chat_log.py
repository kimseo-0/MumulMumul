from datetime import datetime, timedelta
from typing import Any, Dict, List

from pymongo.database import Database
from app.core.mongodb import get_mongo_db
from app.services.db_service.camp import get_camp_by_id

mongo_db: Database = get_mongo_db()
chat_col = mongo_db["learning_chat_logs"]

def get_week_range_by_index(camp_id: int, week_index: int) -> tuple[datetime, datetime]:
    """
    camp_id, week_index로부터 해당 주차의 시작/끝 날짜를 계산하는 헬퍼.
    여기서는 예시로만 두고, 실제 로직은 캠프 시작일 기준으로 구현.
    """
    camp = get_camp_by_id(camp_id)
    
    camp_start = camp.start_date
    week_start = camp_start + timedelta(weeks=week_index - 1)
    week_end = week_start + timedelta(weeks=1)
    return week_start, week_end


def fetch_weekly_logs(camp_id: int, week_index: int) -> List[Dict[str, Any]]:
    """
    주어진 캠프 / 주차에 해당하는 채팅 로그를 MongoDB에서 모두 조회
    """

    week_start, week_end = get_week_range_by_index(camp_id, week_index)

    query = {
        "camp_id": camp_id,
        "created_at": {"$gte": week_start, "$lt": week_end},
    }
    docs = list(chat_col.find(query))
    return docs


def save_weekly_logs(logs: List[Dict[str, Any]]) -> None:
    """
    주어진 로그 리스트를 MongoDB에 저장한다.
    """
    if not logs:
        return

    chat_col.insert_many(logs)


def update_weekly_log(log_id: Any, update_data: Dict[str, Any]) -> None:
    """
    특정 로그 문서를 업데이트한다.
    """
    chat_col.update_one({"_id": log_id}, {"$set": update_data})