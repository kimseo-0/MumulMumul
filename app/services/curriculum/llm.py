import json
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from .schemas import CurriculumAIInsights


# LLM 인스턴스
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,  # 거의 결정적이되, 약간의 다양성만 허용
)

# Pydantic 기반 파서
ai_insights_parser = PydanticOutputParser(pydantic_object=CurriculumAIInsights)


def generate_curriculum_ai_insights(stats: Dict[str, Any]) -> CurriculumAIInsights:
    """
    aggregate_curriculum_stats() 에서 만든 stats dict를 받아서
    이번 주 커리큘럼 난이도 / 추가 학습 요구에 대한 AI 인사이트 텍스트를 생성함.

    stats 주요 필드 예시:
    - total_questions, in_count, out_count
    - in_category_stats: [{category, count, ratio, example_questions}, ...]
    - out_category_stats: [{category, count, ratio, example_questions}, ...]
    """

    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)

    prompt = f"""
너는 온라인 부트캠프의 **커리큘럼 난이도 & 추가 학습 요구**를 분석해서
운영진에게 전달하는 **리포트용 분석가 AI**임.

아래는 특정 캠프의 N주차에 대한 집계 데이터(stats)임.
이 데이터를 바탕으로, Pydantic 스키마(CurriculumAIInsights)에 맞는 JSON 하나만 생성해야 함.

분석과 작성 기준은 다음과 같음:

[데이터 해석 기준]
- "커리큘럼 내(in) 질문"은 stats["in_category_stats"]를 사용함.
  - 각 항목은 { "category", "count", "ratio", "example_questions" } 정보를 가짐.
  - ratio는 해당 scope 내에서 이 카테고리가 차지하는 비율임 (0~1 사이).
- "커리큘럼 외(out) 질문"은 stats["out_category_stats"]를 사용함.

- "어려운 파트" 선정 기준 (커리큘럼 내):
  - in_category_stats 중에서
    1) ratio가 0.2 이상이거나
    2) count 기준 상위 3개
  - 위 조건을 만족하는 카테고리들만 hardest_parts_detail에 포함할 것.

- "커리큘럼 외 주요 토픽" 선정 기준:
  - out_category_stats 중에서
    1) count가 2 이상이거나
    2) ratio가 0.15 이상
  - 위 조건을 만족하는 카테고리들만 extra_topics_detail에 포함할 것.

[말투/스타일 규칙]
- 전체적으로 **보고서 말투**를 사용할 것.
- 문장은 '~임', '~함', '~할 필요가 있음' 과 같이 서술형으로 끝낼 것.
- 불필요하게 과장된 수식어나 형용사를 사용하지 말 것.
- 동일한 내용을 여러 번 반복하지 말 것.
- part_label, topic_label 에 "Week X -" 와 같은 가짜 주차 표기를 넣지 말 것.
  - 카테고리명을 그대로 사용하거나, 카테고리를 짧게 보완한 형태만 사용할 것.

[요약 영역 작성 규칙]
아래 4개 필드는 **한눈에 핵심만 보이도록** 작성해야 함.

- summary_one_line:
  - 이번 주 핵심 인사이트를 1문장으로 요약할 것.
  - 예: "pandas와 시각화 파트에 질문이 집중되고, 커리어 준비·IDE 설정에 대한 요구가 뚜렷하게 나타났음."

- hardest_part_summary:
  - 최대 3~4줄의 bullet 형태로 작성할 것.
  - 각 줄은 "• " 로 시작하고 1문장으로 끝낼 것.
  - 내용은 in_category_stats 중 어려운 파트(선정 기준에 따라 결정)를 요약할 것.
  - 예: "• pandas groupby가 in 질문의 약 30%를 차지해 가장 어려운 파트로 나타났음."

- curriculum_out_summary:
  - 최대 3~4줄의 bullet 형태로 작성할 것.
  - 각 줄은 "• " 로 시작하고 1문장으로 끝낼 것.
  - 내용은 out_category_stats 중 주요 토픽(커리어, IDE, 포트폴리오 등)을 요약할 것.

- improvement_summary:
  - 최대 3~5줄의 bullet 형태로 작성할 것.
  - 각 줄은 "• " 로 시작하고 1문장으로 끝낼 것.
  - "이번 기수에서 즉시 보완할 부분"과 "다음 기수 커리큘럼 설계 시 반영할 부분"을 섞어서 제안할 것.

[상세 영역 작성 규칙]

- hardest_parts_detail (List[HardPartDetail]):
  - in_category_stats에서 "어려운 파트" 선정 기준에 해당하는 카테고리들만 포함할 것.
  - 각 HardPartDetail은 다음과 같이 작성:
    - part_label: 카테고리명을 그대로 사용하거나, 카테고리를 짧게 보완한 한국어 표현으로 작성할 것.
      (예: "pandas groupby", "시각화(matplotlib)" 등)
    - main_categories: 해당 파트와 관련된 핵심 키워드를 1~3개 넣을 것.
      (예: ["데이터 처리", "groupby"], ["그래프 스타일"] 등)
    - example_questions: stats["in_category_stats"]의 example_questions 중 1~3개를 그대로 사용(필요시 짧게 다듬어도 됨).
    - root_cause_analysis:
      - 왜 이 파트가 어려운지에 대한 원인을 2~3문장으로 정리할 것.
      - 예: 선행지식 부족, 개념 난이도, 실습 난이도, 자료 구성 문제 등.
    - improvement_direction:
      - 어떤 보완 강의/실습/자료가 도움이 될지 2~3문장으로 구체적으로 제안할 것.

- extra_topics_detail (List[ExtraTopicDetail]):
  - out_category_stats에서 "커리큘럼 외 주요 토픽" 선정 기준에 해당하는 카테고리들만 포함할 것.
  - 각 ExtraTopicDetail은 다음과 같이 작성:
    - topic_label: 카테고리명을 그대로 사용하거나, "커리어", "IDE 설정", "포트폴리오"처럼 의미가 잘 드러나는 표현으로 작성할 것.
    - question_count: 해당 카테고리의 질문 수(count)를 그대로 넣을 것.
    - example_questions: example_questions 중 1~3개를 사용.
    - suggested_session_idea:
      - 어떤 형태의 별도 세션/자료/워크숍을 열면 좋을지 2~3문장으로 작성할 것.

[운영진 액션 정리 영역]

- curriculum_improvement_actions:
  - hardest_parts_detail에 나온 파트들을 기준으로
    - 어떤 예제/실습을 추가할지
    - 어떤 설명 방식을 보완할지
    - 어떤 사전 가이드를 제공할지
  를 3~6문장으로 구체적으로 제안할 것.
  - "이번 기수에서 바로 적용 가능한 조치"라는 관점으로 작성할 것.

- extra_session_suggestions:
  - extra_topics_detail에 나온 토픽들을 묶어서
    - 커리어/포트폴리오 세션
    - IDE/환경 설정 실습 세션
    - 질의응답(AMA) 세션
  등을 어떻게 구성하면 좋을지 3~6문장으로 제안할 것.

다음은 집계 데이터(stats)의 내용임:

{stats_json}

위 데이터를 기반으로,
아래 Pydantic 스키마 설명에 정확히 맞는 JSON만 반환해야 함.

{ai_insights_parser.get_format_instructions()}
    """

    response = llm.invoke(prompt)
    ai_insights: CurriculumAIInsights = ai_insights_parser.parse(response.content)
    return ai_insights
