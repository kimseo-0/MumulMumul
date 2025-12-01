# app/services/curriculum/enrich_llm.py

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI


# LLM 인스턴스 (기존 llm.py와 같은 모델을 쓰거나, 더 가벼운 걸 써도 됨)
enrich_llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.0,
)


def _build_prompt(logs: List[Dict[str, Any]]) -> str:
    """
    여러 개의 질문 로그를 한 번에 분석하도록 프롬프트를 구성한다.
    logs: [{ "_id": ..., "user_id": ..., "content": "질문 텍스트" }, ...]
    """

    items_text = ""
    for i, log in enumerate(logs, start=1):
        text = (log.get("content") or "").replace("\n", " ").strip()
        items_text += f"{i}. id={log['_id']} user={log.get('user_id')} text={text}\n"

    # 패턴 태그 후보는 처음엔 소수만 사용해서 안정적으로 시작
    prompt = f"""
        너는 온라인 부트캠프 학습 질문을 분석하는 AI 에이전트임.
        각 질문에 대해 아래 항목을 추론해야 함.

        - curriculum_topic: 질문이 다루는 커리큘럼 토픽명
        예: "python_basics", "pandas", "visualization", "eda", "nlp_network", "career", "ide", "portfolio" 등
        - curriculum_scope: "in" 또는 "out"
        - in: 공식 커리큘럼 범위 안의 내용
        - out: 커리큘럼 외(커리어, 포트폴리오, IDE 설정 등)
        - pattern_tags: 다음 태그 중 복수 선택
            - "concept_confusion": 개념/정의가 헷갈리는 경우 (왜, 이유, 개념이 이해 안 됨)
            - "api_usage": 함수/메서드 사용법, 문법, 옵션이 어려운 경우
            - "expected_output_mismatch": 코드가 돌아가지만 결과가 예상과 다를 때
            - "environment_issue": 설치, 경로, 버전, IDE 설정, 에러메시지 관련
        - "other": 위에 해당하지 않는 기타 패턴
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
    
    prompt = _build_prompt(logs)
    resp = enrich_llm.invoke(prompt)
    content = resp.content
    enriched_list = json.loads(content)

    return enriched_list
