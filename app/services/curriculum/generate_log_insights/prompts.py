# app/services/curriculum/generate_log_insights/prompts.py
from typing import Any, Dict, List, Optional

from app.core.mongodb import CurriculumConfig, CurriculumInsights
from typing import List
from pydantic import BaseModel, Field

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI

def build_curriculum_block(curriculum_config: Optional[CurriculumConfig]) -> str:
    """
    커리큘럼 정보를 프롬프트에 삽입할 수 있는 문자열 블록으로 변환
    """
    if not curriculum_config:
        return "커리큘럼 정보 없음"

    lines = []
    lines.append(f"- camp_id={curriculum_config.camp_id}")
    for w in curriculum_config.weeks:
        topics_str = ", ".join(w.topics)
        lines.append(f"  - Week {w.week_index} ({w.week_label}): {topics_str}")
    return "\n".join(lines)

# ---------------------------
# 1) Stage 1: 분류 체계(Taxonomy) 생성
# ---------------------------
class TopicItem(BaseModel):
    name: str = Field(..., description="소문자 영문 snake_case 토픽 이름. 예: python_basic")
    description: str = Field(..., description="이 토픽이 다루는 질문의 범위 설명")

class TopicTaxonomy(BaseModel):
    topics: List[TopicItem]

taxonomy_parser = PydanticOutputParser(pydantic_object=TopicTaxonomy)

def build_taxonomy_prompt(
    logs: List[Dict[str, Any]],
    curriculum_config: Optional[CurriculumConfig],
) -> str:
    """
    Stage 1: 전체 질문을 보고 Topic Taxonomy(분류 체계)를 먼저 만드는 프롬프트.
    """
    items_text = ""
    for i, log in enumerate(logs, start=1):
        text = (log.get("content") or "").replace("\n", " ").strip()
        items_text += f"{i}. id={log.get('_id')} user={log.get('user_id')} text={text}\n"

    curriculum_block = build_curriculum_block(curriculum_config)

    prompt = f"""
    너는 온라인 부트캠프 학습 질문을 분석하는 AI 에이전트이다.

    먼저 **이번 주에 수집된 질문들 전체**를 보고,
    이 질문들을 분류할 수 있는 **주요 Topic 체계(Taxonomy)**를 정의하라.

    규칙:
    - 최소 5개, 최대 10개 사이의 topic을 정의한다.
    - topic 이름은 한글/영어 혼합으로 작성한다.
    예: "python 기초", "python 고급", "pandas", "eda 분석", "자연어 처리", "커리어", "portfolio", "ide 환경 설정"
    - 같은 부류의 질문들은 한 topic 아래로 묶을 수 있도록, 서로 겹치지 않게 설계한다.
    - 토픽 설계 기준은 "질문 자체의 내용"이 우선이며,
    아래 커리큘럼 정보는 **참고용**이다. 커리큘럼에 과하게 끌려가지 말 것.

    참고용 커리큘럼 정보:
    {curriculum_block}

    출력 형식(JSON only):
    {taxonomy_parser.get_format_instructions()}

    [질문 목록]
    {items_text}
    """
    return prompt.strip()


# ---------------------------
# 2) Stage 2: 개별 질문 분류/태깅 프롬프트 생성
# ---------------------------
class CurriculumInsightsBatch(BaseModel):
    items: List[CurriculumInsights]

ai_insights_parser = PydanticOutputParser(pydantic_object=CurriculumInsightsBatch)

def build_classification_prompt(
    logs: List[Dict[str, Any]],
    taxonomy: TopicTaxonomy,
) -> str:
    items_text = ""
    for i, log in enumerate(logs, start=1):
        text = (log.get("content") or "").replace("\n", " ").strip()
        items_text += f"{i}. id={log.get('_id')} user={log.get('user_id')} text={text}\n"

    print("분류체계 :")
    print(taxonomy)
    taxonomy_lines = []
    for t in taxonomy.topics:
        taxonomy_lines.append(f"- {t.name}: {t.description}")
    taxonomy_block = "\n".join(taxonomy_lines)

    prompt = f"""
    너는 온라인 부트캠프 학습 질문을 분석하는 AI 에이전트이다.

    이전에 정의한 Topic 체계는 다음과 같다.

    [Topic Taxonomy]
    {taxonomy_block}

    이제 아래 각 질문에 대해 다음 항목을 추론하라.

    - topic
        - 반드시 위 Topic Taxonomy에 정의된 name 중 하나여야 한다.
    - curriculum_scope
        - "in": 파이썬, 데이터 분석, 통계, 시각화, 웹스크래핑, NLP, ML 등 기술 학습 내용
        - "out": 커리어, 취업, 이력서/포트폴리오, 멘탈/상담, 부트캠프 운영/행정 관련
    - pattern_tags: 아래 중에서 상황에 맞게 복수 선택
        - "개념 이해 부족"      # 개념 헷갈림, 정의/원리 이해 부족
        - "응용 방법 질문"  # 특정 기능/문법/라이브러리 사용법 질문
        - "코드 작성 도움"      # 특정 기능/문법 사용법, 코드 작성법 질문
        - "버그/에러" # 내가 예상한 결과와 실제 결과가 다를 때
        - "환경 설정"      # IDE, 패키지 설치, 버전 문제, 경로 문제 등 환경 이슈
        - "기타"                  # 위에 딱 맞지 않으면
    - intent:
        - 질문을 한 학습자의 "진짜 의도"를 1문장 한국어로 요약
        - 질문 문장을 그대로 복사하지 말고,
        "이 학습자는 ~~을 알고 싶어 한다" 형태로 재작성할 것.

    출력 형식(JSON only):
    {ai_insights_parser.get_format_instructions()}

    [질문 목록]
    {items_text}
    """
    return prompt.strip()
