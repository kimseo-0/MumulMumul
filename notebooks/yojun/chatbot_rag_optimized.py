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
# History 기반 멀티턴 지원 함수 추가
# ==============================================================

def build_history_text(history, max_turns=3):
    """
    최근 max_turns개의 대화 기록을 문자열로 합쳐 반환.
    GPT가 이전 맥락을 이해하도록 도와준다.
    """
    if not history:
        return ""

    recent = history[-max_turns:]

    hist_text = ""
    for turn in recent:
        hist_text += f"학생: {turn['question']}\n"
        hist_text += f"AI: {turn['answer']}\n\n"

    return hist_text


def answer_with_history(question, grade, history):
    """
    멀티턴 질문을 처리하는 함수:
    - 최근 history를 시스템 prompt에 추가하여 모델이 맥락을 이해하게 만듦
    - 새 답변은 history에 저장
    """

    rag_chain = initialize_rag_chain()

    # 최근 대화 기록을 prompt의 'question' 부분 앞에 붙임
    history_text = build_history_text(history)

    # 최종적으로 모델에게 전달할 question 형식
    full_question = f"""
(이전 대화 맥락)
{history_text}

(현재 질문)
{question}
"""

    # 답변 생성
    answer_text = rag_chain.invoke({
        "question": full_question,
        "grade": grade,
        "grade_rules": GRADE_RULES[grade]
    })

    # history 저장
    history.append({
        "question": question,
        "answer": answer_text
    })

    return answer_text


if __name__ == "__main__":
    history = []   # 멀티턴 대화 기록 저장

    while True:
        q = input("\n질문 입력(exit 종료): ")
        if q.lower() == "exit":
            break

        grade = input("난이도(초급/중급/고급): ").strip()

        # 멀티턴 적용된 답변 실행
        result = answer_with_history(q, grade, history)
        print("\n🧠 답변:\n", result)

        print("\n📜 현재 History 턴 수:", len(history))




# ==============================================================
# ★★★ 메인 실행 함수 ★★★
# ==============================================================

# if __name__ == "__main__":
#     print("\n=== 부트캠프 RAG 학습 도우미 챗봇 ===")
#     print("종료하려면 'exit' 입력\n")

#     rag = initialize_rag_chain()

#     while True:
#         question = input("\n📌 질문을 입력하세요: ")
#         if question.lower() == "exit":
#             print("\n👋 챗봇을 종료합니다.")
#             break

#         grade = input("💡 난이도 선택 (초급/중급/고급): ")
#         if grade.lower() == "exit":
#             print("\n👋 챗봇을 종료합니다.")
#             break

#         if grade not in GRADE_RULES:
#             print("❌ 난이도는 '초급', '중급', '고급' 중 하나여야 합니다.")
#             continue

#         print("\n⏳ 답변 생성 중...\n")

#         result = rag.invoke({
#             "question": question,
#             "grade": grade,
#             "grade_rules": GRADE_RULES[grade]
#         })

#         print("🧠 챗봇 답변:\n")
#         print(result)
#         print("\n---------------------------------------")



# ==============================================================

# # CSV 파일 경로
# CSV_PATH = r"C:\POTENUP\MumulMumul\notebooks\yojun\test_csv\rag_question_set.csv"

# if __name__ == "__main__":

#     # 1) CSV 파일 불러오기
#     df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

#     # 2) answer 컬럼 없으면 생성
#     if "answer" not in df.columns:
#         df["answer"] = ""

#     print("\n📌 CSV 예상 질문 자동 평가 시작\n")

#     save_interval = 5   # 5개마다 저장

#     # 3) 각 row 처리
#     for idx, row in df.iterrows():
#         question = str(row["question"]).strip()
#         grade = str(row["grade"]).strip()

#         # 비어 있으면 skip
#         if not question:
#             df.loc[idx, "answer"] = ""
#             continue

#         print(f"\n[{idx+1}] 질문: {question}")
#         print(f"📘 난이도: {grade}")

#         try:
#             result = answer(question, grade)
#         except Exception as e:
#             result = f"ERROR: {e}"

#         df.loc[idx, "answer"] = result
#         print("➡ 답변 저장 완료")

#         # ---- 5개마다 자동 저장 추가됨 ----
#         if (idx + 1) % save_interval == 0:
#             df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
#             print(f"💾 {idx+1}개 처리 완료 → 중간 저장됨")

#     # 4) 전체 처리 후 최종 저장
#     df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

#     print("\n🎉 모든 예상 질문 답변 생성 완료!")
#     print(f"📄 최종 파일 저장됨 → {CSV_PATH}")

# ==============================================================



# ==============================================================
# 예시 실행
# ==============================================================

# if __name__ == "__main__":
#     result = answer("리스트에 대해 설명해줘", grade="초급")
#     print(result)

# # 사용 예시
# answer("리스트 알려줘", grade="초급")