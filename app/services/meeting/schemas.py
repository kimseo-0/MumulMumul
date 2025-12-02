from pydantic import BaseModel

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