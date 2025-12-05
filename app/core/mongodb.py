# app/core/mongodb.py

from datetime import datetime
from typing import Literal, Optional, List, Tuple, Type, Dict, Any

from pydantic import BaseModel, Field
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

# =====================================
# 3-1. Learning Chat Log 모델 정의
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

# =====================================
# 3-2. Team Chat Message 모델 정의
# =====================================
class TeamChatMessage(BaseModel):
    """
    팀 채팅방 메시지 로그

    - room_id: 채팅방 ID (SQL ChatRoom.id 와 연결)
    - user_id: SQL(User.user_id)와 연결
    - user_name: 메시지 보낸 유저 이름 (조회 편의용, 캐시 개념)
    - message: 실제 채팅 내용
    - created_at: 메시지 생성 시각
    """
    room_id: str
    user_id: int
    user_name: str
    message: str
    created_at: datetime = datetime.utcnow()


# TeamChatMessage 모델을 Mongo 레지스트리에 등록
register_mongo_model(
    TeamChatMessage,
    collection_name="team_chat_messages",
    indexes=[
        ("room_id", 1),
        ("user_id", 1),
        ("created_at", -1),
    ],
)

# =====================================
# 3-3. Meeting Transcript 모델 정의
# =====================================
class MeetingSegment(BaseModel):
    """회의 세그먼트"""
    segment_id: str
    user_id: int
    speaker_name: str
    text: str
    start_time_ms: int  # 상대 시간
    end_time_ms: int
    absolute_start_ms: int  # 절대 시간
    absolute_end_ms: int
    confidence: float
    timestamp_display: str  # "[00:05]"


class OverlapInfo(BaseModel):
    """겹침 구간 정보"""
    segment1_id: str
    segment2_id: str
    speaker1: str
    speaker2: str
    overlap_duration_ms: int
    overlap_start_ms: int
    overlap_end_ms: int


class MeetingTranscript(BaseModel):
    """회의 전체 전사본"""
    meeting_id: str
    title: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: int
    participant_count: int
    organizer_id: int
    
    # 전체 텍스트 (타임스탬프 + 화자 포함)
    full_text: str
    
    # 세그먼트 리스트 (시간순 정렬됨)
    segments: List[MeetingSegment]
    
    # 겹침 정보
    overlaps: List[OverlapInfo] = []
    
    # 통계
    total_segments: int
    speakers: List[Dict[str, Any]]
    
    # 메타데이터
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# MeetingTranscript 모델 등록
register_mongo_model(
    MeetingTranscript,
    collection_name="meeting_transcripts",
    indexes=[
        ("meeting_id", 1),
        ("organizer_id", 1),
        ("created_at", -1),
    ],
)


# =====================================
# 3-4. Meeting Summary 모델 정의
# =====================================
class MeetingSummary(BaseModel):
    """회의 요약본"""
    meeting_id: str
    summary_text: str
    key_points: List[str] = []
    action_items: List[str] = []
    next_agenda: List[str] = []
    decisions: List[str] = []
    
    # 메타데이터
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_used: str = "gpt-4o-mini"


# MeetingSummary 모델 등록
register_mongo_model(
    MeetingSummary,
    collection_name="meeting_summaries",
    indexes=[
        ("meeting_id", 1),
        ("generated_at", -1),
    ],
)