# app/api/curriculum.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pymongo.database import Database

from app.core.db import get_db
from app.core.mongodb import get_mongo_db
from app.core.schemas import Camp
from app.services.curriculum.service import create_curriculum_report
from app.services.curriculum.schemas import CurriculumReportPayload

router = APIRouter()


@router.get("/camps")
def list_camps(db: Session = Depends(get_db)):
    """
    스트림릿 사이드바에서 '반 선택' 드롭다운용 캠프 목록 API
    """
    camps = db.query(Camp).all()
    return [
        {
            "camp_id": camp.camp_id,
            "name": camp.name,
        }
        for camp in camps
    ]


@router.get(
    "/report",
    response_model=CurriculumReportPayload,
)
def get_curriculum_report(
    camp_id: int,
    week_index: int,  # "Week 1" / "Week 2" ...
    db: Session = Depends(get_db),
    mongo_db: Database = Depends(get_mongo_db),
):
    """
    특정 캠프 + 특정 주차의 커리큘럼 리포트 전체 Payload 반환 API
    (summary_cards, charts, tables, ai_insights 모두 포함)
    """
    payload = create_curriculum_report(
        db=db,
        mongo_db=mongo_db,
        camp_id=camp_id,
        week_index=week_index,
    )
    return payload
