from pydantic import BaseModel
from typing import Optional

class AudioChunkUploadResponse(BaseModel):
    """음성 청크 업로드 응답"""
    meeting_id: str
    user_id: int
    chunk_index: int
    status: str = "received"

class STTResult(BaseModel):
    """STT 처리 결과"""
    chunk_index: int
    user_id: int
    text: str
    confidence: float
    start_time_ms: int
    end_time_ms: int

class Segment(BaseModel):
    """세그먼트"""
    segment_id: str
    user_id: int
    speaker_name: str
    start_time_ms: int
    end_time_ms: int
    text: str
    confidence: float

class StartMeetingRequest(BaseModel):
    """회의 시작 요청"""
    title: str
    chat_room_id: str
    organizer_id: int
    client_timestamp: int  # 클라이언트의 현재 시간 (epoch ms)
    agenda: Optional[str] = None
    description: Optional[str] = None

class StartMeetingResponse(BaseModel):
    """회의 시작 응답"""
    meeting_id: str
    # title: str
    # organizer_id: int
    # start_time: str
    # start_client_timestamp: int
    # start_server_timestamp: int
    # time_offset: int
    status: str

class JoinMeetingRequest(BaseModel):
    """회의 참가 요청"""
    user_id: int
    client_timestamp: int  # 참가 시점의 클라이언트 시간

class JoinMeetingResponse(BaseModel):
    """회의 참가 응답"""
    participant_id: int
    meeting_id: str
    user_id: int
    # join_time: int
    # role: str

class EndMeetingResponse(BaseModel):
    """회의 종료 응답"""
    meeting_id: str
    status: str
    duration_ms: int
    participant_count: int
    total_segments: int
    # waited_for_processing: bool = False
    # wait_time_ms: int = 0