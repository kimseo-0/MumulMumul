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

def answer(question, grade):
    if grade not in GRADE_RULES:
        raise ValueError("grade는 '초급', '중급', '고급' 중 하나여야 합니다.")

    rag = initialize_rag_chain()

    return rag.invoke({
        "question": question,
        "grade": grade,
        "grade_rules": GRADE_RULES[grade]
    })

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

# #CSV 파일 경로
# CSV_PATH = r"C:\POTENUP\MumulMumul\storage\rag_question_set.csv"

# if __name__ == "__main__":
#     rag_chain = answer()

#     # 1) CSV 파일 불러오기
#     df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

#     # 2) answer 컬럼 없으면 만들기
#     if "answer" not in df.columns:
#         df["answer"] = ""

#     # 3) 각 질문 처리
#     for idx, row in df.iterrows():
#         question = str(row["질문"]).strip()
#         if not question:
#             df.loc[idx, "answer"] = ""
#             continue
        
#         print(f"\n[{idx+1}] 질문: {question}")
#         answer = rag_chain.invoke(question)
#         df.loc[idx, "answer"] = answer
#         print(f"➡ 답변 저장 완료")

#     # 4) CSV 다시 저장
#     df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
#     print("\n🎉 CSV 답변 생성 완료!")

# ==============================================================



# ==============================================================
# 예시 실행
# ==============================================================

if __name__ == "__main__":
    result = answer("리스트에 대해 설명해줘", grade="초급")
    print(result)

# 사용 예시
answer("리스트 알려줘", grade="초급")