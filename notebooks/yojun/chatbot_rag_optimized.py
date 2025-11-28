# chatbot_rag_optimized.py

import time
import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
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

# RAG 체인을 한 번만 만들고 재사용하기 위한 전역 변수
RAG_CHAIN = None


# ==============================================================
# 수준별 답변 규칙
# ==============================================================

GRADE_RULES = {
    "초급": """
[초급자 답변 규칙]

당신은 프로그래밍/데이터 분야를 처음 배우는 초급자를 돕는 학습 도우미입니다.
설명은 반드시 쉬운 한국어로, 짧은 문장 위주로 작성해야 합니다.

아래 6단계 형식을 그대로 따라 답변하세요.

-------------------------------------

1) [질문 이해]
- 사용자가 알고 싶어하는 내용을 한 줄로 다시 정리합니다.
- 전문용어 없이, 쉬운 한국어로 표현합니다.

2) [핵심 한 줄 요약]
- 결론을 가장 쉬운 표현으로 한 문장에 요약합니다.
- 초급자가 바로 이해할 수 있는 단어만 사용합니다.

3) [쉬운 설명]
- 어려운 용어, 영어, 축약어는 최대한 사용하지 않습니다.
- 부득이하게 전문용어가 등장하면:
  → 즉시 괄호 안에 쉬운 뜻을 적습니다.
  예: “라이브러리(미리 만들어둔 기능 묶음)”

4) [비유 / 예시]
- 현실 비유 1개 이상을 제공합니다.
- 예시 코드 1개를 제공하되, 너무 길게 쓰지 않습니다.

5) [추가로 알면 좋은 것]
- 초급자가 부담 없이 받아들일 수 있을 정도로 1~2줄만 확장 설명합니다.

6) [출처]
- 아래 형식으로 정확하게 표기합니다.
  파일명.pdf / p.숫자 또는 p.숫자–숫자

-------------------------------------

[특별 주의 사항]
- 문장은 짧고 명확하게 작성합니다.
- 초급자가 모를 만한 개념은 반드시 풀어서 설명합니다.
- context(강의자료)에 없는 내용은 생성하지 않습니다.
""",
    "중급": """
- 개념의 핵심 정의를 정확하게 제공
- 필요 시 용어 사용 가능하나 불필요한 확장 금지
- 왜 이런 개념이 필요한지 1번 설명
- 실무에서 헷갈리는 포인트도 함께 제공
- 파일명, 페이지 출처를 반드시 함께 명시
""",
    "고급": """
- 내부 동작 원리 중심으로 설명
- 구조, 메커니즘, 메모리·성능 등 심화 내용 포함 가능
- 필요한 경우 수식·전문 용어 사용 가능
- 다른 기술과 비교 설명 가능
- 파일명, 페이지 출처를 반드시 함께 명시
"""
}


# ==============================================================
# RAG 체인 초기화 & 재사용
# ==============================================================

def initialize_rag_chain():
    """
    Chroma 벡터DB + OpenAI 임베딩 + RAG 체인 초기화
    """
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

    # 시스템 프롬프트 (history + context + grade 반영)
    template = """
당신은 부트캠프 학생을 위한 학습 도우미 챗봇입니다.
답변은 반드시 제공된 [Context] 안의 정보만 사용해야 합니다.
문서에 없는 내용은 절대 지어내지 마세요.

[이전 대화]
{history}

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
            # 질문 문자열만 retriever에 전달
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
    return rag_chain


def get_rag_chain():
    """
    RAG 체인을 전역에서 한 번만 생성하고 재사용.
    """
    global RAG_CHAIN
    if RAG_CHAIN is None:
        RAG_CHAIN = initialize_rag_chain()
    return RAG_CHAIN


# ==============================================================
# History 유틸 함수 (멀티턴용)
# ==============================================================

def build_history_text(history, max_turns=3):
    """
    최근 max_turns개의 (질문, 답변)을 history 문자열로 만든다.
    LLM이 이전 대화 흐름을 이해하는 데 사용.
    """
    if not history:
        return ""

    recent = history[-max_turns:]
    lines = []
    for turn in recent:
        lines.append(f"학생: {turn['question']}")
        lines.append(f"AI: {turn['answer']}")
        lines.append("")

    return "\n".join(lines)


# ==============================================================
# 질문 분리 (여러 요청이 섞여 있을 때)
# ==============================================================

def split_questions(user_message: str):
    """
    사용자의 입력에서 '서로 다른 질문/요청'을 의미 단위별로 분리한다.
    예:
      "리스트 문제 1개 내주고 RAG 코드도 보여줘"
    -> ["리스트 문제 1개 내줘", "RAG 코드도 보여줘"]
    """
    splitter = ChatOpenAI(model=LLM_MODEL, temperature=0)

    split_prompt = ChatPromptTemplate.from_template(
        """
사용자의 입력을 보고, 서로 다른 요청이나 질문이 있다면 항목별로 분리하세요.

출력 형식 예시는 아래와 같습니다:

1. 첫 번째 질문...
2. 두 번째 질문...
3. 세 번째 질문...

가능하면 최대한 잘게 나누지 말고,
의미상 자연스럽게 나눠지도록 분리하세요.

사용자 입력:
{message}
"""
    )

    chain = split_prompt | splitter | StrOutputParser()
    raw = chain.invoke({"message": user_message})

    questions = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # "1. 질문..." 형식만 파싱
        if line[0].isdigit() and "." in line:
            _, q = line.split(".", 1)
            q = q.strip()
            if q:
                questions.append(q)

    if not questions:
        return [user_message.strip()]

    return questions


# ==============================================================
# 단일 질문 처리 (history 반영)
# ==============================================================

def answer_single(question: str, grade: str, history: list):
    """
    하나의 질문에 대해:
    - history(이전 대화)를 반영
    - RAG 검색 + LLM 답변
    - 답변을 history에 저장
    """
    if grade not in GRADE_RULES:
        raise ValueError("grade는 '초급', '중급', '고급' 중 하나여야 합니다.")

    rag = get_rag_chain()
    history_text = build_history_text(history)

    answer_text = rag.invoke({
        "question": question,
        "grade": grade,
        "grade_rules": GRADE_RULES[grade],
        "history": history_text,
    })

    # history 저장
    history.append({
        "question": question,
        "answer": answer_text
    })

    return answer_text


# ==============================================================
# 여러 질문 처리 (질문별로 각각 RAG + 출처)
# ==============================================================

def multi_answer(user_message: str, grade: str, history: list):
    """
    한 번에 여러 질문이 섞여 있을 수 있는 user_message를 받아서:
    1) 질문들을 분리하고
    2) 각 질문마다 answer_single()로 답변 생성
    3) 보기 좋게 묶어서 반환
    """
    questions = split_questions(user_message)

    # 질문이 하나만 있으면 단일 질문 처리
    if len(questions) == 1:
        return answer_single(questions[0], grade, history)

    blocks = []
    for idx, q in enumerate(questions, start=1):
        ans = answer_single(q, grade, history)
        block = f"""### 질문 {idx}
> {q}

{ans}

-------------------------------------
"""
        blocks.append(block)

    return "\n".join(blocks)


# ==============================================================
# 터미널에서 테스트용 main 루프
# ==============================================================

if __name__ == "__main__":
    print("\n=== 부트캠프 학습 도우미 RAG 챗봇 ===")
    print("여러 질문을 한 번에 써도 되고, 한 개씩 물어봐도 됩니다.")
    print("종료하려면 'exit'를 입력하세요.\n")

    history = []  # 멀티턴 대화 기록 (나중에 DB로 확장 가능)

    while True:
        user_msg = input("\n📌 질문 입력: ")
        if user_msg.strip().lower() == "exit":
            print("👋 챗봇을 종료합니다.")
            break

        grade = input("💡 난이도 선택 (초급/중급/고급): ").strip()
        if grade.strip().lower() == "exit":
            print("👋 챗봇을 종료합니다.")
            break

        print("\n⏳ 답변 생성 중...\n")

        # 멀티 질문 + 멀티턴 + RAG + 출처까지 모두 포함된 최종 호출
        result = multi_answer(user_message=user_msg, grade=grade, history=history)

        print("🧠 학습 도우미 답변:\n")
        print(result)
        print("\n============================================")
