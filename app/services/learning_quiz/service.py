# app/services/learning_quiz/service.py

from app.services.learning_quiz.llm import generate_quiz
from app.services.learning_quiz.schemas import LearningQuizResponse, QuizItem
from app.services.learning_quiz.vectorstore import search_context
from app.services.learning_quiz.llm import check_learning_intent
from app.core.logger import setup_logger

logger = setup_logger(__name__)


def validate_grade(grade: str):
    valid_grades = ["초급", "중급", "고급"]
    if grade not in valid_grades:
        logger.error(f"[Invalid Grade] 입력된 grade 값: {grade}")
        raise ValueError("INVALID_GRADE")

def get_context(question: str) -> str:
    return search_context(question, k=3)

def create_quiz(question: str, grade: str) -> LearningQuizResponse:

    validate_grade(grade)

    # 학습 여부 판단
    if not check_learning_intent(question):
        logger.info("[LearningQuiz] 학습 관련 없는 질문으로 판정됨.")
        raise ValueError("NOT_LEARNING_RELATED")

    logger.info("[LearningQuiz] 학습 관련 질문으로 판정됨.")

    # ⭐ 실제 vectorstore 검색 적용됨
    context = search_context(question, k=5)

    logger.info(f"[LearningQuiz] Context 길이: {len(context)}")

    # context 기반 퀴즈 생성
    quiz_list = generate_quiz(context, question, grade)

    return LearningQuizResponse(
        isLearningQuestion=True,
        grade=grade,
        quiz=quiz_list.quiz
    )
