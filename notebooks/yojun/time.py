# chatbot_rag_optimized.py (시간 측정 포함 버전)

import os
import time
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
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

RAG_CHAIN = None  # 전역 체인 캐싱

# ==============================================================
# 수준별 답변 규칙
# ==============================================================

GRADE_RULES = {
    "초급": """
[초급자 답변 규칙]

당신은 프로그래밍/데이터 분야를 처음 배우는 초급자를 돕는 학습 도우미입니다.
설명은 반드시 쉬운 한국어로, 짧은 문장 위주로 작성해야 합니다.

--- (생략: 너가 직접 작성한 초급 템플릿 내용 그대로 유지) ---
""",
    "중급": """
- 개념의 핵심 정의를 정확하게 제공
- 필요 시 용어 사용 가능하나 불필요한 확장 금지
- 왜 이런 개념이 필요한지 1번 설명
- 실무에서 헷갈리는 포인트도 함께 제공
- 출처 명시
""",
    "고급": """
- 내부 동작 원리 중심 설명
- 구조, 메커니즘, 성능, 메모리 등 심화 내용 포함 가능
- 다른 기술과 비교 설명 가능
- 출처 명시
"""
}

# ==============================================================
# RAG 체인 초기화 + 캐싱
# ==============================================================

def initialize_rag_chain():
    print("\n[LOG] RAG 체인 초기화 시작")
    start = time.time()

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = Chroma(
        persist_directory=DB_PATH,
        embedding_function=embeddings,
        collection_name=COLLECTION
    )

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": SEARCH_K, "fetch_k": FETCH_K}
    )

    template = """
당신은 부트캠프 학생을 위한 학습 도우미 챗봇입니다.
답변은 반드시 제공된 Context 안의 정보만 사용해야 합니다.

[이전 대화]
{history}

[학생 수준]
{grade}

[답변 규칙]
{grade_rules}

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
            "context": itemgetter("question") | retriever,
            "question": itemgetter("question"),
            "grade": itemgetter("grade"),
            "grade_rules": itemgetter("grade_rules"),
            "history": itemgetter("history"),
        }
        | prompt
        | model
        | StrOutputParser()
    )

    print(f"[Time] RAG 체인 초기화: {time.time() - start:.3f}초")
    return rag_chain


def get_rag_chain():
    global RAG_CHAIN
    if RAG_CHAIN is None:
        RAG_CHAIN = initialize_rag_chain()
    return RAG_CHAIN

# ==============================================================
# History 생성
# ==============================================================

def build_history_text(history, max_turns=3):
    if not history:
        return ""
    recent = history[-max_turns:]
    text = ""
    for turn in recent:
        text += f"학생: {turn['question']}\n"
        text += f"AI: {turn['answer']}\n\n"
    return text

# ==============================================================
# 질문 분리 (LLM 호출 포함 → 시간 측정)
# ==============================================================

def split_questions(user_message: str):
    start = time.time()

    splitter = ChatOpenAI(model=LLM_MODEL, temperature=0)

    prompt = ChatPromptTemplate.from_template(
        """
사용자의 입력을 보고, 다른 요청/질문이 있다면 아래처럼 분리하세요.
1. 질문1
2. 질문2

사용자 입력:
{message}
"""
    )

    chain = prompt | splitter | StrOutputParser()
    raw = chain.invoke({"message": user_message})

    # 결과 파싱
    questions = []
    for line in raw.splitlines():
        line = line.strip()
        if line and line[0].isdigit() and "." in line:
            _, q = line.split(".", 1)
            questions.append(q.strip())

    if not questions:
        questions = [user_message]

    print(f"[Time] 질문 분리(split_questions): {time.time() - start:.3f}초")
    return questions

# ==============================================================
# 단일 질문 처리 (시간 측정 포함)
# ==============================================================

def answer_single(question: str, grade: str, history: list):
    total_start = time.time()

    rag = get_rag_chain()
    history_text = build_history_text(history)

    # LLM 호출 시간 측정
    llm_start = time.time()
    answer_text = rag.invoke({
        "question": question,
        "grade": grade,
        "grade_rules": GRADE_RULES[grade],
        "history": history_text,
    })
    llm_end = time.time()

    print(f"[Time] LLM 답변 생성: {llm_end - llm_start:.3f}초")
    print(f"[Time] answer_single 전체 처리: {time.time() - total_start:.3f}초")

    # history 저장
    history.append({"question": question, "answer": answer_text})

    return answer_text

# ==============================================================
# 여러 질문 처리
# ==============================================================

def multi_answer(user_message: str, grade: str, history: list):
    total_start = time.time()

    questions = split_questions(user_message)

    # 질문 하나면 단일 처리
    if len(questions) == 1:
        return answer_single(questions[0], grade, history)

    outputs = []
    for idx, q in enumerate(questions, start=1):
        q_start = time.time()
        ans = answer_single(q, grade, history)
        outputs.append(f"### 질문 {idx}\n> {q}\n\n{ans}\n\n---")
        print(f"[Time] 질문 {idx} 처리시간: {time.time() - q_start:.3f}초")

    print(f"[Time] multi_answer 전체 처리: {time.time() - total_start:.3f}초")
    return "\n".join(outputs)

# ==============================================================
# CLI 테스트 루프
# ==============================================================

if __name__ == "__main__":
    print("\n=== RAG 학습 도우미 (시간측정 포함) ===\n")

    history = []

    while True:
        msg = input("\n📌 질문 입력(exit 종료): ")
        if msg.lower() == "exit":
            break

        grade = input("💡 난이도(초급/중급/고급): ").strip()

        print("\n⏳ 답변 생성 중...\n")

        result = multi_answer(msg, grade, history)

        print("\n🧠 답변:\n", result)
        print("\n====================================\n")
