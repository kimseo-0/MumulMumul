from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.logger import setup_logger
from app.core.db import get_db
from app.services.meeting.schemas import AudioChunkUploadResponse, StartMeetingRequest, StartMeetingResponse, JoinMeetingRequest, JoinMeetingResponse, EndMeetingResponse
from app.services.meeting.audio_processor import AudioProcessor
from app.services.meeting.meeting_service import MeetingService
from app.services.meeting.audio_service import AudioService
from app.services.meeting.timeline_service import TimelineService

logger = setup_logger(__name__)
router = APIRouter()

# service instance
meeting_service = MeetingService()
audio_service = AudioService()
audio_processor = AudioProcessor()
timeline_service = TimelineService()


# 회의 시작
@router.post("/start", response_model = StartMeetingResponse)
async def start_meeting(
    request: StartMeetingRequest,
    db: Session = Depends(get_db)
):
    logger.info("Starting new meeting")
    try:
        return meeting_service.start_meeting(request, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

# 회의 참가
@router.post("/{meeting_id}/join", response_model = JoinMeetingResponse)
async def join_meeting(
    meeting_id: str,
    request: JoinMeetingRequest,
    db: Session = Depends(get_db)
):
    logger.info(f"User {request.user_id} joining meeting {meeting_id}")
    try:
        return meeting_service.join_meeting(meeting_id, request, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to join meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 음성 청크 업로드
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
        return await audio_service.upload_audio_chunk(
            meeting_id=meeting_id,
            audio_file=audio_file,
            user_id=user_id,
            chunk_index=chunk_index,
            background_tasks=background_tasks,
            db=db
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Audio upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 회의 종료
@router.post("/{meeting_id}/end", response_model=EndMeetingResponse)
async def end_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        result = meeting_service.end_meeting(meeting_id, db)

        # RAG 파이프라인 시작
        # background_tasks.add_task(
        #     pipeline_service.run_rag_pipeline,
        #     meeting_id=meeting_id
        # )

        background_tasks.add_task(
            timeline_service.merge_timeline,
            db=db,
            meeting_id=meeting_id
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"End meeting failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))