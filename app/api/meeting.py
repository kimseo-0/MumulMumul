from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.logger import setup_logger
from app.core.db import get_db
from app.services.meeting.schemas import AudioChunkUploadResponse
from app.services.meeting.audio_processor import AudioProcessor
from app.services.meeting.paths import PathManager
import io

logger = setup_logger(__name__)
router = APIRouter()

audio_processor = AudioProcessor()

# 음성 청크 업로드 및 로컬 저장
@router.post("/{meeting_id}/audio_chunk", response_model=AudioChunkUploadResponse)
async def upload_audio_chunk(
    meeting_id: str,
    audio_file: UploadFile = File(...),
    user_id: int = Form(...),
    chunk_index: int = Form(...),
    db: Session = Depends(get_db)
):
    # 파일 이름과 content-type 확인
    logger.info(f"Received file: {audio_file.filename}")
    logger.info(f"Content type: {audio_file.content_type}")

    try:
        logger.info(
            f"Audio chunk upload:\n"
            f"   Meeting: {meeting_id}\n"
            f"   User: {user_id}\n"
            f"   Chunk: {chunk_index}"
        )
        
        # 1. 파일 읽기
        file_data = await audio_file.read()
        file_size_mb = len(file_data) / (1024 * 1024)
        
        logger.info(f"   File size: {file_size_mb:.2f} MB")
        
        # 2. 파일 검증
        validation = AudioProcessor.validate_audio_file(file_data)
        
        if not validation["is_valid"]:
            logger.error(f"Invalid audio format: {validation.get('error')}")
            raise HTTPException(status_code=400, detail="Invalid audio format")
        
        # 3. 파일 저장 (로컬)
        chunk_path = AudioProcessor.save_chunk_file(
            meeting_id,
            user_id,
            chunk_index,
            file_data
        )
        
        # 4. 응답
        return AudioChunkUploadResponse(
            meeting_id=meeting_id,
            user_id=user_id,
            chunk_index=chunk_index
        )
    
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
