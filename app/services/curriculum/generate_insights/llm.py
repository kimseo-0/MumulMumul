# app/services/curriculum/enrich_llm.py

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI

from app.core.mongodb import CurriculumConfig


# LLM 인스턴스 (기존 llm.py와 같은 모델을 쓰거나, 더 가벼운 걸 써도 됨)
enrich_llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.0,
)


def _build_curriculum_block(curriculum_config: Optional[CurriculumConfig]) -> str:
    if not curriculum_config or not curriculum_config.weeks:
        return "커리큘럼 정보가 제공되지 않음.\n"

    lines = []
    for week in curriculum_config.weeks:
        topics_str = ", ".join(week.topics)
        lines.append(f"- {week.week_label}: {topics_str}")
    return "\n".join(lines)


def _build_judge_prompt(
    logs: List[Dict[str, Any]],
    curriculum_config: Optional[CurriculumConfig],
) -> str:
    """
    여러 개의 질문 로그를 한 번에 분석하도록 프롬프트를 구성한다.
    logs: [{ "_id": ..., "user_id": ..., "content": "질문 텍스트" }, ...]
    """

    items_text = ""
    for i, log in enumerate(logs, start=1):
        text = (log.get("content") or "").replace("\n", " ").strip()
        items_text += f"{i}. id={log['_id']} user={log.get('user_id')} text={text}\n"

    curriculum_block = _build_curriculum_block(curriculum_config)

    prompt = f"""
        너는 온라인 부트캠프 학습 질문을 분석하는 AI 에이전트임.

        이 캠프의 커리큘럼 구조는 다음과 같음:
        {curriculum_block}

        위 커리큘럼에서 다루는 토픽에 해당하면 curriculum_scope="in" 으로,
        커리큘럼에 없는 내용(커리어, 포트폴리오, IDE 설정 등)이면 curriculum_scope="out" 으로 판단하라.

        각 질문에 대해 아래 항목을 추론해야 함.

        - curriculum_topic: 질문이 다루는 주요 토픽 키
        - 가능한 경우 위 커리큘럼 topics 중 하나를 사용
        - 없으면 대략적인 키워드를 소문자 영문으로 작성 (예: "career", "portfolio", "ide")
        - curriculum_scope: "in" 또는 "out"
        - pattern_tags: 다음 태그 중 복수 선택
        - "concept_confusion"
        - "api_usage"
        - "expected_output_mismatch"
        - "environment_issue"
        - "other"
        - intent: 학습자가 이 질문을 통해 알고 싶은 것을 한 줄 한국어 문장으로 요약

        반환 형식:
        - 반드시 JSON 배열로만 응답할 것.
        - 각 원소는 아래 형식을 따를 것.

        [
        {{
            "id": "원본 로그의 id 값 문자열",
            "curriculum_topic": "pandas",
            "curriculum_scope": "in",
            "pattern_tags": ["concept_confusion", "api_usage"],
            "intent": "groupby 결과가 왜 다르게 나오는지 이해하고 싶음"
        }},
        ...
        ]

        아래는 분석 대상 질문 목록임:

        {items_text}

        위 규칙에 맞게 JSON 배열만 반환하라.
        """
    return prompt


def enrich_logs_with_llm(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    주어진 로그 리스트에 대해 LLM을 호출하여
    curriculum_topic / curriculum_scope / pattern_tags / intent 를 생성한다.
    반환값: [{ "id": "...", "curriculum_topic": "...", "curriculum_scope": "...",
               "pattern_tags": [...], "intent": "..." }, ...]
    """
    
    prompt = _build_judge_prompt(logs)
    resp = enrich_llm.invoke(prompt)
    content = resp.content
    enriched_list = json.loads(content)

    return enriched_list
