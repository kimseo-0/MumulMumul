from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .schemas import (
    CurriculumScope,
    QuestionRow,
    TopQuestionCategory,
    TopQuestionItem,
    CategoryQuestionCount,
    ScopeRatioPoint,
    CategoryQuestionBlock,
    CurriculumSummaryCards,
    CurriculumCharts,
    CurriculumTables,
)

# -----------------------------
# 내부 유틸 함수들
# -----------------------------


def _normalize_scope(scope_raw: Any) -> CurriculumScope:
    """
    로그에 들어온 curriculum_scope 값을 내부에서 사용하는 'in' / 'out'으로 정규화한다.
    기본값은 'in'임.
    """
    return "in" if scope_raw == "in" else "out"


def parse_weekly_logs(
    weekly_logs: List[Dict[str, Any]],
) -> tuple[
    List[QuestionRow],
    int,  # total_questions
    int,  # in_count
    int,  # out_count
    Counter[Tuple[str, CurriculumScope]],  # by_category_scope
    Dict[str, Counter],  # category_scope_counts
    Dict[str, List[str]],  # example_questions_per_category
]:
    """
    raw weekly_logs(list[dict]) 를 파싱해서
    이후 집계에 필요한 기초 데이터(QuestionRow / 카운트들)를 만든다.
    """

    total_questions = len(weekly_logs)
    in_count = 0
    out_count = 0

    by_category_scope: Counter[Tuple[str, CurriculumScope]] = Counter()
    category_scope_counts: Dict[str, Counter] = defaultdict(Counter)
    questions_per_category: Dict[str, List[str]] = defaultdict(list)
    question_rows: List[QuestionRow] = []

    for log in weekly_logs:
        # 1) scope 정규화
        scope_raw = log.get("curriculum_scope") or "in"
        scope: CurriculumScope = _normalize_scope(scope_raw)

        # 2) 카테고리 / 내용
        category = (log.get("question_category") or "기타").strip() or "기타"
        content = log.get("content") or ""

        # 3) in/out 카운트
        if scope == "in":
            in_count += 1
        else:
            out_count += 1

        # 4) (category, scope) 단위 카운트
        by_category_scope[(category, scope)] += 1
        category_scope_counts[category][scope] += 1

        # 5) LLM용 예시 질문 (카테고리별 최대 5개)
        if len(questions_per_category[category]) < 5 and content:
            questions_per_category[category].append(content)

        # 6) created_at 파싱
        created_at_val = log.get("created_at")
        created_at_dt: datetime | None = None
        if isinstance(created_at_val, datetime):
            created_at_dt = created_at_val
        elif isinstance(created_at_val, str):
            try:
                created_at_dt = datetime.fromisoformat(created_at_val)
            except Exception:
                created_at_dt = None

        # 7) question_id (Mongo ObjectId 등)
        raw_id = log.get("_id") or log.get("id")
        question_id = str(raw_id) if raw_id is not None else None

        # 8) QuestionRow 생성
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

    return (
        question_rows,
        total_questions,
        in_count,
        out_count,
        by_category_scope,
        category_scope_counts,
        questions_per_category,
    )


def _get_main_scope_for_category(
    category: str,
    category_scope_counts: Dict[str, Counter],
) -> CurriculumScope:
    """
    카테고리별로 in/out 중 더 많이 나온 scope 를 대표 scope 로 선택.
    동률이면 in 우선.
    """
    counts = category_scope_counts[category]
    in_cnt = counts.get("in", 0)
    out_cnt = counts.get("out", 0)
    return "in" if in_cnt >= out_cnt else "out"


def build_summary_cards(
    total_questions: int,
    in_count: int,
    out_count: int,
    by_category_scope: Counter[Tuple[str, CurriculumScope]],
    category_scope_counts: Dict[str, Counter],
    question_rows: List[QuestionRow],
) -> CurriculumSummaryCards:
    """
    상단 Summary 카드 영역(CurriculumSummaryCards)을 생성한다.
    - 전체 질문 수
    - 커리큘럼 내/외 비율
    - Top 카테고리 / Top 질문
    """

    curriculum_out_ratio = out_count / total_questions if total_questions > 0 else 0.0

    # 카테고리별 총합
    by_category_total: Counter[str] = Counter()
    for (cat, _scope), cnt in by_category_scope.items():
        by_category_total[cat] += cnt

    # Top 3 카테고리
    top_categories_sorted = by_category_total.most_common(3)

    # TopQuestionCategory 리스트
    top_question_categories: List[TopQuestionCategory] = []
    for cat, cnt in top_categories_sorted:
        main_scope = _get_main_scope_for_category(cat, category_scope_counts)
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
        main_scope = _get_main_scope_for_category(cat, category_scope_counts)
        # 해당 카테고리 + scope 에 속하는 첫 질문 하나를 대표로 사용
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

    return CurriculumSummaryCards(
        total_questions=total_questions,
        curriculum_out_ratio=curriculum_out_ratio,
        curriculum_in_questions=in_count,
        curriculum_out_questions=out_count,
        top_question_categories=top_question_categories,
        top_questions=top_questions,
    )


def build_charts(
    by_category_scope: Counter[Tuple[str, CurriculumScope]],
    in_count: int,
    out_count: int,
) -> CurriculumCharts:
    """
    차트 영역(CurriculumCharts)에 필요한 데이터를 생성한다.
    - 분류별 질문 수 막대 그래프
    - 커리큘럼 내/외 비율 파이 차트
    """

    questions_by_category_chart: List[CategoryQuestionCount] = [
        CategoryQuestionCount(
            category=cat,
            scope=scope,
            question_count=cnt,
        )
        for (cat, scope), cnt in by_category_scope.most_common()
    ]

    scope_ratio_chart: List[ScopeRatioPoint] = [
        ScopeRatioPoint(scope="in", question_count=in_count),
        ScopeRatioPoint(scope="out", question_count=out_count),
    ]

    return CurriculumCharts(
        questions_by_category=questions_by_category_chart,
        curriculum_scope_ratio=scope_ratio_chart,
    )


def build_tables(
    question_rows: List[QuestionRow],
) -> CurriculumTables:
    """
    표 영역(CurriculumTables)에 사용할 데이터를 생성한다.
    - 분류별 질문 리스트
    - 커리큘럼 외 질문 리스트
    """

    # 1) 분류별로 묶인 질문 리스트
    grouped_blocks_map: Dict[Tuple[str, CurriculumScope], CategoryQuestionBlock] = {}

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

    return CurriculumTables(
        questions_grouped_by_category=questions_grouped_by_category,
        curriculum_out_questions=curriculum_out_questions,
    )

def build_raw_stats(
    total_questions: int,
    in_count: int,
    out_count: int,
    by_category_scope: Counter[Tuple[str, CurriculumScope]],
    questions_per_category: Dict[str, List[str]],
) -> Dict[str, Any]:
    """
    LLM 인사이트 생성을 위해 사용하는 raw_stats dict 를 만든다.
    - 커리큘럼 내(in) / 외(out)를 구분해서 카테고리별 통계를 제공
    - 각 카테고리별 예시 질문을 함께 전달
    """

    # 1) 커리큘럼 내/외 카테고리별 집계
    in_categories: Dict[str, int] = {}
    out_categories: Dict[str, int] = {}

    for (cat, scope), cnt in by_category_scope.items():
        if scope == "in":
            in_categories[cat] = in_categories.get(cat, 0) + cnt
        else:
            out_categories[cat] = out_categories.get(cat, 0) + cnt

    # 2) 정렬된 리스트 형태 (빈도 내림차순) + 비율/예시 질문 포함
    in_category_stats = [
        {
            "category": cat,
            "count": cnt,
            "ratio": cnt / in_count if in_count > 0 else 0.0,
            "example_questions": questions_per_category.get(cat, []),
        }
        for cat, cnt in sorted(
            in_categories.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]

    out_category_stats = [
        {
            "category": cat,
            "count": cnt,
            "ratio": cnt / out_count if out_count > 0 else 0.0,
            "example_questions": questions_per_category.get(cat, []),
        }
        for cat, cnt in sorted(
            out_categories.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]

    # 3) 기존 구조 유지 + 확장 필드 추가
    return {
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
        "example_questions_per_category": dict(questions_per_category),
        # 새로 추가된 구조
        "in_category_stats": in_category_stats,
        "out_category_stats": out_category_stats,
    }


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

    (
        question_rows,
        total_questions,
        in_count,
        out_count,
        by_category_scope,
        category_scope_counts,
        questions_per_category,
    ) = parse_weekly_logs(weekly_logs)

    summary_cards = build_summary_cards(
        total_questions=total_questions,
        in_count=in_count,
        out_count=out_count,
        by_category_scope=by_category_scope,
        category_scope_counts=category_scope_counts,
        question_rows=question_rows,
    )

    charts = build_charts(
        by_category_scope=by_category_scope,
        in_count=in_count,
        out_count=out_count,
    )

    tables = build_tables(question_rows=question_rows)

    raw_stats = build_raw_stats(
        total_questions=total_questions,
        in_count=in_count,
        out_count=out_count,
        by_category_scope=by_category_scope,
        questions_per_category=questions_per_category,
    )

    return {
        "summary_cards": summary_cards,
        "charts": charts,
        "tables": tables,
        "raw_stats": raw_stats,
    }