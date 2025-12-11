# app/services/learning_quiz/llm.py

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.services.learning_quiz.schemas import QuizList
from app.services.learning_quiz.prompt import QUIZ_GENERATION_PROMPT
from app.core.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)

# 1) Parser (QuizList JSON 구조 강제)
quiz_parser = PydanticOutputParser(pydantic_object=QuizList)

# 2) Prompt (STEP 3에서 만든 Prompt 사용)
prompt = ChatPromptTemplate.from_template(QUIZ_GENERATION_PROMPT)

# 3) LLM 생성
llm = ChatOpenAI(
    model="gpt-4.1-mini",  # JSON 안정성 ↑
    temperature=0.1
)

# 4) Prompt + LLM + Parser 를 Chain으로 합치기
quiz_chain = prompt | llm | quiz_parser


# 5) 외부에서 실행하는 함수 (service에서 불러씀)
def generate_quiz(context: str, question: str, grade: str) -> QuizList:
    """
    실제로 퀴즈 5개를 생성하는 함수.
    vectorstore 검색 결과(context), 사용자 질문(question), 난이도(grade)를 조합하여
    JSON 구조의 퀴즈 리스트를 반환한다.
    """

    logger.info("[Quiz Generation] LLM 호출 시작")

    # parser가 사용할 format_instructions 가져오기
    format_instructions = quiz_parser.get_format_instructions()

    try:
        result = quiz_chain.invoke({
            "context": context,
            "question": question,
            "grade": grade,
            "format_instructions": format_instructions
        })

        logger.info("[Quiz Generation] 성공적으로 JSON 파싱 완료")
        return result

    except Exception as e:
        logger.error(f"[Quiz Generation Error] {e}")
        raise e
