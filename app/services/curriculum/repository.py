# app/services/curriculum/repository.py

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from pymongo.database import Database
from sqlalchemy.orm import Session

from app.core.schemas import Camp


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


# -----------------------------
# 3. 로그 집계 → summary / charts / tables / raw_stats
# -----------------------------
def aggregate_curriculum_stats(
    weekly_logs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    weekly_logs(list[dict])를 받아서, Streamlit/LLM에서 쓰기 좋은 구조로 집계한다.

    반환 구조:
    {
        "summary_cards": {...},
        "charts": {...},
        "tables": {...},
        "raw_stats": {...},
    }
    """

    total_questions = len(weekly_logs)

    # in/out 집계
    in_count = 0
    out_count = 0
    by_category: Counter[str] = Counter()
    example_questions_per_category: defaultdict[str, List[str]] = defaultdict(list)

    # 테이블용 전체 row
    question_rows: List[Dict[str, Any]] = []

    for log in weekly_logs:
        scope = log.get("curriculum_scope")  # "in" / "out" / None
        category = log.get("question_category") or "기타"

        if scope == "in":
            in_count += 1
        elif scope == "out":
            out_count += 1

        by_category[category] += 1
        content = log.get("content", "")

        # LLM용 예시 질문 저장 (카테고리당 최대 5개 정도만 써도 충분)
        if len(example_questions_per_category[category]) < 5 and content:
            example_questions_per_category[category].append(content)

        # 테이블 row 구성
        created_at = log.get("created_at")
        if isinstance(created_at, datetime):
            created_str = created_at.isoformat()
        else:
            created_str = str(created_at)

        question_rows.append(
            {
                "user_id": log.get("user_id"),
                "camp_id": log.get("camp_id"),
                "created_at": created_str,
                "curriculum_scope": scope,
                "question_category": category,
                "content": content,
            }
        )

    # 0으로 나누는 것 방지
    curriculum_out_ratio = (
        out_count / total_questions if total_questions > 0 else 0.0
    )

    # 상위 카테고리 Top3
    top_categories_list = [
        {"category": cat, "count": cnt}
        for cat, cnt in by_category.most_common(3)
    ]

    # charts: 카테고리별 막대, in/out 비율
    questions_by_category_chart = [
        {"category": cat, "count": cnt}
        for cat, cnt in by_category.most_common()
    ]

    scope_ratio_chart = [
        {"scope": "curriculum_in", "count": in_count},
        {"scope": "curriculum_out", "count": out_count},
    ]

    # 커리큘럼 외 질문 리스트
    curriculum_out_questions = [
        row for row in question_rows if row["curriculum_scope"] == "out"
    ]

    # 상위 카테고리별 대표 질문 1개씩 (top_questions)
    top_questions: List[Dict[str, Any]] = []
    for cat, _cnt in by_category.most_common(3):
        q = next(
            (
                row
                for row in question_rows
                if row["question_category"] == cat
            ),
            None,
        )
        if q:
            top_questions.append(q)

    # summary_cards
    summary_cards = {
        "total_questions": total_questions,
        "total_user_questions": total_questions,
        "curriculum_in_questions": in_count,
        "curriculum_out_questions": out_count,
        "curriculum_out_ratio": curriculum_out_ratio,
        "top_categories": top_categories_list,
    }

    charts = {
        "questions_by_category": questions_by_category_chart,
        "curriculum_scope_ratio": scope_ratio_chart,
    }

    tables = {
        # Streamlit에서 raw 테이블로 탐색할 전체 질문
        "questions_by_category": question_rows,
        # 커리큘럼 외 질문만 따로 모은 표
        "curriculum_out_questions": curriculum_out_questions,
        # 상위 카테고리 대표 질문 1개씩
        "top_questions": top_questions,
    }

    raw_stats = {
        "total_questions": total_questions,
        "in_count": in_count,
        "out_count": out_count,
        "by_category": [
            {"category": cat, "count": cnt}
            for cat, cnt in by_category.most_common()
        ],
        "example_questions_per_category": example_questions_per_category,
    }

    return {
        "summary_cards": summary_cards,
        "charts": charts,
        "tables": tables,
        "raw_stats": raw_stats,
    }
