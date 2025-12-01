# app/services/curriculum/service.py
from sqlalchemy.orm import Session
from pymongo.database import Database

from app.services.curriculum.judge_learning_chat.judge_runner import judge_weekly_logs
from app.services.db_service.learning_chat_log import fetch_weekly_logs, get_week_range_by_index

from .schemas import CurriculumReportPayload
from .agent import generate_curriculum_report


def create_curriculum_report(
    db: Session,
    mongo_db: Database,
    camp_id: int,
    week_index: int,
) -> CurriculumReportPayload:
    """
    캠프 ID와 주차 인덱스를 받아서 커리큘럼 리포트를 생성/조회
    """

    # TODO : 디비에서 리포트 가져오기

    # TODO : 리포트가 있으면 반환
    
    # TODO : 만약 리포트가 없을 경우 생성 > generate_ai_insights

    # 해당 주차 로그에 대해 LLM enrichment가 되어있는지 확인하고, 필요시 enrichment 수행
    week_start, week_end = get_week_range_by_index(camp_id, week_index)
    judge_weekly_logs(camp_id=camp_id, week_start=week_start, week_end=week_end)

    # 주차 로그 조회
    weekly_logs = fetch_weekly_logs(camp_id=camp_id, week_index=week_index)

    # 리포트 생성
    report = generate_curriculum_report(weekly_logs)

    # TODO : 리포트 저장

    return report
