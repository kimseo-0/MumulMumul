# chatbot_rag_optimized_fast.py
# "최적 속도 버전" - 프롬프트 최적화 + 모델 변경 + retriever 최적화

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
# 기본 설정 (속도 중심 튜닝)
# ==============================================================

DB_PATH = r"C:\POTENUP\MumulMumul\storage\vectorstore\curriculum_all_new"
COLLECTION = "curriculum_all_new"

LLM_MODEL = "gpt-4o-mini"   # ★ 기존 gpt-4o-mini → 빠른 모델로 변경
EMBEDDING_MODEL = "text-embedding-3-large"  # ★ 속도 중심

SEARCH_K = 3       # ★ 기존 5 → 3
FETCH_K = 8        # ★ 기존 20 → 8

RAG_CHAIN = None   # 캐싱


# ==============================================================
# 수준별 규칙 (최적화된 간단 버전)
# ==============================================================

GRADE_RULES = {
    "초급": """
- 어려운 용어/영어 최소화
- 문장은 짧게
- 필요한 경우 괄호로 풀이
- 답변 형식:
  1) 질문 이해(한줄)
  2) 핵심 요약(한줄)
  3) 쉬운 설명
  4) 비유 + 짧은 예시 코드
  5) 추가 설명(1~2줄)
  6) 출처
""",
    "중급": """
- 핵심 개념 정확히
- 용어 사용 가능
- 왜 필요한지(1줄)
- 실무 주의점 포함
- 출처 포함
""",
    "고급": """
- 내부 동작 원리 중심
- 구조/성능/비교 설명 가능
- 필요 시 수식/전문용어 사용
- 출처 포함
"""
}

# ==============================================================
# RAG 체인 초기화 + 캐싱
# ==============================================================

def initialize_rag_chain():
    start = time.time()
    print("[LOG] 초기화 시작")

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

    template = """
당신은 부트캠프 학생을 위한 학습 도우미 챗봇입니다.
답변은 반드시 제공된 Context 안의 정보만 이용하여 작성해야 합니다.
문서에 없는 내용은 절대 생성하지 마세요.
출처(파일명, 페이지)를 반드시 포함하세요.

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

가능한 한 간단하고 짧게 답변하세요.
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

    print(f"[Time] RAG 초기화: {time.time() - start:.3f}초")
    return rag_chain


def get_rag_chain():
    global RAG_CHAIN
    if RAG_CHAIN is None:
        RAG_CHAIN = initialize_rag_chain()
    return RAG_CHAIN


# ==============================================================
# HISTORY
# ==============================================================

def build_history_text(history, max_turns=2):
    """
    history 길이를 2턴만 반영 → 속도 개선
    """
    if not history:
        return ""
    recent = history[-max_turns:]
    return "\n".join([
        f"학생: {h['question']}\nAI: {h['answer']}\n"
        for h in recent
    ])


# ==============================================================
# 질문 분리
# ==============================================================

def split_questions(user_message: str):
    splitter_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = ChatPromptTemplate.from_template(
        """
사용자의 입력에서 서로 다른 질문이 있다면 분리하세요.

출력 형식:
1. 질문1
2. 질문2

사용자 입력:
{message}
"""
    )

    chain = prompt | splitter_model | StrOutputParser()
    raw = chain.invoke({"message": user_message})

    questions = []
    for line in raw.splitlines():
        line = line.strip()
        if line and line[0].isdigit() and "." in line:
            try:
                _, q = line.split(".", 1)
                questions.append(q.strip())
            except:
                pass

    if not questions:
        return [user_message]
    return questions


# ==============================================================
# 단일 질문 답변
# ==============================================================

def answer_single(question: str, grade: str, history: list):
    rag = get_rag_chain()
    history_text = build_history_text(history)

    start = time.time()
    
    answer_text = rag.invoke({
        "question": question,
        "grade": grade,
        "grade_rules": GRADE_RULES[grade],
        "history": history_text,
    })

    print(f"[Time] LLM 답변 생성: {time.time() - start:.3f}초")

    history.append({"question": question, "answer": answer_text})
    return answer_text


# ==============================================================
# 여러 질문 처리
# ==============================================================

def multi_answer(user_message: str, grade: str, history: list):
    questions = split_questions(user_message)

    if len(questions) == 1:
        return answer_single(questions[0], grade, history)

    outputs = []
    for idx, q in enumerate(questions, start=1):
        ans = answer_single(q, grade, history)
        outputs.append(
            f"### 질문 {idx}\n> {q}\n\n{ans}\n\n---"
        )
    return "\n".join(outputs)


# ==============================================================
# CLI 테스트
# ==============================================================

if __name__ == "__main__":
    print("\n=== 최적 속도 버전 RAG 챗봇 ===\n")

    history = []

    while True:
        msg = input("\n📌 질문 입력(exit 종료): ")
        if msg.lower() == "exit":
            break

        grade = input("💡 난이도(초급/중급/고급): ").strip()

        print("\n⏳ 답변 생성 중...\n")
        result = multi_answer(msg, grade, history)

        print("\n🧠 답변:\n", result)
        print("\n------------------------------------\n")
