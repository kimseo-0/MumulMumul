from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
from app.core.logger import setup_logger
from app.core.db import get_db
from app.services.meeting.schemas import AudioChunkUploadResponse
from app.services.meeting.audio_processor import AudioProcessor
from app.services.meeting.paths import PathManager
from app.core.schemas import User, Meeting, STTSegment
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
    background_tasks: BackgroundTasks = BackgroundTasks(),
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
        
        meeting = db.query(Meeting).filter(
            Meeting.meeting_id == meeting_id
        ).first()
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if meeting.status != "in_progress":
            raise HTTPException(status_code=409, detail="Meeting not in progress")
        
        user = db.query(User).filter(User.user_id == user_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # 3. 파일 저장 (로컬)
        chunk_path = AudioProcessor.save_chunk_file(
            meeting_id,
            user_id,
            chunk_index,
            file_data
        )

        # ===== 이전 청크 경로 구성 (겹침 처리용) =====
        chunk_dir = PathManager.get_user_chunk_dir(meeting_id, str(user_id))
        prev_chunk_path = chunk_dir / f"chunk_{chunk_index - 1}.wav" if chunk_index > 0 else None

        # 백그라운드에서 STT 처리 시작
        background_tasks.add_task(
            process_chunk_stt_with_overlap,
            meeting_id=meeting_id,
            user_id=user_id,
            chunk_index=chunk_index,
            chunk_path=chunk_path,
            prev_chunk_path=prev_chunk_path,
            speaker_name=user.name,
            db=db
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


async def process_chunk_stt_with_overlap(
    meeting_id: str,
    user_id: int,
    chunk_index: int,
    chunk_path: Path,
    prev_chunk_path: Path,
    speaker_name: str,
    db: Session
):
    """
    백그라운드에서 실행되는 STT 처리 (overlap 포함)
    
    Flow:
    1. Whisper STT 실행 (겹침 처리)
    2. 후처리 (필터링, 신뢰도 보정)
    3. DB 저장
    """
    
    try:
        logger.info(f"Background STT task started")
        
        # ===== Step 1: 겹침 처리 STT =====
        stt_result = await AudioProcessor.transcribe_chunk_with_overlap(
            chunk_path=Path(chunk_path),
            prev_chunk_path=Path(prev_chunk_path) if prev_chunk_path else None,
            user_id=user_id,
            chunk_index=chunk_index,
            speaker_name=speaker_name
        )
        
        # ===== Step 2: 후처리 =====
        segment = AudioProcessor.post_process_segment(stt_result)
        
        if segment is None:
            logger.warning(f"Segment was filtered out")
            return
        
        # ===== Step 3: DB 저장 =====
        logger.info(f"Saving segment to DB...")
        
        db_segment = STTSegment(
            segment_id=segment['segment_id'],
            meeting_id=meeting_id,
            user_id=segment['user_id'],
            chunk_index=chunk_index,
            text=segment['text'],
            confidence=segment['confidence'],
            start_time_ms=segment['start_time_ms'],
            end_time_ms=segment['end_time_ms'],
            source_chunks=segment['source_chunks'],
            is_overlapped=segment['is_overlapped']
        )
        
        db.add(db_segment)
        db.commit()
        
        logger.info(
            f"STT complete and saved to DB\n"
            f"   Segment ID: {segment['segment_id']}\n"
            f"   Text: {segment['text'][:50]}...\n"
            f"   Overlapped: {segment['is_overlapped']}\n"
            f"   Source chunks: {segment['source_chunks']}"
        )
    
    except Exception as e:
        logger.error(f"Background STT task failed: {e}", exc_info=True)
        db.rollback()
