# app/services/feedback_board/llm.py

from typing import List, Dict, Any
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda

from app.core.mongodb import (
    AnalysisBlock,
    ModerationBlock,
)

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
)

class FeedbackAnalysisResult(BaseModel):
    analysis: AnalysisBlock
    moderation: ModerationBlock


feedback_parser = PydanticOutputParser(pydantic_object=FeedbackAnalysisResult)


def build_feedback_analysis_prompt(raw_text: str) -> str:
    """
    1, 2번 기능: 고민/건의 분류 + 욕설/실명 여부 판단
    """
    format_instructions = feedback_parser.get_format_instructions()

    return f"""
    너는 부트캠프 피드백 게시판(익명)의 글을 분석하는 AI 분석가임.

    아래 글에 대해 다음을 판단하라:

    1) category (concern / suggestion / other)
       - concern : 개인 고민, 정서, 인간관계, 학습 스트레스 등
       - suggestion : 운영, 커리큘럼, 시스템에 대한 건의/제안
       - other : 위 둘에 딱 맞지 않는 잡담/기타

    2) normalized_text
       - 비속어/중복 표현을 줄이고, 의미는 유지한 상태로 정제한 텍스트

    3) topic_tags
       - 글의 주제를 나타내는 2~5개의 태그를 한글 또는 영문 한 단어로 생성
       - 예: ["멘탈", "팀프로젝트", "강의속도", "운영", "환경설정"]

    4) sentiment
       - "positive", "negative", "neutral" 중 하나

    5) importance_score
       - 0.0 ~ 10.0 사이 실수
       - 운영진이 바로 개입해야 할 정도의 긴급도 + 영향도 기준으로 점수화
       - ex) 강사 성희롱, 심각한 우울/자해 암시, 운영 전반 문제 제기 → 8 이상

    6) is_toxic
       - 심한 욕설, 인신공격, 조롱, 혐오 표현이 포함되면 true

    7) has_realname
       - 특정 사람의 실명을 직접 거론하거나
         "홍길동 코치", "김○○ 매니저"처럼 개인 식별 가능한 표현이 있으면 true

    8) risk_level
       - "high" : 자해/타해 암시, 심각한 멘탈 위기, 법적/윤리적 문제 가능성
       - "medium" : 반복된 갈등, 과도한 욕설, 강한 불만, 팀 붕괴 가능성
       - "low" : 일반적인 고민/건의 수준

    9) moderation_note
       - 운영진이 참고해야 할 핵심 요약을 1~2문장으로 작성
       - 예) "멘탈이 상당히 흔들려 있어 1:1 상담 권유 필요해 보임."

    분석 대상 글:

    ---
    {raw_text}
    ---

    아래 Pydantic 스키마 설명에 맞는 JSON만 반환하라.

    {format_instructions}
    """.strip()


def analyze_single_post(raw_text: str) -> FeedbackAnalysisResult:
    prompt = build_feedback_analysis_prompt(raw_text)
    resp = llm.invoke(prompt)
    return feedback_parser.parse(resp.content)


# LangChain Runnable 형태 (원하면 배치 처리에 사용)
analyze_post_chain = (
    RunnableLambda(lambda x: build_feedback_analysis_prompt(x["raw_text"]))
    | llm
    | feedback_parser
)
