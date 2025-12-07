# app/services/feedbackBoard/generate_report/llm.py
import json
from typing import Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from ..schemas import FeedbackBoardAIReport, FeedbackPriorityItem

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
)

report_parser = PydanticOutputParser(pydantic_object=FeedbackBoardAIReport)


def build_feedback_report_prompt(stats: Dict[str, Any]) -> str:
    total_posts = stats.get("total_posts", 0)
    posts_by_category = stats.get("posts_by_category", [])
    priority_candidates = stats.get("priority_candidates", [])
    author_stats = stats.get("author_stats", [])  # ✅ 추가

    stats_json = json.dumps(stats, ensure_ascii=False, indent=2, default=str)
    format_instructions = report_parser.get_format_instructions()

    return f"""
    너는 부트캠프 피드백 게시판을 분석해서 운영진에게
    **실질적인 행동 계획**을 제안하는 AI 리포트 분석가임.

    아래 JSON에는 다음과 같은 정보가 포함되어 있음:

    - total_posts: 전체 글 수
    - posts_by_category: concern/suggestion/other 개수
    - priority_candidates: 각 글의 category, normalized_text, topic_tags,
      importance_score, risk_level, author_id 등
    - author_stats: 작성자별 글 수 / high_risk_count / concern_count / suggestion_count

    JSON 데이터 전체:

    {stats_json}

    -----------------------------
    [작성자 관점 분석 규칙]
    -----------------------------
    1) 한 명(author_id)이 비슷한 고민/불만 글을 여러 개 올린 경우:
       - "특정 학습자가 반복적으로 힘들다는 신호"로 간주한다.
       - 이 경우, priority_items 또는 global_actions 안에
         "해당 작성자를 특정하진 않지만,
          1:1 상담 제안 / 개별 케어"가 필요하다는 내용을 반드시 포함하라.

    2) 서로 다른 여러 작성자가 같은 주제(topic_tags)를 반복해서 언급하는 경우:
       - "구조적 문제(커리큘럼, 운영, 팀 문화 등)"로 간주한다.
       - 이 경우, 개별 케어보다 **제도/프로세스 개선**을 먼저 제안하라.

    3) report 본문에는 author_id를 그대로 쓰지 말고,
       "특정 익명 작성자", "여러 명의 학습자" 정도로만 표현하라.

    -----------------------------
    [리포트 작성 규칙 나머지]  # 이하 기존 내용 유지
    -----------------------------
    ...
    {format_instructions}
    """.strip()
