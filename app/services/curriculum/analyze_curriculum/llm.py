# app/services/curriculum/analyze_curriculum/llm.py

import json
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from app.core.mongodb import CurriculumConfig

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
)

curriculum_parser = PydanticOutputParser(pydantic_object=CurriculumConfig)


def parse_curriculum_text(camp_id: int, raw_text: str) -> CurriculumConfig:
    """
    운영진이 붙여넣은 커리큘럼 설명 텍스트를
    주차별 CurriculumConfig 형태로 파싱한다.
    """

    format_instructions = curriculum_parser.get_format_instructions()

    prompt = f"""
        너는 부트캠프 운영진이 작성한 커리큘럼 설명 문서를 읽고
        이를 주차별 CurriculumConfig 구조로 정리하는 분석가임.

        입력 텍스트에는 예를 들어 다음과 같은 형식이 섞여 있을 수 있음:
        - "1주차: 파이썬 기초, 자료형, 조건문, 반복문"
        - "2주차 - Numpy / Pandas 데이터 처리"
        - "Week 3: 시각화, Matplotlib, Seaborn"
        - "4주차에는 EDA 프로젝트를 진행함"

        규칙:
        1. 텍스트에서 '1주차', '2주차', 'Week 1', 'Week 2' 등 주차를 나타내는 표현을 찾아서
        주차 단위로 커리큘럼을 나누어라.
        2. 각 주차마다 그 주에서 다루는 **핵심 토픽 키**를 topics 리스트로 정리하라.
        - 토픽 키는 가능한 한 짧고 일관되게 사용하라.
        - 예: "파이썬 기초", "자료형", "조건문", "반복문", "numpy", "pandas", "시각화", "EDA 프로젝트" 등
        3. week_label은 사람이 보기 좋은 형태로 설정하되, 기본값은 "N주차" 형식을 사용하라.
        4. camp_id는 아래 숫자를 그대로 사용하라:
        - camp_id: {camp_id}

        입력 커리큘럼 텍스트는 다음과 같음:

        ---
        {raw_text}
        ---

        아래 Pydantic 스키마 설명에 맞는 JSON만 반환하라.
        반드시 한국어 토픽명을 유지하되, 키는 간결하게 정리하라.

        {format_instructions}
    """

    response = llm.invoke(prompt)
    config: CurriculumConfig = curriculum_parser.parse(response.content)

    # 안전장치: camp_id를 강제로 덮어쓰기
    config.camp_id = camp_id
    return config
