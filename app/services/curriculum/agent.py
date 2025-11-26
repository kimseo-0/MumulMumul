# app/services/curriculum/agent.py

from typing import Any, Dict, List

from sqlalchemy.orm import Session
from pymongo.database import Database

from .schemas import CurriculumReportPayload, CurriculumAIInsights
from .repository import (
    get_weekly_curriculum_logs,
    aggregate_curriculum_stats,
)
from .llm import generate_curriculum_ai_insights


def generate_ai_insights(
    db: Session,
    mongo_db: Database,
    camp_id: int,
    week_index: int,
) -> CurriculumReportPayload:
    # 1) Mongo + SQL → N주차 user 질문 로그
    weekly_logs: List[Dict[str, Any]] = get_weekly_curriculum_logs(
        db=db,
        mongo_db=mongo_db,
        camp_id=camp_id,
        week_index=week_index,
    )

    # 2) 집계
    stats: Dict[str, Any] = aggregate_curriculum_stats(weekly_logs)

    # 3) LLM 인사이트
    ai_insights: CurriculumAIInsights = generate_curriculum_ai_insights(
        stats.get("raw_stats", stats)
    )

    # 4) 최종 payload
    payload = CurriculumReportPayload(
        summary_cards=stats["summary_cards"],
        charts=stats["charts"],
        tables=stats["tables"],
        ai_insights=ai_insights,
    )
    return payload
