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

# app/services/curriculum/llm.py

import json
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from ..schemas import CurriculumAIInsights


llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
)

ai_insights_parser = PydanticOutputParser(pydantic_object=CurriculumAIInsights)


def build_llm_context_block(stats: Dict[str, Any]) -> str:
    """
    raw_stats(dict)를 사람이 읽기 좋은 텍스트 블록으로 변환.
    LLM 프롬프트에 그대로 붙여서 사용한다.
    """

    total_questions = stats.get("total_questions", 0)
    in_count = stats.get("in_count", 0)
    out_count = stats.get("out_count", 0)

    in_category_stats = stats.get("in_category_stats") or []
    out_category_stats = stats.get("out_category_stats") or []
    pattern_stats_overall = stats.get("pattern_stats_overall") or []
    curriculum_config = stats.get("curriculum_config") or {}

    lines: list[str] = []

    # ---------------------------
    # 0. OVERVIEW
    # ---------------------------
    lines.append("### OVERVIEW")
    lines.append(f"- total_questions: {total_questions}")
    lines.append(f"- in_count: {in_count}")
    lines.append(f"- out_count: {out_count}")
    lines.append("")

    # ---------------------------
    # 1. QUESTION VOLUME (IN)
    # ---------------------------
    if in_category_stats:
        lines.append("### QUESTION VOLUME — CURRICULUM IN")
        for item in in_category_stats:
            cat = item.get("category", "기타")
            cnt = item.get("count", 0)
            ratio = item.get("ratio", 0.0)
            uq = item.get("unique_users", 0)
            diff_score = item.get("difficulty_score", 0.0)
            diff_level = item.get("difficulty_level", "low")
            lines.append(
                f"- {cat}: {cnt} questions "
                f"(ratio: {ratio:.2f}, unique_users: {uq}, "
                f"difficulty_score: {diff_score:.2f}, level: {diff_level})"
            )
        lines.append("")

    # ---------------------------
    # 2. QUESTION VOLUME (OUT)
    # ---------------------------
    if out_category_stats:
        lines.append("### QUESTION VOLUME — CURRICULUM OUT")
        for item in out_category_stats:
            cat = item.get("category", "기타")
            cnt = item.get("count", 0)
            ratio = item.get("ratio", 0.0)
            uq = item.get("unique_users", 0)
            diff_score = item.get("difficulty_score", 0.0)
            diff_level = item.get("difficulty_level", "low")
            lines.append(
                f"- {cat}: {cnt} questions "
                f"(ratio: {ratio:.2f}, unique_users: {uq}, "
                f"difficulty_score: {diff_score:.2f}, level: {diff_level})"
            )
        lines.append("")

    # ---------------------------
    # 3. PATTERN ANALYSIS (OVERALL)
    # ---------------------------
    if pattern_stats_overall:
        lines.append("### PATTERN ANALYSIS — OVERALL")
        for p in pattern_stats_overall:
            tag = p.get("tag", "unknown")
            cnt = p.get("count", 0)
            ratio = p.get("ratio", 0.0)
            lines.append(f"- {tag}: {cnt} occurrences (ratio: {ratio:.2f})")
        lines.append("")

    # ---------------------------
    # 4. PATTERN ANALYSIS BY CATEGORY (IN)
    # ---------------------------
    if in_category_stats:
        lines.append("### PATTERN ANALYSIS — BY CATEGORY (IN)")
        for item in in_category_stats:
            cat = item.get("category", "기타")
            pattern_counts = item.get("pattern_counts") or {}
            if not pattern_counts:
                continue
            pattern_str = ", ".join(
                f"{tag}: {cnt}" for tag, cnt in pattern_counts.items()
            )
            lines.append(f"- {cat}: {pattern_str}")
        lines.append("")

    # ---------------------------
    # 5. CURRICULUM STRUCTURE (OPTIONAL)
    # ---------------------------
    weeks = curriculum_config.get("weeks") or []
    if weeks:
        lines.append("### CURRICULUM STRUCTURE")
        for week in weeks:
            w_idx = week.get("week_index")
            w_label = week.get("week_label") or f"{w_idx}주차"
            topics = week.get("topics") or []
            topics_str = ", ".join(topics) if topics else "no topics"
            lines.append(f"- {w_label} (week_index={w_idx}): {topics_str}")
        lines.append("")

    # ---------------------------
    # 6. EXAMPLE QUESTIONS (선택)
    # ---------------------------
    # 필요하면 in_category_stats 의 example_questions를 간단히 붙여줄 수도 있음
    # 너무 길어지는 게 싫으면 생략 가능

    return "\n".join(lines).strip()

def generate_curriculum_ai_insights(stats: Dict[str, Any]) -> CurriculumAIInsights:
    """
    aggregate_curriculum_stats() 에서 만든 raw_stats dict를 받아서
    이번 주 커리큘럼 난이도 / 추가 요구에 대한 AI 인사이트 텍스트를 생성함.
    """

    context_block = build_llm_context_block(stats)
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2, default=str)

    prompt = f"""
      너는 온라인 부트캠프의 **커리큘럼 난이도 & 추가 학습 요구**를 분석해서
      운영진에게 전달하는 **리포트용 분석가 AI**임.

      아래 두 가지 정보를 기반으로 분석해야 함.

      1) 사람이 읽기 좋게 정리된 요약 컨텍스트(context_block)
      2) 기계가 읽기 좋은 원시 집계 데이터(stats_json)

      --------------------------------
      [0] CONTEXT BLOCK (요약 정보)
      --------------------------------
      아래 블록은 이번 주 질문 데이터에 대한 요약임.
      이 내용을 최우선으로 참고해서 어떤 파트가 어려웠는지, 어떤 패턴이 많은지 판단하라.

      {context_block}

      --------------------------------
      [1] STATS JSON (상세 수치)
      --------------------------------
      아래 JSON은 동일한 데이터를 보다 정밀하게 표현한 것임.
      필요할 때만 참고해서 수치 근거를 확인하라.

      {stats_json}

      --------------------------------
      [2] 데이터 구조 핵심 요약
      --------------------------------
      stats에는 다음과 같은 정보가 포함됨:

      - total_questions, in_count, out_count
      - in_category_stats / out_category_stats:
        - category, count, unique_users, ratio, difficulty_score, difficulty_level
        - pattern_counts (태그별 빈도)
        - example_questions
      - pattern_stats_overall:
        - tag별 전반적인 분포
      - (선택) curriculum_config:
        - weeks: [(week_index, week_label, topics), ...]

      이 정보를 바탕으로, 아래 규칙에 따라 리포트를 작성해야 함.

      --------------------------------
      [3] 분석 규칙 (꼭 지킬 것)
      --------------------------------

      1) "어려운 파트" 판단 시:
      - difficulty_score와 difficulty_level을 최우선 기준으로 사용.
      - unique_users가 많은 카테고리를 우선적으로 다룰 것.
      - unique_users가 1명인데 count만 높은 경우는 outlier 가능성이 있으므로 중요도를 낮게 평가할 것.

      2) 패턴 기반 원인 분석:
      - pattern_counts와 pattern_stats_overall를 활용하여
        - 개념 혼란, API 사용, 예상 결과 불일치, 환경 이슈 등 어떤 유형의 어려움이 많은지 설명할 것.

      3) 커리큘럼 외(out) 질문:
      - out_category_stats를 기반으로
        - 커리어, 포트폴리오, IDE 설정 등 커리큘럼 외 추가 세션이 필요한 토픽을 정리할 것.
        - out_category_stats이 없을 경우 반드시 빈 값을 반환할 것.

      4) 표현 방식:
      - 전체적으로 보고서 말투, "~임, ~함" 체를 사용할 것.
      - summary 계열은 2~3문장 이내로 간결하게 작성할 것.
      - 문장은 짧고 명확하게, 한 문장에 하나의 메시지만 담을 것.
      - 필요시 difficulty_score, unique_users 등 수치 근거를 1~2회 정도 언급할 것.

      --------------------------------
      [4] 출력해야 하는 구조
      --------------------------------

      아래 Pydantic 스키마(CurriculumAIInsights)에 맞게 JSON만 반환해야 함.

      각 필드 의도:
      - summary_one_line: 이번 주 전체 인사이트 한 줄 요약
      - hardest_part_summary: 난이도 높은 핵심 파트 요약
      - curriculum_out_summary: 커리큘럼 외 주요 요구 요약
      - improvement_summary: 이번 기수에 바로 적용 가능한 개선 방향 요약
      - hardest_parts_detail: 난이도 높은 파트별 상세 분석
      - extra_topics_detail: 커리큘럼 외 주요 토픽별 상세 분석
      - curriculum_improvement_actions: 커리큘럼/난이도 개선 액션 정리
      - extra_session_suggestions: 커리큘럼 외 세션/자료 제안 정리

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
