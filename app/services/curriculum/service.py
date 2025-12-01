# app/services/curriculum/service.py
from sqlalchemy.orm import Session
from pymongo.database import Database

from app.services.curriculum.generate_insights.judge_pipeline import compute_curriculum_insights_for_week
from app.services.db_service.curriculum_reports import get_curriculum_report, upsert_curriculum_report
from app.services.db_service.learning_chat_log import fetch_weekly_logs, get_week_range_by_index

from .schemas import CurriculumReportPayload
from .agent import generate_curriculum_report


from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session
from pymongo.database import Database

from .schemas import CurriculumReportPayload


def create_curriculum_report(
    db: Session,
    mongo_db: Database,
    camp_id: int,
    week_index: int,
) -> CurriculumReportPayload:
    """
    캠프 ID와 주차 인덱스를 받아서 커리큘럼 리포트를 생성/조회.
    """

    # 1) 기존 리포트 조회
    existing = get_curriculum_report(camp_id, week_index)
    if existing:
        # Mongo _id 제거 후 Pydantic 모델로 변환
        existing.pop("_id", None)
        return CurriculumReportPayload(**existing)

    # 2) 리포트가 없으면 새로 생성

    # 2-1) 해당 주차 범위 계산
    week_start, week_end = get_week_range_by_index(camp_id, week_index)

    # 2-2) 해당 주차 로그에 대해 CurriculumInsights 없으면 생성
    compute_curriculum_insights_for_week(
        camp_id=camp_id,
        week_start=week_start,
        week_end=week_end,
    )

    # 2-3) 주차 로그 조회 (이미 insights가 붙어 있다고 가정)
    weekly_logs = fetch_weekly_logs(camp_id=camp_id, week_index=week_index)

    # 2-4) 리포트 생성
    report: CurriculumReportPayload = generate_curriculum_report(
        camp_id=camp_id,
        weekly_logs=weekly_logs,
    )

    # 3) 리포트 MongoDB에 저장
    now = datetime.utcnow()
    doc = report.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now

    upsert_curriculum_report(camp_id=camp_id, week_index=week_index, report_data=doc)

    return report

