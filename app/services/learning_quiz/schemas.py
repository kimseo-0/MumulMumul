# app/services/learning_quiz/schemas.py

from pydantic import BaseModel
from typing import List

class QuizInfo(BaseModel):
    id: int
    type: str
    question: str
    answer: str
    explanation: str


class QuizList(BaseModel):
    quiz: List[QuizInfo]