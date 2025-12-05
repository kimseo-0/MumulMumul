# app/services/curriculum/schemas.py

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


# --------------------------------
# 공통 타입
# --------------------------------

CurriculumScope = Literal["in", "out"]  # 커리큘럼 내/외


# --------------------------------
# (1) Summary Cards
# --------------------------------

class TopQuestionCategory(BaseModel):
    """이번 주 상위 질문 카테고리 요약 (카드/텍스트에 사용)."""

    category: str = Field(..., description="예: 'Numpy 배열', 'Pandas 전처리', '포트폴리오'")
    question_count: int = Field(..., description="해당 카테고리 질문 수")
    scope: CurriculumScope = Field(..., description="'in' = 커리큘럼 내, 'out' = 커리큘럼 외")


class TopQuestionItem(BaseModel):
    """이번 주 상위 질문 리스트용 아이템 (요약 탭 상단 리스트)."""

    question_id: Optional[str] = Field(
        None, description="로그 식별용 ID (Mongo ObjectId 등 문자열로)"
    )
    category: str = Field(..., description="질문 분류명")
    scope: CurriculumScope = Field(..., description="'in' / 'out'")
    question_text: str = Field(..., description="실제 질문 예시 문장 1개")
    total_count: int = Field(..., description="같은 유형으로 묶인 질문 총 개수")


class CurriculumSummaryCards(BaseModel):
    """요약 탭 상단 카드 영역 데이터."""

    total_questions: int = Field(..., description="이번 주 전체 질문 수")
    curriculum_out_ratio: float = Field(
        ...,
        description="커리큘럼 외 질문 비율 (0~1 사이, UI에서는 %로 변환해서 사용)",
    )
    curriculum_in_questions: int = Field(..., description="커리큘럼 내 질문 수")
    curriculum_out_questions: int = Field(..., description="커리큘럼 외 질문 수")

    top_question_categories: List[TopQuestionCategory] = Field(
        default_factory=list,
        description="이번 주 상위 질문 카테고리 Top N (보통 3개)",
    )
    top_questions: List[TopQuestionItem] = Field(
        default_factory=list,
        description="이번 주 상위 질문 리스트 (가장 많이 물어본 질문 Top N)",
    )


# --------------------------------
# (2) Charts
# --------------------------------

class CategoryQuestionCount(BaseModel):
    """질문 분류별 질문 수 (막대 그래프용)."""

    category: str = Field(..., description="질문 분류명")
    scope: CurriculumScope = Field(..., description="'in' / 'out'")
    question_count: int = Field(..., description="질문 수")


class ScopeRatioPoint(BaseModel):
    """커리큘럼 내/외 질문 비율 (파이/도넛 차트용)."""

    scope: CurriculumScope = Field(..., description="'in' / 'out'")
    question_count: int = Field(..., description="질문 수")


class CurriculumCharts(BaseModel):
    """요약 탭 하단 차트 영역에 필요한 데이터."""

    questions_by_category: List[CategoryQuestionCount] = Field(
        default_factory=list,
        description="질문 분류별 질문 수 (막대 그래프용)",
    )
    curriculum_scope_ratio: List[ScopeRatioPoint] = Field(
        default_factory=list,
        description="커리큘럼 내/외 질문 비율 (파이 차트용)",
    )


# --------------------------------
# (3) Tables (질문 리스트)
# --------------------------------

class QuestionRow(BaseModel):
    """질문 리스트 테이블에서 사용하는 1행 데이터."""

    question_id: Optional[str] = Field(None, description="Mongo ObjectId 등")
    user_id: Optional[int] = Field(None, description="SQL user_id (있다면)")
    camp_id: Optional[int] = Field(None, description="소속 캠프 ID (있다면)")

    scope: CurriculumScope = Field(..., description="'in' / 'out'")
    category: str = Field(..., description="질문 분류명")
    question_text: str = Field(..., description="사용자 실제 질문 내용")
    pattern_tags: List[str] = Field(default_factory=list, description="질문 패턴 태그")
    intent: Optional[str] = Field(None, description="질문 의도 한 줄 요약")
    answer_summary: Optional[str] = Field(
        None,
        description="AI 답변 요약 (있으면 보고용으로 활용)",
    )
    created_at: Optional[datetime] = Field(
        None,
        description="질문이 발생한 시각 (UTC 또는 로컬, 서비스 기준에 맞게)",
    )


class CategoryQuestionBlock(BaseModel):
    """분류별 하단 질문 리스트용 블록."""

    category: str = Field(..., description="분류명")
    scope: CurriculumScope = Field(..., description="'in' / 'out'")
    questions: List[QuestionRow] = Field(
        default_factory=list,
        description="해당 분류에 속하는 질문 리스트 (최근 N개 등)",
    )


class CurriculumTables(BaseModel):
    """요약 탭 하단에서 사용할 표 데이터들."""

    # 질문 분류별 질문 수 그래프 아래에 보여줄 리스트
    questions_grouped_by_category: List[CategoryQuestionBlock] = Field(
        default_factory=list,
        description="분류별로 묶인 질문 리스트",
    )

    # 커리큘럼 외 질문 비율 그래프 아래에 보여줄 리스트
    curriculum_out_questions: List[QuestionRow] = Field(
        default_factory=list,
        description="커리큘럼 외 질문만 모은 리스트 (최근 N개 등)",
    )


# --------------------------------
# (4) AI 인사이트
# --------------------------------

class HardPartDetail(BaseModel):
    """AI 심층 분석에서 '가장 어려워하는 파트' 상세에 사용."""

    part_label: str = Field(
        ...,
        description="예: 'Week 3 - Git 협업', 'Week 5 - 환경 세팅'",
    )
    main_categories: List[str] = Field(
        default_factory=list,
        description="이 파트에서 특히 많이 나온 질문 분류 목록",
    )
    example_questions: List[str] = Field(
        default_factory=list,
        description="대표 질문 예시 문장 여러 개",
    )
    root_cause_analysis: Optional[str] = Field(
        None,
        description="난이도/혼란의 원인 분석 텍스트",
    )
    improvement_direction: Optional[str] = Field(
        None,
        description="커리큘럼/자료/설명 방식 개선 방향 제안",
    )


class ExtraTopicDetail(BaseModel):
    """AI 심층 분석에서 '커리큘럼 외 질문' 상세에 사용."""

    topic_label: str = Field(
        ...,
        description="예: '포트폴리오/이력서', '면접/커리어', 'IDE 설정'",
    )
    question_count: int = Field(..., description="해당 주제 질문 수")
    example_questions: List[str] = Field(
        default_factory=list,
        description="대표 질문 예시 문장들",
    )
    suggested_session_idea: Optional[str] = Field(
        None,
        description="추가 세션/자료 기획 아이디어",
    )


class CurriculumAIInsights(BaseModel):
    """AI 심층 분석 탭 전체에 사용할 요약 텍스트."""

    # 상단 3개 블록 요약용
    summary_one_line: str = Field(
        ...,
        description="한 줄로 정리한 이번 주 핵심 인사이트",
    )
    hardest_part_summary: str = Field(
        ...,
        description="이번 주 가장 어려워하는 파트에 대한 요약",
    )
    curriculum_out_summary: str = Field(
        ...,
        description="커리큘럼 외 질문에서 드러난 추가 학습 요구 요약",
    )
    improvement_summary: str = Field(
        ...,
        description="전체적인 개선 방향 요약",
    )

    # 하단 상세 리포트용
    hardest_parts_detail: List[HardPartDetail] = Field(
        default_factory=list,
        description="가장 어려워하는 파트별 상세 분석",
    )
    extra_topics_detail: List[ExtraTopicDetail] = Field(
        default_factory=list,
        description="커리큘럼 외 질문 주요 토픽별 상세 분석",
    )

    # 운영진 액션 정리
    curriculum_improvement_actions: str = Field(
        ...,
        description=(
            "어려워하는 파트에 대한 원인 분석 및 개선 방향, "
            "추가 강의 자료/설명 방식 제안 등을 자연어로 정리한 텍스트"
        ),
    )
    extra_session_suggestions: str = Field(
        ...,
        description="커리큘럼 외 세션(포트폴리오, 커리어, IDE 등) 진행 제안 텍스트",
    )


# --------------------------------
# (5) 최상위 Payload
# --------------------------------

class CurriculumReportPayload(BaseModel):
    """
    커리큘럼 리포트 서비스의 최종 출력 구조.
    Streamlit 화면은 이 Payload 하나를 받아서 그대로 렌더링하면 됨.
    """
    summary_cards: CurriculumSummaryCards
    charts: CurriculumCharts
    tables: CurriculumTables
    ai_insights: CurriculumAIInsights