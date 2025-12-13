# app/services/feedbackBoard/io_contract.py
from __future__ import annotations

from typing import Optional, Literal, List, Dict, Any, Tuple
from datetime import datetime
from pydantic import BaseModel, Field

from app.services.feedbackBoard.schemas import FeedbackBoardPost


# ----------------------------
# 1) Pipeline Input / Config
# ----------------------------

class DateRange(BaseModel):
    start: datetime
    end: datetime


class RunConfig(BaseModel):
    camp_id: int
    week: Optional[int] = None
    range: Optional[DateRange] = None

    analyzer_version: str = "fb_v1"

    # 정책 파라미터(결정된 값 반영)
    split_max_parts: int = 5
    dedup_similarity_threshold: float = 0.88
    dedup_scope: Literal["user_week"] = "user_week"

    # 카테고리 템플릿 (운영진 제공)
    # 예: ["팀 갈등", "일정 압박", "과제 난이도", "운영/행정", "피로/번아웃"]
    category_template: List[str] = Field(default_factory=list)


class PipelineInput(BaseModel):
    config: RunConfig


# ----------------------------
# 2) Intermediate Aggregations
# ----------------------------

class ClusterItem(BaseModel):
    local_cluster_id: int
    sub_category: str
    # 대표 문장/요약 (weekly context용)
    representative_summary: str
    representative_keywords: List[str] = Field(default_factory=list)
    count: int


class CategoryAgg(BaseModel):
    category: str
    count: int
    sub_items: List[ClusterItem] = Field(default_factory=list)


class RiskAgg(BaseModel):
    total: int
    toxic_count: int
    severity_count: Dict[Literal["low", "medium", "high"], int]
    danger_count: int         # (is_toxic OR severity=high)
    warning_count: int        # (severity=medium AND not toxic)
    normal_count: int


class RiskHighlight(BaseModel):
    post_id: str
    created_at: datetime
    author_id: Optional[int]
    category: Optional[str]
    sub_category: Optional[str]
    severity: Optional[str]
    is_toxic: Optional[bool]
    summary: Optional[str]
    # 원문 전체 대신: clean_text 일부(또는 마스킹)만
    excerpt: Optional[str] = None


class WeeklyContext(BaseModel):
    camp_id: int
    week: Optional[int] = None
    range: Optional[DateRange] = None

    # 전체 지표
    risk: RiskAgg

    # 카테고리/서브카테고리 집계 + 대표요약
    categories: List[CategoryAgg] = Field(default_factory=list)

    # 위험 글 대표(TopK)
    highlights: List[RiskHighlight] = Field(default_factory=list)

    # action_type 분포 (운영 액션 가이드용)
    action_type_count: Dict[Literal["immediate", "short", "long"], int] = Field(default_factory=dict)


# ----------------------------
# 3) Weekly Report Outputs
# ----------------------------

class KeyTopic(BaseModel):
    category: str
    count: int
    summary: str
    post_ids: List[str] = Field(default_factory=list)
    texts: List[str] = Field(
        default_factory=list,
        description="ai_analysis.clean_text 기반의 대표 excerpt (운영진 확인용)"
    )

class OpsAction(BaseModel):
    title: str
    target: str
    reason: str
    todo: str
    action_type: Literal["immediate", "short", "long"]


class WeeklyReport(BaseModel):
    week_summary: str
    key_topics: List[KeyTopic] = Field(default_factory=list)
    ops_actions: List[OpsAction] = Field(default_factory=list)


class FinalizePayload(BaseModel):
    logs: List[Dict[str, Any]]
    week_summary: str
    key_topics: List[KeyTopic]
    ops_actions: List[OpsAction]
    stats: Dict[str, Any]
    wordcloud_keywords: List[str] = Field(default_factory=list)


# ----------------------------
# 4) Agent State for LangGraph
# ----------------------------

class FeedbackBoardState(BaseModel):
    # input
    input: PipelineInput

    # raw + working
    raw_posts: List[FeedbackBoardPost] = Field(default_factory=list)
    posts: List[FeedbackBoardPost] = Field(default_factory=list)  # split 포함, 계속 여기로 진행

    # derived
    weekly_context: Optional[WeeklyContext] = None
    weekly_report: Optional[WeeklyReport] = None
    final: Optional[FinalizePayload] = None

    # debug / tracing
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
