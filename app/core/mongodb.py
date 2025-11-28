# app/core/mongodb.py

from datetime import datetime
from typing import Literal, Optional, List, Tuple, Type, Dict, Any

from pydantic import BaseModel
from pymongo import MongoClient
from app.config import MONGO_URL, MONGO_DB_NAME


# =====================================
# 1. MongoDB 연결
# =====================================
mongo_client = MongoClient(MONGO_URL)
mongo_db = mongo_client[MONGO_DB_NAME]

def get_mongo_db() -> MongoClient:
    """
    MongoDB 데이터베이스 인스턴스 반환
    """
    return mongo_db


# =====================================
# 2. MongoDB 모델 레지스트리 및 초기화
# =====================================
class MongoModelSpec(BaseModel):
    model: Type[BaseModel]
    collection_name: str
    indexes: List[Tuple[str, int]]  # [("field", 1), ("created_at", -1)] 이런식


MONGO_MODELS: List[MongoModelSpec] = []


def register_mongo_model(
    model: Type[BaseModel],
    collection_name: str,
    indexes: List[Tuple[str, int]],
):
    """
    새로운 Mongo 문서 모델을 등록하는 함수.
    - 모델 클래스(BaseModel)
    - 사용할 컬렉션 이름
    - 만들고 싶은 인덱스 리스트
    """
    spec = MongoModelSpec(
        model=model,
        collection_name=collection_name,
        indexes=indexes,
    )
    MONGO_MODELS.append(spec)


def init_mongo(db):
    """
    서버 시작 시 한 번만 호출해서
    - 각 컬렉션에 대해 필요한 인덱스를 생성함.
    """
    for spec in MONGO_MODELS:
        coll = db[spec.collection_name]
        for field, order in spec.indexes:
            coll.create_index([(field, order)])

    print(f"[MongoDB] Initialized {len(MONGO_MODELS)} collections/indexes.")


# =====================================
# 3. 도메인 모델 정의
# =====================================

class LearningChatLog(BaseModel):
    """
    학습 챗봇과의 채팅 로그

    - user_id: SQL(User.user_id)와 연결
    - session_id: 세션 식별자 (옵션)
    - camp_id: SQL(Camp.camp_id)와 연결 (옵션)
    - role: 'user' or 'assistant'
    - content: 실제 채팅 내용
    - curriculum_scope: 커리큘럼 내/외 ("in" / "out")
    - question_category: numpy / pandas / portfolio 등 분류 태그
    - created_at: 생성 시각
    """
    user_id: int
    session_id: Optional[int] = None
    camp_id: Optional[int] = None

    role: Literal["user", "assistant"]
    content: str

    curriculum_scope: Optional[Literal["in", "out"]] = None
    question_category: Optional[str] = None

    created_at: datetime = datetime.utcnow()


# 이 모델을 Mongo 레지스트리에 등록
register_mongo_model(
    LearningChatLog,
    collection_name="learning_chat_logs",
    indexes=[
        ("user_id", 1),
        ("camp_id", 1),
        ("question_category", 1),
        ("curriculum_scope", 1),
        ("created_at", -1),
    ],
)
