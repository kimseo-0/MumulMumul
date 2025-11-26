# app/services/curriculum/llm.py
import json
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from .schemas import CurriculumAIInsights


# LLM 인스턴스 (필요하면 model 이름만 바꿔 쓰면 됨)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
)


# Pydantic 기반 파서
ai_insights_parser = PydanticOutputParser(pydantic_object=CurriculumAIInsights)


def generate_curriculum_ai_insights(stats: Dict[str, Any]) -> CurriculumAIInsights:
    """
    repository.aggregate_curriculum_stats() 에서 만든 stats dict를 받아서
    이번 주 커리큘럼 난이도 / 추가 요구에 대한 AI 인사이트 텍스트를 생성함.
    """

    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)

    prompt = f"""
너는 온라인 부트캠프의 **커리큘럼 난이도 & 추가 학습 요구**를 분석해서
운영진에게 전달하는 **리포트용 분석가 AI**임.

아래는 특정 캠프의 N주차에 대한 집계 데이터(stats)임.
이를 기반으로, 아래 항목들을 모두 채운 하나의 JSON을 반환해야 함.

- summary_top_difficult_parts: 이번 주 가장 어려워한 파트 요약 (짧은 문장 2~3줄)
- summary_curriculum_out: 커리큘럼 외 질문에서 드러난 요구 요약
- summary_improvement: 당장 적용할 수 있는 개선 방향 요약

- section_difficult_parts: 
    1. 이번주 가장 어려워하는 파트
    2. 질문 분류
    3. 대표 질문 내용 예시

- section_curriculum_out:
    1. 커리큘럼 외 질문 주요 카테고리
    2. 각 카테고리별 대표 질문 예시

- section_actions:
    - 어려워하는 파트 원인 분석 및 개선 방향
    - 추가 강의 자료 방향성
    - 커리큘럼 외 세션 진행 제안

반드시 **보고서 말투**로, '~임, ~함' 체를 사용해야 함.
운영진이 그대로 복붙해서 보고서에 넣을 수 있게 작성해야 함.

다음은 집계 데이터(stats)의 내용임:

{stats_json}

위 데이터를 기반으로, 다음 Pydantic 스키마 설명에 맞는 JSON만 반환해야 함.

{ai_insights_parser.get_format_instructions()}
    """

    response = llm.invoke(prompt)
    # response.content 를 바로 파싱
    ai_insights: CurriculumAIInsights = ai_insights_parser.parse(response.content)
    return ai_insights
