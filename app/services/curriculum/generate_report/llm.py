# app/services/curriculum/llm.py
import json
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from ..schemas import CurriculumAIInsights


# LLM 인스턴스 (필요하면 model 이름만 바꿔 쓰면 됨)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
)


# Pydantic 기반 파서
ai_insights_parser = PydanticOutputParser(pydantic_object=CurriculumAIInsights)


def generate_curriculum_ai_insights(stats: Dict[str, Any]) -> CurriculumAIInsights:
    """
    aggregate_curriculum_stats() 에서 만든 raw_stats dict를 받아서
    이번 주 커리큘럼 난이도 / 추가 요구에 대한 AI 인사이트 텍스트를 생성함.

    stats 구조 핵심:
    - total_questions, in_count, out_count
    - in_category_stats: [
        {
          "category": str,
          "count": int,
          "unique_users": int,
          "ratio": float,
          "difficulty_score": float,
          "difficulty_level": "high" | "medium" | "low",
          "pattern_counts": {tag: count, ...},
          "example_questions": [str, ...]
        }, ...
      ]
    - out_category_stats: (구조 동일, scope = "out")
    - pattern_stats_overall: [
        { "tag": str, "count": int, "ratio": float }, ...
      ]
    """

    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)

    prompt = f"""
    너는 온라인 부트캠프의 **커리큘럼 난이도 & 추가 학습 요구**를 분석해서
    운영진에게 전달하는 **리포트용 분석가 AI**임.

    아래 stats는 이미 전처리된 집계 데이터임.
    이 데이터를 기반으로, **정해진 규칙에 따라** 리포트를 작성해야 함.

    --------------------------------
    [1] 데이터 구조 설명
    --------------------------------
    stats는 대략 아래 의미를 가짐:

    - total_questions: 이번 주 전체 질문 수
    - in_category_stats: 커리큘럼 내(in) 카테고리별 통계 리스트
      - category: 토픽명 (예: pandas, visualization, nlp_network 등)
      - count: 해당 카테고리 질문 수
      - unique_users: 질문한 서로 다른 사용자 수
      - ratio: 같은 scope 안에서의 비율 (0~1)
      - difficulty_score: 난이도 신호 점수
          log(1+count) + 1.5 * unique_users 로 계산됨
      - difficulty_level: "high" / "medium" / "low"
      - pattern_counts: pattern_tags 분포
          - concept_confusion: 개념/정의 혼란
          - api_usage: 라이브러리/함수 사용법 어려움
          - expected_output_mismatch: 예상 결과와 실제 결과 불일치
          - environment_issue: 설치/버전/IDE 등 환경 문제
          - other: 기타
      - example_questions: 대표 질문 예시 문장들

    - out_category_stats: 커리큘럼 외(out) 질문에 대한 구조 (커리어, 포트폴리오, IDE 등)
    - pattern_stats_overall:
      - tag별 전체 비율 (이번 주 전체에서 어떤 패턴이 많이 나왔는지)

    --------------------------------
    [2] 분석 규칙 (꼭 지킬 것)
    --------------------------------

    1) "어려운 파트" 판단 기준
    - difficulty_score와 difficulty_level을 **최우선 기준**으로 사용하라.
    - difficulty_level이 "high"인 카테고리를 우선적으로 다루라.
    - unique_users가 많을수록 "여러 명이 동시에 어려워한 파트"로 간주하라.
    - unique_users가 1명이고 count가 높은 경우:
      - outlier로 간주하고, 중요도를 한 단계 낮게 보라.
      - 이런 경우에는 "특정 학습자의 반복 질문으로 인한 난이도 상승 가능성"이라고 언급할 수 있음.

    2) 패턴 기반 원인 분석
    - pattern_counts를 활용해서 "왜 어려웠는지"를 설명하라.
      예시:
      - concept_confusion 비율이 높으면: 개념/정의가 충분히 설명되지 않았거나 예제가 부족함.
      - api_usage 비율이 높으면: 함수/메서드 인자, 옵션, 사용 패턴에 대한 실습이 부족함.
      - expected_output_mismatch 비율이 높으면: 예시와 실제 데이터가 다르거나, 출력 구조를 충분히 안내하지 못한 것일 수 있음.
      - environment_issue 비율이 높으면: 설치/경로/버전/IDE 설정 가이드를 강화해야 함.

    3) 커리큘럼 외 질문 분석
    - out_category_stats에서 count, difficulty_score, pattern_counts를 보고
      - 커리어, 포트폴리오, IDE와 같이 "추가 세션이 필요한 영역"을 선정하라.
    - pattern_tags가 environment_issue가 많은 경우:
      - IDE 설정/디버깅/환경 구성 세션 제안을 포함하라.
    - 커리어/포트폴리오 관련 카테고리는:
      - 이력서/포트폴리오/채용 전략 세션 제안을 포함하라.

    4) 표현 방식 규칙
    - 전체적으로 **보고서 말투**로, "~임, ~함" 체를 사용하라.
    - 요약 필드(summary_*)는 **최대 2~3문장**으로 간결하게 작성하라.
    - 문장은 가능하면 짧게, 한 문장에 하나의 메시지만 담아라.
    - 가능하면 difficulty_score, unique_users, pattern 비율 등 **데이터 근거를 한두 번 언급**하라.
      예: "pandas 파트는 11명의 학습자가 질문하여 난이도가 높은 파트로 판단됨."

    --------------------------------
    [3] 출력해야 하는 구조
    --------------------------------

    아래 Pydantic 스키마(CurriculumAIInsights)에 맞게 JSON만 반환해야 함.

    각 필드는 다음 의도를 가지고 작성하라:

    - summary_one_line:
      - 이번 주 인사이트 전체를 한 줄로 요약.
      - 예: "이번 주는 pandas와 시각화 파트에서 개념 혼란이 집중적으로 발생하였으며, 커리어/IDE 관련 추가 요구가 뚜렷하게 나타났음."

    - hardest_part_summary:
      - in_category_stats 중 difficulty_level "high"인 상위 1~3개를 중심으로
      - 어떤 파트가 왜 어려웠는지를 짧게 요약.

    - curriculum_out_summary:
      - out_category_stats를 기반으로
      - 커리어/포트폴리오/IDE 등 주요 토픽과 질문 경향을 요약.

    - improvement_summary:
      - 난이도 높은 파트와 커리큘럼 외 요구를 종합하여
      - "이번 기수에서 바로 적용할 수 있는 개선 방향"을 요약.

    - hardest_parts_detail:
      - difficulty_level "high" 또는 score 상위 카테고리들에 대해
        - part_label: "Week X - pandas" 같은 형식 대신, stats에 있는 category명을 토대로 자연스럽게 작성. (예: "pandas 데이터 집계", "시각화 기초")
        - main_categories: 해당 카테고리명 또는 세부 주제명 리스트
        - example_questions: stats에 포함된 example_questions 중 대표적인 것들
        - root_cause_analysis: pattern_counts를 활용하여 "개념 이해 부족", "API 사용 패턴 미숙" 등 구체적으로 작성
        - improvement_direction: 실습 강화, 예제 추가, 가이드 문서 보완 등 구체적인 개선 방향 제안

    - extra_topics_detail:
      - out_category_stats 중 count가 일정 이상이거나 difficulty_score가 높은 항목에 대해
        - topic_label: "커리어", "포트폴리오", "IDE 설정" 등
        - question_count: 해당 카테고리 질문 수
        - example_questions: example_questions 중 대표 질문들
        - suggested_session_idea: 어떤 추가 세션/자료를 제안하는지 구체적인 한두 문장으로 작성

    - curriculum_improvement_actions:
      - hardest_parts_detail와 pattern_stats_overall를 종합해서
      - "어떤 파트를 어떤 방식으로 보완해야 하는지"를 액션 아이템 형태로 정리.
      - 예: "pandas groupby 개념 정리 미니 세션 1회 추가", "matplotlib 스타일 변경 실습 예제 3개 제공" 등.

    - extra_session_suggestions:
      - out_category_stats를 기반으로
      - 커리어/포트폴리오/IDE 등 추가 세션 아이디어를 묶어서 정리.

    --------------------------------
    [4] 집계 데이터(stats)
    --------------------------------

    아래는 이번 주차에 대한 집계 데이터(stats) JSON임.
    이 데이터를 참고하여 위 규칙을 지키는 분석 결과 JSON을 생성하라.

    {stats_json}

    --------------------------------
    [5] 최종 출력 형식
    --------------------------------

    아래 PydanticOutputParser 설명에 맞는 **JSON만** 반환하라.
    여분의 설명, 마크다운, 자연어 설명을 붙이지 말고, 오직 JSON만 출력할 것.

    {ai_insights_parser.get_format_instructions()}
    """

    response = llm.invoke(prompt)
    ai_insights: CurriculumAIInsights = ai_insights_parser.parse(response.content)
    return ai_insights
