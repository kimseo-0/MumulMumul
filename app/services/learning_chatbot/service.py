# chatbot_rag_optimized.py

import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import pandas as pd
from operator import itemgetter

load_dotenv()

# ==============================================================
# 기본 설정
# ==============================================================

DB_PATH = r"C:\POTENUP\MumulMumul\storage\vectorstore\curriculum_all_new"
COLLECTION = "curriculum_all_new"

LLM_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-large"

SEARCH_K = 5
FETCH_K = 20

# ==============================================================
# 수준별 답변 규칙
# ==============================================================

GRADE_RULES = {
    "초급": """
- 어려운 단어 사용 금지
- 전문 용어 등장 시 반드시 쉬운 말로 풀어서 먼저 설명
- 비유·예시 중심으로 설명
- 너무 긴 문장은 금지 (짧게 끊어서 설명)
""",
    "중급": """
- 개념의 핵심 정의를 정확하게 제공
- 필요 시 용어 사용 가능하나 불필요한 확장 금지
- 왜 이런 개념이 필요한지 1번 설명
- 실무에서 헷갈리는 포인트도 함께 제공
""",
    "고급": """
- 내부 동작 원리 중심으로 설명
- 구조, 메커니즘, 메모리·성능 등 심화 내용 포함 가능
- 필요한 경우 수식·전문 용어 사용 가능
- 다른 기술과 비교 설명 가능
"""
}

# ==============================================================
# RAG 체인 초기화
# ==============================================================

def initialize_rag_chain():
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    vectorstore = Chroma(
        persist_directory=DB_PATH,
        embedding_function=embeddings,
        collection_name=COLLECTION,
    )

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": SEARCH_K, "fetch_k": FETCH_K}
    )

    # ----------------------------
    # 시스템 프롬프트 (최적화 버전)
    # ----------------------------
    template = """
    당신은 부트캠프 학생을 위한 학습 도우미 챗봇입니다.
    답변은 반드시 제공된 [Context] 안의 정보만 사용해야 합니다.
    문서에 없는 내용은 절대 지어내지 마세요.

    [학생 수준]
    {grade}

    [답변 규칙]
    {grade_rules}

    [답변 조건]
    - 설명은 반드시 학생 수준에 맞춰서 작성
    - 답변은 한국어로 작성
    - 출처(파일명, 페이지 등) 반드시 명시
    - Context 바깥 정보는 사용 금지

    -------------------------
    [Context]
    {context}

    [Question]
    {question}
    -------------------------
    """

    prompt = ChatPromptTemplate.from_template(template)
    model = ChatOpenAI(model=LLM_MODEL, temperature=0.2)

    rag_chain = (
        {
            # 질문 문자열만 꺼내서 retriever에 전달
            "context": itemgetter("question") | retriever,
            # 나머지도 각각 필요한 키만 전달
            "question": itemgetter("question"),
            "grade": itemgetter("grade"),
            "grade_rules": itemgetter("grade_rules"),
        }
        | prompt
        | model
        | StrOutputParser()
    )
    return rag_chain

# ==============================================================
# 챗봇 호출 함수
# ==============================================================

def answer(question, grade = "중급"):
    if grade not in GRADE_RULES:
        raise ValueError("grade는 '초급', '중급', '고급' 중 하나여야 합니다.")

    rag = initialize_rag_chain()

    return rag.invoke({
        "question": question,
        "grade": grade,
        "grade_rules": GRADE_RULES[grade]
    })