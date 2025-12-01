# app/services/curriculum/agent.py

from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy.orm import Session
from pymongo.database import Database

from app.core.mongodb import get_mongo_db
from app.services.curriculum.judge_learning_chat.judge_runner import judge_weekly_logs
from app.services.db_service.camp import get_camp_by_id

from .schemas import CurriculumReportPayload, CurriculumAIInsights
from .generate_report.calculator import aggregate_curriculum_stats
from .generate_report.llm import generate_curriculum_ai_insights


def generate_curriculum_report(weekly_logs) -> Dict[str, Any]:
    """
    전체 리포트 생성 파이프라인
    1) 해당 주차 로그 LLM enrichment (없으면)
    2) 주차 로그 조회
    3) 집계
    4) AI 인사이트 생성
    5) 최종 payload 반환
    """
    # 집계
    agg_result = aggregate_curriculum_stats(weekly_logs)
    summary_cards = agg_result["summary_cards"]
    charts = agg_result["charts"]
    tables = agg_result["tables"]
    raw_stats = agg_result["raw_stats"]

    #  AI 인사이트 생성
    ai_insights = generate_curriculum_ai_insights(raw_stats)

    return {
        "summary_cards": summary_cards,
        "charts": charts,
        "tables": tables,
        "ai_insights": ai_insights,
        "raw_stats": raw_stats,
    }
