# app/services/feedback_board/report_schemas.py

from pydantic import BaseModel, Field
from typing import List


class FeedbackPriorityItem(BaseModel):
    post_id: str = Field(..., description="Mongo _id 문자열")
    category: str
    title: str           # 한 줄 요약
    reason: str          # 왜 우선순위 높은지
    urgency_level: str   # "즉시 대응", "단기 대응", "중기 대응" 등
    suggested_actions: List[str]   # 운영진 액션 2~3개


class FeedbackBoardAIReport(BaseModel):
    summary_one_line: str
    main_concern_patterns: str      # 고민 글에서 주로 드러난 패턴 요약
    main_suggestion_patterns: str   # 건의 글에서 주로 드러난 패턴 요약

    priority_items: List[FeedbackPriorityItem]

    global_actions: List[str]       # 전체적으로 꼭 해야할 3~5개 액션
    references: List[str]           # 참고하면 좋은 자료/키워드 (간단 링크/키워드)

