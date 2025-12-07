# app/services/curriculum/generate_report/llm.py
import json
from typing import Dict, Any, List, Literal

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from ..schemas import CurriculumAIInsights
from pydantic import BaseModel, Field

class PriorityIssue(BaseModel):
    rank: int = Field(..., description="1이 가장 시급한 이슈")
    category: str = Field(..., description="예: '파이썬 기초', 'numpy', '포트폴리오'")
    scope: Literal["in", "out"] = Field(..., description="'in' or 'out'")
    issue_type: Literal["difficulty", "extra_need"] = Field(
        ..., description="난이도 이슈인지, 커리큘럼 외 추가 요구인지"
    )
    summary: str = Field(..., description="이 이슈에 대한 한 줄 요약")
    main_patterns: List[str] = Field(
        default_factory=list,
        description="주요 패턴 태그 또는 반복 양상 (예: ['개념 이해 부족', '코드 작성 도움'])",
    )
    root_cause_hint: str = Field(
        ...,
        description="추측 가능한 원인 요약 (설명 방식, 과제 난이도, 순서 문제 등)"
    )
    action_hint: str = Field(
        ...,
        description="운영진이 바로 실행할 수 있는 구체 액션 한 줄"
    )

class PriorityAnalysis(BaseModel):
    priority: List[PriorityIssue]



# LLM 인스턴스 (필요하면 model 이름만 바꿔 쓰면 됨)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
)


# Pydantic 기반 파서
ai_insights_parser = PydanticOutputParser(pydantic_object=CurriculumAIInsights)


import json
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from ..schemas import CurriculumAIInsights


llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
)

priority_parser = PydanticOutputParser(pydantic_object=PriorityAnalysis)
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
    category_pattern_summary = stats.get("category_pattern_summary") or []
    priority_rows = stats.get("priority") or []
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
    # 4. PATTERN ANALYSIS BY CATEGORY
    # ---------------------------
    if category_pattern_summary:
        lines.append("### PATTERN ANALYSIS — BY CATEGORY (TOP PATTERNS)")
        for item in category_pattern_summary:
            cat = item.get("category", "기타")
            patterns = item.get("patterns") or []
            pattern_str = ", ".join(
                f"{p.get('tag')}({p.get('count')})" for p in patterns
            )
            lines.append(f"- {cat}: {pattern_str}")
        lines.append("")

    # ---------------------------
    # 5. PRIORITY (DIFFICULTY-BASED)
    # ---------------------------
    if priority_rows:
        lines.append("### PRIORITY CATEGORIES (BY DIFFICULTY_SCORE)")
        for row in priority_rows:
            rank = row.get("rank")
            cat = row.get("category", "기타")
            level = row.get("difficulty_level", "Medium")
            lines.append(f"- #{rank}: {cat} (level={level})")
        lines.append("")

    # ---------------------------
    # 6. CURRICULUM STRUCTURE (OPTIONAL)
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

    return "\n".join(lines).strip()

def analyze_priority_issues(stats: Dict[str, Any]) -> PriorityAnalysis:
    """
    raw_stats를 기반으로 우선순위 이슈 + 액션 힌트를 구조화해서 뽑는 단계.
    이후 최종 리포트는 이 결과를 기반으로 다시 생성함.
    """
    context_block = build_llm_context_block(stats)
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2, default=str)

    prompt = f"""
    너는 온라인 데이터 부트캠프의 질문 로그를 분석해서
    운영진에게 줄 **우선순위 이슈 리스트**를 만드는 분석가임.

    아래 두 정보를 기반으로 분석하라.

    [0] CONTEXT BLOCK (요약 정보)
    {context_block}

    [1] STATS JSON (상세 수치)
    {stats_json}

    분석 규칙:
    - in_category_stats / out_category_stats의 difficulty_score, difficulty_level, ratio, unique_users를 사용해서
      "어디에서 학습 난이도 문제가 큰지", "어떤 커리큘럼 외 요구가 반복되는지"를 찾는다.
    - difficulty_score가 높고 ratio/unique_users가 높은 카테고리를 상위 이슈로 둔다.
    - scope == "in"이면 issue_type은 주로 "difficulty"로, scope == "out"이면 "extra_need" 비율이 높을수록 우선순위를 올린다.
    - pattern_stats / category_pattern_summary를 참고해서 main_patterns에 들어갈 패턴을 선정한다.
      (예: '개념 이해 부족', '코드 작성 도움', '버그/에러', '환경 설정' 등)

    action_hint 작성 규칙:
    - "추가 강의 필요" 같은 추상적인 표현 금지.
    - 아래 형식처럼 **구체적인 실행 단위**로 작성할 것:
      - "[이번 주] 실습 문제 2개를 '자료형 변환' 중심으로 교체 및 해설 영상 추가"
      - "[다음 기수] Week 1과 2를 나누어, 반복문은 별도 주차로 분리"
      - "[커리어 세션] 포트폴리오 초안 리뷰 워크숍 1회(90분) 추가"

    root_cause_hint 작성 규칙:
    - "설명 부족" 같은 포괄 표현 대신,
      - "예제 코드가 현실 과제와 달라 연결이 안 됨"
      - "자료형·조건문·반복문이 한 주에 몰려 있어 인지 부하가 큼"
      - "실습 난이도가 강의 난이도보다 1단계 높음"
      처럼 구체적으로 적을 것.

    출력 형식(JSON only):
    {priority_parser.get_format_instructions()}
    """

    resp = llm.invoke(prompt)
    analysis: PriorityAnalysis = priority_parser.parse(resp.content)
    return analysis

def generate_curriculum_ai_insights(stats: Dict[str, Any]) -> CurriculumAIInsights:
    """
    1단계: raw_stats → 우선순위 이슈/액션 PriorityAnalysis 생성
    2단계: PriorityAnalysis + stats → CurriculumAIInsights 리포트 생성
    """

    # 1단계: 이슈/액션 구조화
    priority_analysis = analyze_priority_issues(stats)

    # raw_stats 안에 다시 넣어주면 Streamlit 요약 탭에서 바로 활용 가능
    stats["priority"] = [
        {
            "rank": p.rank,
            "category": p.category,
            "difficulty_level": "high",  # 필요하면 p.issue_type이나 난이도 정보로 조정
            "main_patterns": p.main_patterns,
            "action_hint": p.action_hint,
        }
        for p in priority_analysis.priority
    ]

    context_block = build_llm_context_block(stats)
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2, default=str)
    priority_json = priority_analysis.model_dump_json(ensure_ascii=False, indent=2)
    print("=== PRIORITY JSON ===")
    print(priority_json)

    prompt = f"""
      너는 온라인 부트캠프의 **커리큘럼 난이도 & 추가 학습 요구**를 분석해서
      운영진에게 전달하는 **전략 리포트용 AI**임.

      이제 다음 세 가지 정보를 모두 참고해서,
      아래 CurriculumAIInsights 스키마에 맞는 리포트를 작성하라.

      [0] CONTEXT BLOCK (요약 정보)
      {context_block}

      [1] STATS JSON (상세 집계)
      {stats_json}

      [2] PRIORITY ANALYSIS (우선순위 이슈 + 액션 힌트)
      {priority_json}

      작성 원칙:
      1) summary_one_line, hardest_part_summary, curriculum_out_summary, improvement_summary
         - 모두 **운영진이 바로 보고 결론을 이해할 수 있도록**, 2~3문장 안으로 정리.
         - 반드시 priority_analysis에서 뽑힌 상위 1~3개 이슈를 직접 언급할 것.

      2) hardest_parts_detail / extra_topics_detail
         - PriorityIssue 중 issue_type == "difficulty"인 것 → hardest_parts_detail에 매핑.
         - issue_type == "extra_need"인 것 → extra_topics_detail에 매핑.
         - example_questions는 stats의 example_questions_per_category에서 2~3개씩 가져와 요약.
         - root_cause_analysis에는 priority.issue.root_cause_hint를 자연스럽게 녹여서 작성.

      3) curriculum_improvement_actions / extra_session_suggestions
         - priority.action_hint들을 정리해서, 실제 실행 계획처럼 쓸 것.
         - 각 액션에는 최소한 다음 정보를 포함:
           - 언제: 이번 주/다음 주/다음 기수 중 하나
           - 무엇을: 강의/실습/자료/세션/운영 방식 등 구체 단위
           - 누구: 강의 담당자, 튜터, 운영진 등 책임 주체
         - 예를 들어:
           - "[이번 주] Week 1 자료형 파트에 'int/float/str 변환'만 다루는 10분 보충 영상 추가 (담당: 메인 강사)"
           - "[다음 기수] Week 1과 Week 2를 분리하여 반복문은 2주차로 이동 (커리큘럼 담당자 조정)"

      4) 표현 방식:
         - "~임, ~함" 보고서 말투를 유지.
         - 뜬구름 잡는 말 금지. stats와 priority에 근거한 내용만 쓸 것.
         - 숫자를 언급할 때는 '질문 비율', 'unique_users', '난이도 점수' 등을 최소 1~2회 언급.

      아래 Pydantic 스키마 설명에 맞는 JSON만 출력하라.
      {ai_insights_parser.get_format_instructions()}
    """

    response = llm.invoke(prompt)
    ai_insights: CurriculumAIInsights = ai_insights_parser.parse(response.content)
    print("=== AI INSIGHTS GENERATED ===")
    print(ai_insights)
    
    return ai_insights
