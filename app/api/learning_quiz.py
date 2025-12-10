from typing import List, Dict
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class LearningQuizRequest(BaseModel):
    question: str
    grade: str

class QuizInfo(BaseModel):
    id: int
    type: str
    question: str
    answer: str
    explanation: str

class LearningQuizResponse(BaseModel):
    isLearningQuestion: bool
    grade: str
    quiz: List[QuizInfo]




@router.post("/generate", response_model=LearningQuizResponse)
def create_learning_quiz(payload: LearningQuizRequest):
    question = payload.question
    grade = payload.grade
    
    return {
  "isLearningQuestion": True,
  "grade": "초급",
  "quiz": [
    {
      "id": 1,
      "type": "OX",
      "question": "Pandas에서 DataFrame을 행 기준으로 합칠 때 merge() 함수를 사용한다. (O/X)",
      "answer": "X",
      "explanation": "merge()는 공통 컬럼을 기준으로 결합하고, 행 기준 단순 결합은 concat()을 사용한다."
    },
    {
      "id": 2,
      "type": "OX",
      "question": "concat() 함수는 여러 DataFrame을 세로 방향으로 이어붙일 수 있다. (O/X)",
      "answer": "O",
      "explanation": "concat(df1, df2)은 index를 유지하며 세로 방향 결합을 수행한다."
    },
    {
      "id": 3,
      "type": "OX",
      "question": "join()은 인덱스를 기준으로 두 DataFrame을 결합한다. (O/X)",
      "answer": "O",
      "explanation": "기본적으로 join은 인덱스를 기준으로 결합한다."
    },
    {
      "id": 4,
      "type": "OX",
      "question": "merge()는 SQL의 JOIN과 유사하게 동작한다. (O/X)",
      "answer": "O",
      "explanation": "on 키를 지정하는 방식은 SQL JOIN과 동일하다."
    },
    {
      "id": 5,
      "type": "OX",
      "question": "concat()은 열(column) 기준 결합을 지원하지 않는다. (O/X)",
      "answer": "X",
      "explanation": "axis=1 옵션을 주면 열 기준 결합도 가능하다."
    }
  ]
}


