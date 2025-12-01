# app/api/curriculum.py
from datetime import datetime
from http.client import HTTPException
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from pymongo.database import Database

from app.core.db import get_db
from app.core.mongodb import CurriculumWeek, CurriculumConfig, get_mongo_db
from app.core.schemas import Camp
from app.services.curriculum.service import create_curriculum_report
from app.services.curriculum.schemas import CurriculumReportPayload
from app.services.db_service.curriculum_config import get_curriculum_config_for_camp

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

mongo_db: Database = get_mongo_db()
curriculum_col = mongo_db["curriculum_configs"]

class CurriculumConfigIn(BaseModel):
    """
    클라이언트에서 입력받는 커리큘럼 설정.
    camp_id는 URL path에서 받고, 여기에는 주차 정보만 포함.
    """
    weeks: List[CurriculumWeek]


@router.get("/config/{camp_id}", response_model=CurriculumConfig)
def get_curriculum_config(camp_id: int) -> CurriculumConfig:
    doc = curriculum_col.find_one({"camp_id": camp_id})
    if not doc:
        # 없으면 404 대신 "빈 기본값"을 반환하는 것도 가능하지만,
        # 여기서는 명시적으로 404를 사용
        raise HTTPException(status_code=404, detail="Curriculum config not found")

    doc.pop("_id", None)
    return CurriculumConfig(**doc)


@router.post("/config/{camp_id}", response_model=CurriculumConfig)
def upsert_curriculum_config(
    camp_id: int,
    payload: CurriculumConfigIn,
) -> CurriculumConfig:
    now = datetime.utcnow()

    update_doc = {
        "camp_id": camp_id,
        "weeks": [week.model_dump() for week in payload.weeks],
        "updated_at": now,
    }

    upsert_curriculum_config(
        camp_id=camp_id,
        update_doc=update_doc,
    )

    doc = get_curriculum_config_for_camp(camp_id)

    if not doc:
        raise HTTPException(status_code=500, detail="Failed to upsert curriculum config")

    doc.pop("_id", None)
    return CurriculumConfig(**doc)