# ==============================================================
# chatbot_rag_final.py
# 설명 모드 + 학습퀴즈 모드 자동 분기 (LLM 기반 의도 판단)
# 캐시 + 메타데이터 포맷 + 멀티턴 히스토리
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

# 벡터DB(Chroma)가 저장된 폴더 경로
DB_PATH = r"C:\POTENUP\MumulMumul\storage\vectorstore\curriculum_all_new"
COLLECTION = "curriculum_all_new"

LLM_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-large"

# 기본 검색 개수 설정(질문 내용에 따라 자동으로 조정됨)
SEARCH_K = 3
FETCH_K = 8

RAG_CHAIN = None   # 실제로 답변을 만드는 체인(파이프라인)
RETRIEVER = None   # 벡터DB에서 문서를 찾아오는 친구


# ==============================================================
# 캐시 (이미 했던 질문/답을 기억해두기)
# ==============================================================

# "semantic" 이라는 말이 어려울 수 있어서 쉽게 설명:
# - 우리가 문장을 숫자로 바꿔서(벡터) "뜻이 비슷한 문장"을 찾는 방식을
#   보통 "의미 기반 검색(semantic search)" 라고 부름.
# - 여기서는 "비슷한 질문"을 찾기 위해 사용함.

embedder_for_cache = OpenAIEmbeddings(model=EMBEDDING_MODEL)

# 난이도별로 캐시를 따로 관리
# - exact: 질문 문장이 완전히 똑같을 때
# - semantic: 질문 문장은 다르지만 '뜻'이 비슷할 때
CACHE = {
    "초급": {"exact": {}, "semantic": []},
    "중급": {"exact": {}, "semantic": []},
    "고급": {"exact": {}, "semantic": []},
}


def cosine_similarity(a, b):
    """두 벡터(숫자 리스트)가 얼마나 비슷한지 0~1 사이 점수로 계산"""
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def is_quiz_like_question(q: str) -> bool:
    """
    이 질문이 '문제/퀴즈를 내달라'에 가까운지 간단히 판별.
    - 여기서는 캐시(특히 '비슷한 질문 찾기')를 막기 위한 용도로만 사용.
    - 모드(설명/퀴즈) 구분은 LLM이 따로 한다.
    """
    q2 = q.replace(" ", "")
    keywords = ["퀴즈", "문제", "테스트", "연습문제", "ox", "OX"]
    return any(k in q2 for k in keywords)


def search_cache(question: str, grade: str):
    """
    캐시에서 먼저 답을 찾아보는 함수.
    1) 질문이 완전히 같으면(exact) → 바로 반환
    2) 퀴즈/문제 요청이면 → '비슷한 질문' 재사용은 위험해서 건너뜀
    3) 설명 요청이면 → '뜻이 비슷한 질문'도 찾아보고 충분히 비슷하면 재사용
    """
    # 1) 완전히 같은 질문인 경우 (문장 그대로 일치)
    if question in CACHE[grade]["exact"]:
        print("[CACHE HIT] Exact")
        return CACHE[grade]["exact"][question]

    # 2) 퀴즈/문제 요청이면, '비슷한 질문' 캐시는 사용하지 않음
    #    예: "for문 문제 5개" vs "for문 문제 3개" → 섞이면 안 됨
    if is_quiz_like_question(question):
        print("[CACHE SKIP] 퀴즈 요청 → semantic 캐시 사용 안 함")
        return None

    # 3) 설명 요청인 경우에만 '뜻이 비슷한 질문'을 찾아본다.
    print("[CACHE CHECK] Semantic...")
    q_vec = embedder_for_cache.embed_query(question)

    best_score = 0
    best_answer = None

    for entry in CACHE[grade]["semantic"]:
        score = cosine_similarity(q_vec, entry["vector"])
        if score > best_score:
            best_score = score
            best_answer = entry["answer"]

    # 0.8 이상이면 "꽤 비슷하다"라고 보고 재사용
    if best_score >= 0.80:
        print(f"[CACHE HIT] Semantic score={best_score:.3f}")
        return best_answer

    return None


def save_to_cache(question: str, grade: str, answer: str):
    """새로 만든 답변을 캐시에 저장"""
    vec = embedder_for_cache.embed_query(question)

    # 1) 완전히 같은 질문용 캐시
    CACHE[grade]["exact"][question] = answer

    # 2) '뜻이 비슷한 질문' 검색용 캐시
    CACHE[grade]["semantic"].append({
        "question": question,
        "vector": vec,
        "answer": answer
    })

    print("[CACHE SAVE] 완료")


# ==============================================================
# 설명 모드 템플릿
# ==============================================================

GRADE_RULES = {
    "초급": """
[질문 이해]
- 사용자가 무엇을 궁금해하는지 쉬운 말로 한 줄 정리.

[핵심 요약]
- 초보자도 바로 이해할 수 있도록 한 문장으로 요약.

[쉬운 설명]
- 어려운 용어 최소화. 즉시 풀이 포함.
- 2~4줄로 설명.

[비유 + 예시 코드]
- 현실 비유 1~2개.
- 코드 예시는 3~7줄, 반드시 ```python 코드블록```으로 작성.

[추가 설명]
- 1~2줄.

[연습 문제]
- 1~2개, 힌트 포함. 반드시 context 안의 내용 기반.

[출처]
- 사용한 내용의 파일명 + 페이지 번호.
""",

    "중급": """
[핵심 개념 요약]
- 개념을 한 문장으로 정리.

[정확한 정의]
- context 기반으로 2~4줄.

[왜 필요한가]
- 실무/학습 관점으로 1~2줄.

[주의 포인트]
- 헷갈리기 쉬운 부분 1~3개 bullet.

[예시 코드]
- 3~8줄, 반드시 ```python 코드블록``` 사용.

[출처]
- 파일명 + 페이지 번호.
""",

    "고급": """
[핵심 요약]
- 개념의 본질을 한 문장으로 요약.

[동작 원리]
- 내부 구조/메커니즘 중심 설명.

[성능/메모리]
- context 기반으로 설명.

[비교]
- 유사 기술과의 비교 1~3개.

[사례]
- 3~8줄의 고급 예시 코드(코드블록).

[출처]
- 파일명 + 페이지 번호.
"""
}


# ==============================================================
# 학습퀴즈 생성 모드 템플릿
# ==============================================================

QUIZ_RULES_TEMPLATE = """
[모드]
- 이 요청은 '학습퀴즈 생성'입니다.
- 반드시 JSON만 출력하세요.
- 정답은 context(강의자료)에 근거해야 하지만,
  학습 효과를 높이기 위한 범위 내에서 약간의 일반 파이썬 지식 확장은 허용합니다.

[허용 문제 형식]
1) OX 문제
2) 객관식 문제(보기 5개)

[문제 개수 규칙]
- 사용자가 문제 개수를 직접 요청했다면, 요청한 개수만 생성합니다.
- 사용자가 문제 개수를 말하지 않았다면, 기본적으로 5문제를 생성합니다.

[문제 유형 기본 규칙]
- 사용자가 문제 유형을 특별히 말하지 않았다면, 기본적으로 객관식(multiple) 문제 위주로 생성합니다.
- 필요한 경우 OX 문제를 섞어도 되지만, 난이도와 학습 효과를 고려해서 적절히 선택합니다.

[코드가 들어가는 문제 규칙]
- 코드가 포함된 문제는 반드시 코드블록( ```python ... ``` ) 형태로 출력해야 합니다.
- 코드블록 내부는 들여쓰기와 줄바꿈을 정확하게 유지해야 합니다.

[JSON 스키마]
{
  "total": 문제수,
  "items": [
    {
      "number": 1,
      "type": "ox" 또는 "multiple",
      "question": "문제 내용 (필요시 코드블록 포함)",
      "choices": ["보기1","보기2","보기3","보기4","보기5"] 또는 null,
      "answer": "정답(또는 정답 보기 내용)",
      "difficulty": "{GRADE_LEVEL}",
      "source_file": "파일명",
      "source_page": 페이지번호
    }
  ]
}

[문제 생성 규칙]
- context 안의 내용을 우선적으로 기반으로 문제를 출제합니다.
- 단, 수강생 학습을 돕는 범위 내에서는 약간의 확장도 허용합니다.
- 객관식 보기는 반드시 5개여야 합니다.
- 객관식 문제의 정답은 반드시 보기 안에 포함되어야 합니다.
- 문제는 수강생이 핵심 개념을 이해했는지 확인할 수 있도록 구성합니다.

[출력 규칙]
- JSON만 출력합니다. (설명, 해설, 자연어 문장 절대 금지)
"""


# ==============================================================
# 질문 의도(설명/퀴즈) LLM으로 판단
# ==============================================================

INTENT_PROMPT = """
당신은 질문의 의도를 분석하는 분류 AI입니다.

사용자의 질문이 아래 둘 중 무엇에 해당하는지 판단하세요.

1) "설명" → 개념 설명, 이해를 돕는 답변을 원하는 경우
2) "퀴즈" → 학습을 위한 문제(퀴즈)를 만들어달라는 경우

출력 형식:
- 아래 둘 중 하나의 단어만 출력하세요.
  - 설명
  - 퀴즈
"""


def detect_intent(question: str, llm: ChatOpenAI) -> str:
    """LLM에게 '설명' 또는 '퀴즈' 중 하나로 분류해 달라고 요청"""
    prompt = INTENT_PROMPT + f"\n\n[질문]\n{question}\n"
    result = llm.invoke(prompt)   # AIMessage 객체 반환
    text = result.content.strip()

    # 혹시라도 이상한 답이 나오면 기본값은 "설명"
    if "퀴즈" in text:
        return "퀴즈"
    return "설명"


def build_rules(question: str, grade: str, llm_for_intent: ChatOpenAI) -> str:
    """
    질문을 보고 '설명 모드'로 갈지, '퀴즈 모드'로 갈지 선택한 뒤
    그에 맞는 규칙 텍스트를 돌려주는 함수.
    """
    intent = detect_intent(question, llm_for_intent)  # "설명" 또는 "퀴즈"

    if intent == "퀴즈":
        print("[MODE] 학습퀴즈 모드 (LLM 판단)")
        return QUIZ_RULES_TEMPLATE.replace("{GRADE_LEVEL}", grade)

    print("[MODE] 설명 모드 (LLM 판단)")
    return GRADE_RULES[grade]


# ==============================================================
# metadata → 텍스트로 포맷팅
# ==============================================================

def format_docs_with_metadata(docs):
    """
    벡터DB에서 가져온 문서 리스트(docs)를
    - [1] 출처: 파일명 / p.페이지
    - 본문 내용
    이런 형태의 큰 문자열로 합치는 함수.
    """
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
        if page is not None:
            header += f" / p.{page}"

        body = doc.page_content or ""

        parts.append(f"{header}\n{body}")

    return "\n\n".join(parts)


# ==============================================================
# 질문 복잡도에 따라 검색량 조절
# ==============================================================

def estimate_topic_count(question: str) -> int:
    """
    질문 안에 '그리고, /, 와, 과' 같은 연결어가 몇 개 있는지 대략 세어서
    - 한 가지 주제인지
    - 두세 가지를 한 번에 물어보는지
    를 아주 단순하게 추정.
    """
    joiners = ["와 ", "과 ", "이랑", "랑", " 및 ", " 그리고 ", ",", "/"]
    score = 1
    for j in joiners:
        if j in question:
            score += 1
    return max(1, min(score, 3))  # 1~3 사이로 제한


def adjust_retriever_for_question(question: str):
    """
    질문이 여러 주제를 섞어서 물어보는 것 같으면
    한 번에 가져오는 문서 수(k, fetch_k)를 늘려주는 함수.
    """
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
    """
    - 임베딩 모델 준비
    - Chroma 벡터DB 연결
    - Retriever 생성
    - 프롬프트 템플릿 + LLM 연결
    - 전체 파이프라인(chain) 구성
    """
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

[역할]
- 설명 모드일 때: 반드시 [Context] 안의 내용만 사용해서 답변해야 합니다.
- 퀴즈 모드일 때: 문제는 context를 기반으로 만들고,
  필요하다면 학습 효과를 위해 가볍게 확장할 수 있지만,
  정답은 context 안에서 근거를 찾을 수 있어야 합니다.

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
        # docs를 받아서 context 문자열로 합치는 단계
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
    """RAG 체인이 없으면 새로 만들고, 있으면 재사용"""
    global RAG_CHAIN
    if RAG_CHAIN is None:
        RAG_CHAIN = initialize_rag_chain()
    return RAG_CHAIN


# ==============================================================
# HISTORY (멀티턴)
# ==============================================================

def build_history_text(history, max_turns=2):
    """
    이전 대화 내용 리스트(history)를
    "학생: ... / AI: ..." 형식의 문자열로 합치는 함수.
    너무 길어지지 않게 최근 max_turns번만 사용.
    """
    if not history:
        return ""
    recent = history[-max_turns:]
    return "\n".join(
        [f"학생: {h['question']}\nAI: {h['answer']}" for h in recent]
    )


# ==============================================================
# 메인 답변 함수
# ==============================================================

def answer_single(question: str, grade: str, history: list):
    """
    실제로 1개의 질문에 대해 1개의 답변을 만들어주는 함수.
    - 캐시 확인
    - 검색량 조정
    - 설명/퀴즈 모드 판단
    - RAG 체인 호출
    - 캐시에 저장 + history 업데이트
    """

    # 1) 캐시 확인
    cached = search_cache(question, grade)
    if cached:
        print("[INFO] 캐시 사용")
        history.append({"question": question, "answer": cached})
        return cached

    # 2) 검색량 조정
    adjust_retriever_for_question(question)

    # 3) LLM에게 '설명/퀴즈' 의도 판단 맡기기
    llm_for_intent = ChatOpenAI(model=LLM_MODEL, temperature=0.0)
    rules_text = build_rules(question, grade, llm_for_intent)

    # 4) RAG 체인 준비
    rag = get_rag_chain()
    history_text = build_history_text(history)

    # 5) 실제 답변 생성
    start = time.time()
    answer = rag.invoke({
        "question": question,
        "grade": grade,
        "rules": rules_text,
        "history": history_text
    })
    print(f"[Time] 답변 생성: {time.time() - start:.3f}s")

    # 6) 캐시에 저장 + history 업데이트
    save_to_cache(question, grade, answer)
    history.append({"question": question, "answer": answer})

    return answer


# ==============================================================
# CLI 실행부 (터미널에서 테스트용)
# ==============================================================

if __name__ == "__main__":
    print("\n=== RAG 학습 도우미 챗봇 (설명 + 학습퀴즈 자동 분기) ===\n")
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
