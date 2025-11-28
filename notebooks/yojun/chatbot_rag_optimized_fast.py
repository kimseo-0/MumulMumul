# chatbot_rag_optimized.py
# metadata 패킹 + 구조화 템플릿 + 최적화된 RAG 버전

import os
import time
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

LLM_MODEL = "gpt-4o-mini"           # 속도+정확도 균형
EMBEDDING_MODEL = "text-embedding-3-large"  # 기존 DB와 차원 맞춤

SEARCH_K = 3       # 최적화된 검색 개수
FETCH_K = 8        # 후보 개수

RAG_CHAIN = None   # 전역 캐싱용


# ==============================================================
# 구조화 템플릿 (초급 / 중급 / 고급)
# ==============================================================

GRADE_RULES = {
    "초급": """
[질문 이해]
- 사용자가 무엇을 궁금해하는지 쉬운 말로 한 줄로 다시 정리합니다.

[핵심 한 줄 요약]
- 이 개념을 초보자가 바로 이해할 수 있도록 한 문장으로 요약합니다.

[쉬운 설명]
- 어려운 용어, 영어, 축약어는 최대한 피하고
  필요할 때는 괄호로 즉시 풀이합니다.
  예: “라이브러리(미리 만들어둔 기능 묶음)”
- 설명은 2~4줄로 간단하고 직관적으로 작성합니다.

[비유 + 예시 코드]
- 현실 세계의 비유를 1~2개 제공합니다.
  조건:
    1) 생활 속 물건, 음식, 기존 경험 등 초보자가 바로 떠올릴 수 있는 대상
    2) 비유가 개념과 1:1로 연결되도록 설명

- 비유 → 코드 개념 연결 과정을 명확히 적습니다.
  예: “요리 레시피에 재료를 넣으면 결과가 나오듯,
       함수에 입력을 넣으면 출력이 나옵니다.”

- 초보자가 따라 칠 수 있는 짧은 코드 예시(3~7줄)를 제공합니다.

[추가로 알면 좋은 점]
- 부담되지 않을 정도의 추가 설명 1~2줄

[연습 문제]
- 초보자가 풀 수 있는 짧은 연습 문제 1~2개 제시
- 각 문제에 1줄 힌트 제공

[출처]
- 사용된 context chunk들의 파일명 + 페이지 번호를 정활히 표기합니다.
  예: “01 파이썬 기초 문법 I.pdf / p.3”
""",

    "중급": """
[핵심 개념 요약]
- 개념을 한 문장으로 명확하게 요약합니다.

[정확한 정의]
- context 기반으로 2~4줄 안에서 정의를 설명합니다.
- 필요 시 용어 사용 가능 (불필요하게 확장 금지)

[왜 필요한가]
- 이 개념이 왜 중요한지 실무 또는 학습 관점에서 1~2줄로 설명합니다.

[실무 주의 포인트]
- 실무 또는 프로젝트에서 자주 실수하는 부분, 헷갈리는 포인트 1~3개 제시

[예시 코드 또는 간단 예제]
- 중급자 수준의 코드 예시를 3~8줄 제공

[출처]
- 사용된 context chunk들의 파일명 + 페이지 번호를 정활히 표기합니다.
""",

    "고급": """
[핵심 개념 요약]
- 개념의 본질을 한 문장으로 요약합니다.

[내부 동작 원리]
- 구조, 메커니즘, 흐름 중심으로 원리를 설명합니다.
- context 기반으로 서술하며 불필요한 외부 지식 확장은 금지합니다.

[성능/메모리/효율성 관점]
- 가능한 경우 시간 복잡도, 메모리 사용, 처리 구조 등을 분석합니다.
- context에 존재하는 내용만 사용합니다.

[비교]
- 유사 개념 또는 대안 기술과의 차이를 1~3개 bullet로 설명합니다.

[예시 또는 적용 사례]
- 고급자에게 적합한 예시 또는 기술 적용 사례를 3~8줄 사이로 작성합니다.

[출처]
- 사용된 context chunk들의 파일명 + 페이지 번호를 정활히 표기합니다.
"""
}


# ==============================================================
# metadata → 텍스트로 패킹하는 유틸 함수
# ==============================================================

def format_docs_with_metadata(docs):
    """
    retriever가 반환한 Document 리스트를
    [출처 정보 + 내용] 형태의 긴 문자열로 변환한다.

    각 문서는 대략 이런 형식으로 변환됨:

    [1] 출처: 03 데이터 분석 기초 - 판다스.pdf / p.5
    문서 내용...

    [2] 출처: 01 파이썬 기초 문법 I.pdf / p.3
    문서 내용...
    """
    parts = []

    for idx, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}

        # 파일명 후보 키들
        file_name = (
            meta.get("file_name")
            or meta.get("source")
            or meta.get("filename")
            or "알 수 없는 파일"
        )

        # 페이지 번호 후보 키들
        page = (
            meta.get("page")
            or meta.get("page_number")
            or meta.get("page_index")
        )

        if page is not None:
            header = f"[{idx}] 출처: {file_name} / p.{page}"
        else:
            header = f"[{idx}] 출처: {file_name}"

        body = doc.page_content or ""
        parts.append(f"{header}\n{body}")

    return "\n\n".join(parts)


# ==============================================================
# RAG 체인 초기화 + 캐싱
# ==============================================================

def initialize_rag_chain():
    print("[LOG] RAG 체인 초기화 시작")
    start = time.time()

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

    # 시스템 프롬프트
    template = """
당신은 부트캠프 학생을 위한 학습 도우미 RAG 챗봇입니다.
답변은 반드시 아래 [Context] 안의 정보만 사용해야 합니다.
문서에 없는 내용은 절대 생성하지 마세요.
답변 마지막에는 반드시 출처(파일명, 페이지)를 명시하세요.

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
위 구조와 규칙을 따라 답변하세요.
"""

    prompt = ChatPromptTemplate.from_template(template)
    model = ChatOpenAI(model=LLM_MODEL, temperature=0.2)

    # 1) question → retriever → docs
    # 2) docs를 사람이 읽기 좋은 문자열(context)로 변환
    # 3) prompt에 전달
    chain = (
        {
            "docs": itemgetter("question") | retriever,
            "question": itemgetter("question"),
            "grade": itemgetter("grade"),
            "grade_rules": itemgetter("grade_rules"),
            "history": itemgetter("history"),
        }
        | RunnableLambda(
            lambda x: {
                **x,
                "context": format_docs_with_metadata(x["docs"])
            }
        )
        | prompt
        | model
        | StrOutputParser()
    )

    print(f"[Time] RAG 체인 초기화 완료: {time.time() - start:.3f}초")
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
    """
    최근 max_turns 개의 질문/답변만 사용해 LLM에 전달.
    """
    if not history:
        return ""
    recent = history[-max_turns:]
    return "\n".join(
        [f"학생: {h['question']}\nAI: {h['answer']}\n" for h in recent]
    )


# ==============================================================
# 질문 분리 (여러 요청이 섞여 있을 때)
# ==============================================================

def split_questions(user_message: str):
    """
    "리스트 설명해주고, 함수 예제도 보여줘" 같은 입력을
    1. 리스트 설명해줘
    2. 함수 예제도 보여줘
    이런 식으로 분리.
    """
    splitter = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = ChatPromptTemplate.from_template(
        """
사용자의 입력에서 서로 다른 질문을 아래 형식으로 분리하세요.

1. 질문1
2. 질문2

너무 잘게 쪼개지 말고, 의미 단위로 자연스럽게 나누세요.

사용자 입력:
{message}
"""
    )

    chain = prompt | splitter | StrOutputParser()
    raw = chain.invoke({"message": user_message})

    questions = []

    for line in raw.splitlines():
        line = line.strip()
        if line and line[0].isdigit() and "." in line:
            try:
                _, q = line.split(".", 1)
                q = q.strip()
                if q:
                    questions.append(q)
            except ValueError:
                continue

    if not questions:
        return [user_message.strip()]

    return questions


# ==============================================================
# 단일 질문 처리
# ==============================================================

def answer_single(question: str, grade: str, history: list):
    """
    하나의 질문에 대해:
    - history 반영
    - RAG 검색 + LLM 답변
    - 답변을 history에 저장
    """
    if grade not in GRADE_RULES:
        raise ValueError("grade는 '초급', '중급', '고급' 중 하나여야 합니다.")

    rag = get_rag_chain()
    history_text = build_history_text(history)

    start = time.time()
    answer = rag.invoke({
        "question": question,
        "grade": grade,
        "grade_rules": GRADE_RULES[grade],
        "history": history_text,
    })
    print(f"[Time] LLM 답변 생성: {time.time() - start:.3f}초")

    history.append({"question": question, "answer": answer})
    return answer


# ==============================================================
# 여러 질문 처리
# ==============================================================

def multi_answer(user_message: str, grade: str, history: list):
    """
    여러 질문이 섞인 경우:
    1) split_questions로 나누고
    2) 각 질문마다 answer_single 호출
    3) 보기 좋게 묶어서 반환
    """
    questions = split_questions(user_message)

    # 질문이 하나면 단일 처리
    if len(questions) == 1:
        return answer_single(questions[0], grade, history)

    blocks = []
    for idx, q in enumerate(questions, start=1):
        ans = answer_single(q, grade, history)
        block = f"""### 질문 {idx}
> {q}

{ans}

---
"""
        blocks.append(block)

    return "\n".join(blocks)


# ==============================================================
# CLI 테스트용 main
# ==============================================================

if __name__ == "__main__":
    print("\n=== metadata 패킹 + 구조화 템플릿 RAG 챗봇 ===\n")
    print("여러 질문을 한 번에 써도 되고, 하나씩 물어봐도 됩니다.")
    print("종료하려면 'exit'를 입력하세요.\n")

    history = []

    while True:
        msg = input("\n📌 질문 입력: ").strip()
        if msg.lower() == "exit":
            print("👋 챗봇을 종료합니다.")
            break

        grade = input("💡 난이도 선택 (초급/중급/고급): ").strip()
        if grade.lower() == "exit":
            print("👋 챗봇을 종료합니다.")
            break

        print("\n⏳ 답변 생성 중...\n")
        result = multi_answer(msg, grade, history)

        print("\n🧠 학습 도우미 답변:\n")
        print(result)
        print("\n============================================")