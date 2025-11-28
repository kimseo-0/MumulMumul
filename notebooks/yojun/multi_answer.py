from operator import itemgetter
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

DB_PATH = r"C:\POTENUP\MumulMumul\storage\vectorstore\curriculum_all_new"
COLLECTION = "curriculum_all_new"

LLM_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-large"

SEARCH_K = 5
FETCH_K = 20


# -----------------------------------
#  학습 수준별 템플릿
# -----------------------------------
GRADE_RULES = {
    "초급": """
당신은 프로그래밍/데이터를 처음 배우는 초급자를 돕는 학습 도우미입니다.
답변은 반드시 아래 6단계 형식을 따라야 합니다.

1) [질문 이해]
- 사용자가 알고 싶어하는 내용을 한 줄로 다시 정리합니다.

2) [핵심 한 줄 요약]
- 초보자가 단번에 이해할 수 있도록 결론을 한 문장으로 요약합니다.

3) [쉬운 설명]
- 어려운 용어, 영어, 축약어는 가능한 사용하지 않습니다.
- 꼭 사용해야 한다면 괄호로 쉬운 뜻을 적습니다.

4) [비유 / 예시]
- 현실 비유 1개 이상
- 간단한 예시 코드 1개

5) [추가로 알면 좋은 것]
- 1~2줄만 확장 설명 (너무 깊은 내용 금지)

6) [출처]
- 파일명.pdf / p.숫자 형식으로 정확히 명시

주의:
- 문장은 짧게, 쉽게.
- context에 없는 내용은 생성하지 않기.
""",

    "중급": """
- 개념의 핵심 정의 제공
- 필요 시 용어 사용 가능
- 왜 필요한 개념인지 설명
- 실무에서 자주 헷갈리는 개념 포함
- 예시 코드 포함 가능
- 출처 포함
""",

    "고급": """
- 내부 동작 원리 중심 설명
- 구조, 메커니즘, 성능 등 심화 개념 포함
- 수식·전문용어 사용 가능
- 다른 기술 비교 가능
- 출처 포함
"""
}


# -----------------------------------
#  RAG 초기화
# -----------------------------------
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

    template = """
당신은 부트캠프 학습 자료 기반으로 답변하는 학습 도우미입니다.

[중요 지침]
- 답변은 반드시 제공된 Context에서만 가져와야 합니다.
- Context에 없는 내용은 절대 지어내지 마세요.
- 학생 수준(초급/중급/고급)에 맞게 설명하세요.
- 출처(파일명 + 페이지)를 반드시 포함하세요.

[학생 수준]
{grade}

[답변 규칙]
{grade_rules}

-------------------------------------
[Context]
{context}

[Question]
{question}
-------------------------------------
위 형식을 따라 답변하세요.
"""

    prompt = ChatPromptTemplate.from_template(template)
    model = ChatOpenAI(model=LLM_MODEL, temperature=0.2)

    rag_chain = (
        {
            "context": itemgetter("question") | retriever,
            "question": itemgetter("question"),
            "grade": itemgetter("grade"),
            "grade_rules": itemgetter("grade_rules"),
        }
        | prompt
        | model
        | StrOutputParser()
    )

    return rag_chain


# -----------------------------------
#  단일 질문 답변
# -----------------------------------
def answer(question, grade, rag_chain=None):
    if grade not in GRADE_RULES:
        raise ValueError("grade는 '초급', '중급', '고급' 중 하나여야 합니다.")

    if rag_chain is None:
        rag_chain = initialize_rag_chain()

    return rag_chain.invoke({
        "question": question,
        "grade": grade,
        "grade_rules": GRADE_RULES[grade]
    })


# -----------------------------------
#  여러 질문 자동 분리
# -----------------------------------
def split_questions(user_message: str) -> list[str]:
    splitter = ChatOpenAI(model=LLM_MODEL, temperature=0)

    split_prompt = ChatPromptTemplate.from_template(
        """
사용자의 입력에서 '서로 다른 질문'을 의미 단위별로 분리하세요.

출력 형식:
1. 질문1
2. 질문2
3. 질문3

사용자 입력:
{message}
"""
    )

    chain = split_prompt | splitter | StrOutputParser()
    raw = chain.invoke({"message": user_message})

    questions = []
    for line in raw.splitlines():
        line = line.strip()
        if line and line[0].isdigit() and "." in line:
            _, q = line.split(".", 1)
            if q.strip():
                questions.append(q.strip())

    if not questions:
        return [user_message.strip()]

    return questions


# -----------------------------------
#  여러 질문 → 질문별 RAG 호출 → 통합 출력
# -----------------------------------
def multi_answer(user_message: str, grade: str):
    questions = split_questions(user_message)

    rag_chain = initialize_rag_chain()

    results = []

    for idx, q in enumerate(questions, start=1):
        try:
            ans = answer(q, grade, rag_chain=rag_chain)
        except Exception as e:
            ans = f"ERROR: {e}"

        block = f"""
### 질문 {idx}
> {q}

{ans}

-------------------------------------
"""
        results.append(block)

    return "\n".join(results)


# -----------------------------------
#  MAIN 루프 (단일 vs 복수 자동 감지)
# -----------------------------------
if __name__ == "__main__":
    print("\n=== 부트캠프 RAG 학습 도우미 (멀티 질문 완전 지원) ===")
    print("종료하려면 'exit' 입력\n")

    while True:
        user_msg = input("\n📌 질문 입력: ")
        if user_msg.lower().strip() == "exit":
            break

        grade = input("💡 난이도 선택 (초급/중급/고급): ").strip()
        if grade.lower().strip() == "exit":
            break

        print("\n⏳ 답변 생성 중...\n")

        # 질문 자동 분리
        qs = split_questions(user_msg)

        # 1개면 → 단일 answer()
        if len(qs) <= 1:
            result = answer(user_msg, grade)
        else:
            # 여러 개면 → multi_answer()
            result = multi_answer(user_msg, grade)

        print("🧠 학습 도우미 답변:\n")
        print(result)
        print("\n============================================")
