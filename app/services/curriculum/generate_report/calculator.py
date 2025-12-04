from collections import Counter, defaultdict
from datetime import datetime
import math
from typing import Any, Dict, List, Tuple

from ..schemas import (
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

def parse_weekly_logs(weekly_logs: List[Dict[str, Any]]) -> tuple[
    List[QuestionRow],
    int,  # total_questions
    int,  # in_count
    int,  # out_count
    Counter[Tuple[str, CurriculumScope]],  # by_category_scope
    Dict[str, Counter],  # category_scope_counts
    Dict[str, List[str]],  # example_questions_per_category
    Dict[Tuple[str, CurriculumScope], set],  # users_per_category_scope
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

    #  (category, scope)별 unique user 집계
    users_per_category_scope: Dict[Tuple[str, CurriculumScope], set] = defaultdict(set)

    pattern_tags_per_category: Dict[str, Counter] = defaultdict(Counter)
    pattern_tags_overall: Counter[str] = Counter()

    for log in weekly_logs:

        insights = log.get("curriculum_insights") or {}

        # 1) scope
        scope_raw = insights.get("scope") or "in"
        scope: CurriculumScope = _normalize_scope(scope_raw)

        # 2) category/topic
        category = insights.get("topic") or "기타"
        category = category.strip() or "기타"

        # 3) content
        content = log.get("content") or ""

        # 4) in/out count
        if scope == "in":
            in_count += 1
        else:
            out_count += 1

        # 5) category scope count
        key = (category, scope)
        by_category_scope[key] += 1
        category_scope_counts[category][scope] += 1

        # 6) example questions 저장
        if len(questions_per_category[category]) < 5 and content:
            questions_per_category[category].append(content)

        # 7) unique user count
        user_id = log.get("user_id")
        if user_id:
            users_per_category_scope[key].add(user_id)

        # 8) pattern_tags 집계
        tags = insights.get("pattern_tags") or []
        for tag in tags:
            pattern_tags_per_category[category][tag] += 1
            pattern_tags_overall[tag] += 1
        
        intent = insights.get("intent")
            
        # 9) created_at 파싱
        created_at_val = log.get("created_at")
        created_at_dt: datetime | None = None
        if isinstance(created_at_val, datetime):
            created_at_dt = created_at_val
        elif isinstance(created_at_val, str):
            try:
                created_at_dt = datetime.fromisoformat(created_at_val)
            except Exception:
                created_at_dt = None

        # QuestionRow 생성
        question_rows.append(
            QuestionRow(
                question_id=str(log.get("_id")),
                user_id=log.get("user_id"),
                camp_id=log.get("camp_id"),
                scope=scope,
                category=category,
                question_text=content,
                answer_summary=log.get("answer_summary"),
                created_at=created_at_dt,
                pattern_tags=tags,
                intent=intent,
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
        users_per_category_scope,
        pattern_tags_per_category,
        pattern_tags_overall,
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

def classify_difficulty(score: float) -> str:
    """
    difficulty_score를 high / medium / low로 나누는 헬퍼.
    구간은 이후 운영진 의견에 따라 조정 가능.
    """
    if score >= 5.0:
        return "high"
    elif score >= 3.0:
        return "medium"
    else:
        return "low"


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
    users_per_category_scope: Dict[Tuple[str, CurriculumScope], set],
    pattern_tags_per_category: Dict[str, Counter],
    pattern_tags_overall: Counter[str],
    question_rows: List[QuestionRow]
) -> Dict[str, Any]:
    """
    LLM 인사이트 생성을 위해 사용하는 raw_stats dict 를 만든다.
    - 커리큘럼 내(in) / 외(out)를 구분해서 카테고리별 통계를 제공
    - 각 카테고리별 예시 질문을 함께 전달
    """

    # 1) 커리큘럼 내/외 카테고리별 집계 + unique user 집계
    in_categories: Dict[str, int] = {}
    out_categories: Dict[str, int] = {}
    in_unique_users: Dict[str, int] = {}
    out_unique_users: Dict[str, int] = {}

    for (cat, scope), cnt in by_category_scope.items():
        users = users_per_category_scope.get((cat, scope), set())
        u_cnt = len(users)

        if scope == "in":
            in_categories[cat] = in_categories.get(cat, 0) + cnt
            in_unique_users[cat] = in_unique_users.get(cat, 0) + u_cnt
        else:
            out_categories[cat] = out_categories.get(cat, 0) + cnt
            out_unique_users[cat] = out_unique_users.get(cat, 0) + u_cnt

    # in/out 합계가 0일 때 0으로 나누기 방지용
    in_total = in_count if in_count > 0 else 1
    out_total = out_count if out_count > 0 else 1

    # 2) 정렬된 리스트 형태 (빈도 내림차순) + 비율/예시 질문 + 난이도 점수 포함
    in_category_stats = []
    for cat, cnt in sorted(in_categories.items(), key=lambda x: x[1], reverse=True):
        unique_users = in_unique_users.get(cat, 0)
        ratio = cnt / in_total if in_total > 0 else 0.0
        difficulty_score = math.log(1 + cnt) + 1.5 * unique_users
        difficulty_level = classify_difficulty(difficulty_score)

        pattern_counts = dict(pattern_tags_per_category.get(cat, {}))

        in_category_stats.append(
            {
                "category": cat,
                "count": cnt,
                "unique_users": unique_users,
                "ratio": ratio,
                "difficulty_score": difficulty_score,
                "difficulty_level": difficulty_level,
                "pattern_counts": pattern_counts,
                "example_questions": questions_per_category.get(cat, []),
            }
        )

    out_category_stats = []
    for cat, cnt in sorted(out_categories.items(), key=lambda x: x[1], reverse=True):
        unique_users = out_unique_users.get(cat, 0)
        ratio = cnt / out_total if out_total > 0 else 0.0
        difficulty_score = math.log(1 + cnt) + 1.5 * unique_users
        difficulty_level = classify_difficulty(difficulty_score)
        pattern_counts = dict(pattern_tags_per_category.get(cat, {}))

        out_category_stats.append(
            {
                "category": cat,
                "count": cnt,
                "unique_users": unique_users,
                "ratio": ratio,
                "difficulty_score": difficulty_score,
                "difficulty_level": difficulty_level,
                "pattern_counts": pattern_counts,
                "example_questions": questions_per_category.get(cat, []),
            }
        )
    
    # 3) 전체 pattern_tags 통계
    total_pattern_count = sum(pattern_tags_overall.values()) or 1

    pattern_counter: Counter[str] = Counter()
    category_pattern_counter: Dict[str, Counter] = defaultdict(Counter)
    
    for row in question_rows:
        for tag in row.pattern_tags:
            pattern_counter[tag] += 1
            category_pattern_counter[row.category][tag] += 1
    
    pattern_stats = []
    for tag, cnt in pattern_counter.most_common():
        ratio = cnt / total_questions if total_questions > 0 else 0.0
        pattern_stats.append(
            {
                "tag": tag,
                "count": cnt,
                "ratio": ratio,
            }
        )
        
    category_pattern_summary = []
    for category, counter in category_pattern_counter.items():
        top_patterns = counter.most_common(3)
        pattern_str = ", ".join(f"{t}({c})" for t, c in top_patterns)
        category_pattern_summary.append(
            {
                "category": category,
                "patterns": [
                    {"tag": t, "count": c}
                    for t, c in top_patterns
                ],
            }
        )
    
    # difficulty_score 기준 정렬 후 Top 3 추출
    sorted_stats = sorted(
        in_category_stats,
        key=lambda x: x.get("difficulty_score", 0.0),
        reverse=True,
    )

    priority_rows = []
    for rank, row in enumerate(sorted_stats[:3], start=1):
        level = classify_difficulty(row["difficulty_score"])  # high/medium/low
        priority_rows.append(
            {
                "rank": rank,
                "category": row["category"],
                "difficulty_level": level.capitalize(),
                "main_patterns": [],  # 나중에 패턴 기반으로 채워도 됨
                "action_hint": "",    # LLM이 생성한 문구를 넣어도 되고
            }
        )

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
        "in_category_stats": in_category_stats,
        "out_category_stats": out_category_stats,
        "pattern_stats": pattern_stats,
        "category_pattern_summary": category_pattern_summary,
        "priority": priority_rows
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
        users_per_category_scope,
        pattern_tags_per_category,
        pattern_tags_overall,
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
        users_per_category_scope=users_per_category_scope,
        pattern_tags_per_category=pattern_tags_per_category,
        pattern_tags_overall=pattern_tags_overall,
        question_rows=question_rows,
    )

    return {
        "summary_cards": summary_cards,
        "charts": charts,
        "tables": tables,
        "raw_stats": raw_stats,
    }