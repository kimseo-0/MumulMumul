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
        "summary_cards": CurriculumSummaryCards,
        "charts": CurriculumCharts,
        "tables": CurriculumTables,
        "raw_stats": {...},   # LLM용 생데이터
    }
    """

    total_questions = len(weekly_logs)

    in_count = 0
    out_count = 0

    # (category, scope) 단위로 카운트
    by_category_scope: Counter[Tuple[str, CurriculumScope]] = Counter()

    # 카테고리별 예시 질문 (LLM용)
    example_questions_per_category: defaultdict[str, List[str]] = defaultdict(list)

    # 테이블용 QuestionRow 리스트
    question_rows: List[QuestionRow] = []

    # 카테고리별 scope 카운트 (TopQuestionCategory의 scope 결정을 위해)
    category_scope_counts: defaultdict[str, Counter] = defaultdict(Counter)

    for log in weekly_logs:
        # scope: "in" / "out" / None
        scope_raw = log.get("curriculum_scope") or "in"
        scope: CurriculumScope = "in" if scope_raw == "in" else "out"

        category = (log.get("question_category") or "기타").strip() or "기타"
        content = log.get("content") or ""

        if scope == "in":
            in_count += 1
        else:
            out_count += 1

        by_category_scope[(category, scope)] += 1
        category_scope_counts[category][scope] += 1

        # LLM용 예시 질문
        if len(example_questions_per_category[category]) < 5 and content:
            example_questions_per_category[category].append(content)

        # created_at 파싱
        created_at_val = log.get("created_at")
        created_at_dt: datetime | None = None
        if isinstance(created_at_val, datetime):
            created_at_dt = created_at_val
        elif isinstance(created_at_val, str):
            try:
                created_at_dt = datetime.fromisoformat(created_at_val)
            except Exception:
                created_at_dt = None

        # question_id (Mongo ObjectId 등)
        raw_id = log.get("_id") or log.get("id")
        question_id = str(raw_id) if raw_id is not None else None

        question_rows.append(
            QuestionRow(
                question_id=question_id,
                user_id=log.get("user_id"),
                camp_id=log.get("camp_id"),
                scope=scope,
                category=category,
                question_text=content,
                answer_summary=log.get("answer_summary"),
                created_at=created_at_dt,
            )
        )

    # 비율 계산 (0으로 나누기 방지)
    curriculum_out_ratio = (
        out_count / total_questions if total_questions > 0 else 0.0
    )

    # -------------------------------
    # 상위 카테고리 (scope 상관없이)
    # -------------------------------
    by_category_total: Counter[str] = Counter()
    for (cat, _scope), cnt in by_category_scope.items():
        by_category_total[cat] += cnt

    # Top 3 카테고리
    top_categories_sorted = by_category_total.most_common(3)

    # 카테고리별 대표 scope (in/out 중 더 많이 나온 쪽)
    def get_main_scope_for_category(cat: str) -> CurriculumScope:
        counts = category_scope_counts[cat]
        in_cnt = counts.get("in", 0)
        out_cnt = counts.get("out", 0)
        return "in" if in_cnt >= out_cnt else "out"

    # TopQuestionCategory 리스트
    top_question_categories: List[TopQuestionCategory] = []
    for cat, cnt in top_categories_sorted:
        main_scope = get_main_scope_for_category(cat)
        top_question_categories.append(
            TopQuestionCategory(
                category=cat,
                question_count=cnt,
                scope=main_scope,
            )
        )

    # TopQuestionItem 리스트 (카테고리별 대표 질문 + 전체 개수)
    top_questions: List[TopQuestionItem] = []
    for cat, cnt in top_categories_sorted:
        main_scope = get_main_scope_for_category(cat)
        # 해당 카테고리 + scope에 속하는 첫 질문 하나를 대표로 사용
        q_row = next(
            (
                row
                for row in question_rows
                if row.category == cat and row.scope == main_scope
            ),
            None,
        )
        if q_row:
            top_questions.append(
                TopQuestionItem(
                    question_id=q_row.question_id,
                    category=cat,
                    scope=main_scope,
                    question_text=q_row.question_text,
                    total_count=cnt,
                )
            )

    # -------------------------------
    # Charts: questions_by_category, curriculum_scope_ratio
    # -------------------------------
    questions_by_category_chart: List[CategoryQuestionCount] = []
    for (cat, scope), cnt in by_category_scope.most_common():
        questions_by_category_chart.append(
            CategoryQuestionCount(
                category=cat,
                scope=scope,
                question_count=cnt,
            )
        )

    scope_ratio_chart: List[ScopeRatioPoint] = [
        ScopeRatioPoint(scope="in", question_count=in_count),
        ScopeRatioPoint(scope="out", question_count=out_count),
    ]

    # -------------------------------
    # Tables
    # -------------------------------
    # 1) 분류별로 묶인 질문 리스트
    grouped_blocks_map: dict[tuple[str, CurriculumScope], CategoryQuestionBlock] = {}

    for row in question_rows:
        key = (row.category, row.scope)
        if key not in grouped_blocks_map:
            grouped_blocks_map[key] = CategoryQuestionBlock(
                category=row.category,
                scope=row.scope,
                questions=[],
            )
        grouped_blocks_map[key].questions.append(row)

    questions_grouped_by_category = list(grouped_blocks_map.values())

    # 2) 커리큘럼 외 질문만 리스트
    curriculum_out_questions: List[QuestionRow] = [
        row for row in question_rows if row.scope == "out"
    ]

    # -------------------------------
    # SummaryCards / Charts / Tables 모델 생성
    # -------------------------------
    summary_cards = CurriculumSummaryCards(
        total_questions=total_questions,
        curriculum_out_ratio=curriculum_out_ratio,
        curriculum_in_questions=in_count,
        curriculum_out_questions=out_count,
        top_question_categories=top_question_categories,
        top_questions=top_questions,
    )

    charts = CurriculumCharts(
        questions_by_category=questions_by_category_chart,
        curriculum_scope_ratio=scope_ratio_chart,
    )

    tables = CurriculumTables(
        questions_grouped_by_category=questions_grouped_by_category,
        curriculum_out_questions=curriculum_out_questions,
    )

    # -------------------------------
    # LLM용 raw_stats (그냥 dict로 둬도 됨)
    # -------------------------------
    raw_stats = {
        "total_questions": total_questions,
        "in_count": in_count,
        "out_count": out_count,
        "by_category_scope": [
            {
                "category": cat,
                "scope": scope,
                "count": cnt,
            }
            for (cat, scope), cnt in by_category_scope.most_common()
        ],
        "example_questions_per_category": dict(example_questions_per_category),
    }

    return {
        "summary_cards": summary_cards,
        "charts": charts,
        "tables": tables,
        "raw_stats": raw_stats,
    }