# ==============================================================
# chatbot_rag_final.py
# 설명 모드 + 학습퀴즈 모드 자동 분기
# Hybrid Cache + Metadata Packing + Context 확장 + 멀티턴 히스토리
# ==============================================================
import os
import time
import numpy as np
from dotenv import load_dotenv
from operator import itemgetter

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda


load_dotenv()

# ==============================================================
# 기본 설정
# ==============================================================

DB_PATH = r"C:\POTENUP\MumulMumul\storage\vectorstore\curriculum_all_new"
COLLECTION = "curriculum_all_new"

LLM_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-large"

SEARCH_K = 3
FETCH_K = 8

RAG_CHAIN = None
RETRIEVER = None


# ==============================================================
# Hybrid Cache (Exact + Semantic)
# ==============================================================

embedder_for_cache = OpenAIEmbeddings(model=EMBEDDING_MODEL)

CACHE = {
    "초급": {"exact": {}, "semantic": []},
    "중급": {"exact": {}, "semantic": []},
    "고급": {"exact": {}, "semantic": []},
}

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def search_cache(question: str, grade: str):
    """캐시 조회"""
    if question in CACHE[grade]["exact"]:
        print("[CACHE HIT] Exact")
        return CACHE[grade]["exact"][question]

    print("[CACHE CHECK] Semantic...")
    q_vec = embedder_for_cache.embed_query(question)

    best_score, best_answer = 0, None
    for entry in CACHE[grade]["semantic"]:
        score = cosine_similarity(q_vec, entry["vector"])
        if score > best_score:
            best_score, best_answer = score, entry["answer"]

    if best_score >= 0.80:
        print(f"[CACHE HIT] Semantic score={best_score:.3f}")
        return best_answer

    return None

def save_to_cache(question: str, grade: str, answer: str):
    """캐시 저장"""
    vec = embedder_for_cache.embed_query(question)
    CACHE[grade]["exact"][question] = answer

    CACHE[grade]["semantic"].append({
        "question": question,
        "vector": vec,
        "answer": answer
    })

    print("[CACHE SAVE] 완료")


# ==============================================================
# "설명 모드" 템플릿
# ==============================================================

GRADE_RULES = {
    "초급": """
[질문 이해]
- 사용자가 무엇을 궁금해하는지 쉬운 말로 한 줄 정리.

[핵심 요약]
- 초보자도 바로 이해할 수 있도록 한 문장으로 요약.

[쉬운 설명]
- 어려운 용어 최소화. 영어/축약어 즉시 풀이.
- 2~4줄 설명.

[비유 + 예시 코드]
- 현실 비유 제공 (1~2개)
- 3~7줄 간단한 코드 예시 포함.

[추가 설명]
- 1~2줄.

[연습 문제]
- 1~2개 + 힌트 포함.

[출처]
- 파일명 + 페이지 번호 명확히 표시.
""",

    "중급": """
[핵심 개념 요약]
- 개념을 한 문장으로 정리.

[정확한 정의]
- context 기반 정의를 정확히 2~4줄 작성.

[왜 필요한가]
- 실무/학습 관점 1~2줄.

[주의 포인트]
- 헷갈리는 부분 1~3개.

[예시 코드]
- 3~8줄.

[출처]
- 파일명 + 페이지 번호 포함.
""",

    "고급": """
[핵심 요약]
- 개념의 본질을 한 문장으로 요약.

[동작 원리]
- 내부 구조/메커니즘 중심 설명.

[성능/메모리]
- context 기반 분석.

[비교]
- 유사 기술 비교 1~3개 bullet.

[사례]
- 3~8줄로 고급 예시.

[출처]
- 파일명 + 페이지 번호.
"""
}


# ==============================================================
# 학습퀴즈 생성 모드 템플릿
# ==============================================================

QUIZ_RULES_TEMPLATE = """
[모드]
- 지금 요청은 '학습퀴즈 생성'입니다.
- 반드시 JSON 형식만 출력하세요.

[JSON 스키마]
{
  "total": 문제수,
  "items": [
    {
      "number": 1,
      "type": "ox" 또는 "multiple" 또는 "short",
      "question": "문제 내용",
      "choices": ["보기1","보기2"] 또는 null,
      "answer": "정답",
      "difficulty": "초급/중급/고급",
      "source_file": "파일명",
      "source_page": 1
    }
  ]
}

[문제 생성 규칙]
- 반드시 context 안의 내용만으로 문제 생성.
- type은 ox, short, multiple 섞어서 생성.
- 난이도는 {GRADE_LEVEL} 레벨에 맞게.
- 출처는 context 기반으로 정확히 넣기.

[출력 규칙]
- JSON만 출력.  
- 절대 설명 문장 출력 금지.
"""



# ==============================================================
# 문제/퀴즈 요청인지 판단
# ==============================================================

def is_quiz_request(q: str):
    q2 = q.replace(" ", "")
    keywords = ["퀴즈", "OX", "문제", "테스트", "연습문제", "5문제", "10문제"]
    return any(k.lower() in q2.lower() for k in keywords)


def build_rules(question: str, grade: str) -> str:
    if is_quiz_request(question):
        print("[MODE] 학습퀴즈 모드로 동작합니다.")
        # format 대신 안전하게 replace만 사용
        return QUIZ_RULES_TEMPLATE.replace("{GRADE_LEVEL}", grade)
    else:
        return GRADE_RULES[grade]


# ==============================================================
# metadata → 텍스트 패킹
# ==============================================================

def format_docs_with_metadata(docs):
    parts = []

    for idx, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}

        file_name = (
            meta.get("filename")
            or meta.get("file_name")
            or meta.get("source")
            or meta.get("filename_eng")
            or "알 수 없는 파일"
        )

        page = meta.get("page") or meta.get("page_number") or meta.get("page_index")

        header = f"[{idx}] 출처: {file_name}"
        if page:
            header += f" / p.{page}"

        body = doc.page_content or ""

        parts.append(f"{header}\n{body}")

    return "\n\n".join(parts)



# ==============================================================
# 질문 난이도 → 검색량 자동 확장 (Context 확장)
# ==============================================================

def estimate_topic_count(question: str) -> int:
    joiners = ["와 ", "과 ", "이랑", "랑", " 및 ", " 그리고 ", ",", "/"]
    score = 1
    for j in joiners:
        if j in question:
            score += 1
    return max(1, min(score, 3))

def adjust_retriever_for_question(question: str):
    global RETRIEVER
    if RETRIEVER is None:
        return

    t = estimate_topic_count(question)

    if t == 1:
        k, f = 3, 8
    elif t == 2:
        k, f = 6, 16
    else:
        k, f = 9, 24

    RETRIEVER.search_kwargs["k"] = k
    RETRIEVER.search_kwargs["fetch_k"] = f

    print(f"[RETRIEVER] topic={t} → k={k}, fetch_k={f}")


# ==============================================================
# RAG 체인 초기화
# ==============================================================

def initialize_rag_chain():
    global RETRIEVER

    print("[LOG] RAG 체인 초기화…")
    start = time.time()

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    vectorstore = Chroma(
        persist_directory=DB_PATH,
        embedding_function=embeddings,
        collection_name=COLLECTION
    )

    RETRIEVER = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": SEARCH_K, "fetch_k": FETCH_K}
    )

    template = """
당신은 부트캠프 학습 도우미 RAG 챗봇입니다.
반드시 [Context] 안의 정보만 사용해서 답변하거나 문제를 생성합니다.

[이전 대화]
{history}

[학생 수준]
{grade}

[규칙]
{rules}

-------------------------
[Context]
{context}

[Question]
{question}
-------------------------
"""

    prompt = ChatPromptTemplate.from_template(template)
    model = ChatOpenAI(model=LLM_MODEL, temperature=0.2)

    chain = (
        {
            "docs": itemgetter("question") | RETRIEVER,
            "question": itemgetter("question"),
            "rules": itemgetter("rules"),
            "grade": itemgetter("grade"),
            "history": itemgetter("history"),
        }
        | RunnableLambda(lambda x: {
            **x,
            "context": format_docs_with_metadata(x["docs"])
        })
        | prompt
        | model
        | StrOutputParser()
    )

    print(f"[Time] init 완료: {time.time() - start:.2f}s")
    return chain


def get_rag_chain():
    global RAG_CHAIN
    if RAG_CHAIN is None:
        RAG_CHAIN = initialize_rag_chain()
    return RAG_CHAIN



# ==============================================================
# HISTORY (멀티턴)
# ==============================================================

def build_history_text(history, max_turns=2):
    if not history:
        return ""
    recent = history[-max_turns:]
    return "\n".join([f"학생: {h['question']}\nAI: {h['answer']}" for h in recent])



# ==============================================================
# 메인 답변 함수
# ==============================================================

def answer_single(question: str, grade: str, history: list):
    """1질문 → 1답변"""

    cached = search_cache(question, grade)
    if cached:
        print("[INFO] 캐시 사용")
        return cached

    # context 확장
    adjust_retriever_for_question(question)

    # 모드 자동 결정
    rules_text = build_rules(question, grade)

    rag = get_rag_chain()
    history_text = build_history_text(history)

    start = time.time()
    answer = rag.invoke({
        "question": question,
        "grade": grade,
        "rules": rules_text,
        "history": history_text
    })
    print(f"[Time] 답변 생성: {time.time() - start:.3f}s")

    save_to_cache(question, grade, answer)

    history.append({"question": question, "answer": answer})
    return answer



# ==============================================================
# CLI 실행부
# ==============================================================

if __name__ == "__main__":
    print("\n=== RAG 챗봇 (설명 + 학습퀴즈 2모드 자동 분기) ===\n")
    history = []

    while True:
        msg = input("\n📌 질문 입력: ").strip()
        if msg.lower() == "exit":
            print("\n👋 종료합니다.")
            break

        grade = input("💡 난이도 (초급/중급/고급): ").strip()

        print("\n⏳ 생성 중...\n")
        result = answer_single(msg, grade, history)

        print("\n🧠 학습 도우미 응답:\n")
        print(result)
        print("\n-----------------------------------\n")