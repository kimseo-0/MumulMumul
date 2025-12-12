# app/api/learning_quiz.py

from typing import Union
from fastapi import APIRouter, HTTPException
from app.services.learning_quiz.service import create_quiz
from app.services.learning_quiz.schemas import LearningQuizRequest, LearningQuizResponse, LearningQuizErrorResponse
from app.core.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.post(
    "/generate",
    response_model=Union[LearningQuizResponse, LearningQuizErrorResponse],
    responses={400: {"description": "학습 무관 또는 잘못된 요청"}}
)
def create_learning_quiz(payload: LearningQuizRequest):
    """
    학습 퀴즈 생성 API
    - 학습 관련 여부 판단
    - vectorstore 검색
    - OX 퀴즈 5개 생성
    """

    question = "Pandas와 DataFrame에 대한 문제를 만들어줘" # TODO : 김서영이 만든 커리큘럼 리포트 기반 학습 퀴즈 제작 질문 함수로 교체 예정
    grade = payload.grade

    try:
        result = create_quiz(question, grade)
        return result

    except ValueError as e:

        # 1️⃣ grade 잘못된 경우
        if str(e) == "INVALID_GRADE":
            raise HTTPException(
                status_code=400,
                detail={
                    "errorCode": "INVALID_REQUEST",
                    "message": "grade 값은 초급/중급/고급 중 하나여야 합니다."
                }
            )

        # 2️⃣ 학습 무관 질문일 경우
        elif str(e) == "NOT_LEARNING_RELATED":
            return {
                "isLearningQuestion": False,
                "detail": {
                    "errorCode": "NOT_LEARNING_RELATED",
                    "message": "학습 퀴즈와 관련 없는 질문입니다. 학습 관련 질문을 입력해주세요."
                }
            }

        # 3️⃣ 나머지는 서버 오류
        else:
            raise HTTPException(status_code=500, detail="Internal Server Error")


