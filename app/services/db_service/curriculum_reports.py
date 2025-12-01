from typing import Dict, Any
from app.core.mongodb import get_mongo_db


mongo_db = get_mongo_db()
report_col = mongo_db["curriculum_reports"]

def get_curriculum_report(
    camp_id: int,
    week_index: int,
) -> Dict[str, Any] | None:
    """
    MongoDB에서 기존 커리큘럼 리포트를 조회한다.
    없으면 None 반환.
    """
    report = report_col.find_one(
            {"camp_id": camp_id, "week_index": week_index}
        )
    return report

def upsert_curriculum_report(
    camp_id: int,
    week_index: int,
    report_data: Dict[str, Any],
) -> None:
    """
    MongoDB에 커리큘럼 리포트를 upsert 한다.
    """
    report_col.update_one(
        {"camp_id": camp_id, "week_index": week_index},
        {"$set": report_data},
        upsert=True,
    )