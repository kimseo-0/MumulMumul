# app/services/curriculum/repository.py

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from pymongo.database import Database
from sqlalchemy.orm import Session

from app.core.schemas import Camp
from app.services.curriculum.schemas import (
    CurriculumScope,
    CurriculumSummaryCards,
    CurriculumCharts,
    CurriculumTables,
    TopQuestionCategory,
    TopQuestionItem,
    CategoryQuestionCount,
    ScopeRatioPoint,
    QuestionRow,
    CategoryQuestionBlock,
)


# -----------------------------
# 1. 캠프 N주차 날짜 구간 계산
# -----------------------------
def get_camp_week_range(
    db: Session,
    camp_id: int,
    week_index: int,
) -> Tuple[datetime, datetime]:
    """
    Camp.start_date 기준으로 N주차의 [start, end) 범위를 계산한다.
    - week_index: 1주차=1, 2주차=2 ...
    - 반환값: (week_start, week_end_exclusive)
    """

    camp: Camp | None = db.query(Camp).filter(Camp.camp_id == camp_id).first()
    if camp is None or camp.start_date is None:
        raise ValueError(f"캠프 {camp_id}의 start_date가 설정되어 있지 않음")

    # N주차 시작: start_date + (N-1) * 7일
    week_start = camp.start_date + timedelta(weeks=week_index - 1)
    week_end = week_start + timedelta(days=7)

    # end_date 설정되어 있으면 넘어가지 않게 클램프
    if camp.end_date is not None and week_end > camp.end_date:
        # end_date는 하루의 끝까지 포함되도록 +1일
        week_end = camp.end_date + timedelta(days=1)

    return week_start, week_end


# -----------------------------
# 2. N주차 user 질문 로그 조회
# -----------------------------
def get_weekly_curriculum_logs(
    db: Session,
    mongo_db: Database,
    camp_id: int,
    week_index: int,
) -> List[Dict[str, Any]]:
    """
    learning_chat_logs 컬렉션에서
    - 해당 camp_id
    - role == "user"
    - created_at 이 N주차 범위에 속하는 문서만 가져온다.
    """

    week_start, week_end = get_camp_week_range(db, camp_id, week_index)

    coll = mongo_db["learning_chat_logs"]

    cursor = coll.find(
        {
            "camp_id": camp_id,
            "role": "user",
            "created_at": {
                "$gte": week_start,
                "$lt": week_end,
            },
        }
    )

    # PyMongo Cursor → list[dict]
    logs = list(cursor)
    return logs