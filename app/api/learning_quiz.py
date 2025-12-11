from typing import List, Dict
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.learning_quiz.schemas import QuizInfo
from app.services.learning_quiz.service import test_make_quiz

router = APIRouter()

class LearningQuizRequest(BaseModel):
    question: str
    grade: str

class LearningQuizResponse(BaseModel):
    isLearningQuestion: bool
    grade: str
    quiz: List[QuizInfo]


@router.post("/generate", response_model=LearningQuizResponse)
def create_learning_quiz(payload: LearningQuizRequest):
 

  result = test_make_quiz(question = payload.question, grade = payload.grade) # {"quiz": List[QuizInfo]}
  return {
     "isLearningQuestion": True,
     "grade": payload.grade,
     "quiz": result.quiz

  }
  



