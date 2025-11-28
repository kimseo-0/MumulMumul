# app/services/curriculum/service.py
from sqlalchemy.orm import Session
from pymongo.database import Database

from .schemas import CurriculumReportPayload
from .agent import generate_ai_insights


def create_curriculum_report(
    db: Session,
    mongo_db: Database,
    camp_id: int,
    week_index: int,
) -> CurriculumReportPayload:
    """
    외부(예: FastAPI 라우터, Streamlit API 래퍼)에서 호출할
    최상위 서비스 함수.

    단순히 agent.generate_curriculum_report 를 감싸는 thin-service 레이어임.
    """
    return generate_ai_insights(
        db=db,
        mongo_db=mongo_db,
        camp_id=camp_id,
        week_index=week_index,
    )
