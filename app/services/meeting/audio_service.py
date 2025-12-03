from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
from app.core.logger import setup_logger
from app.core.schemas import User, MeetingParticipant, STTSegment
from app.services.meeting.audio_processor import AudioProcessor
from app.services.meeting.paths import PathManager
from app.services.meeting.schemas import AudioChunkUploadResponse
from app.core.db import SessionLocal

logger = setup_logger(__name__)


class AudioService:
    """오디오 처리 서비스"""
    
    def __init__(self):
        self.audio_processor = AudioProcessor()
        self.user_cumulative_times = {}


    # 사용자의 현재 누적 시간 조회
    def _get_cumulative_time(self, meeting_id: str, user_id: int) -> int:
        if meeting_id not in self.user_cumulative_times:
            self.user_cumulative_times[meeting_id] = {}

        return self.user_cumulative_times[meeting_id].get(user_id, 0)
    
    # 사용자의 누적 시간 업데이트
    def _update_cumulative_time(
            self,
            meeting_id: str,
            user_id: int,
            duration_ms: int
    ):
        if meeting_id not in self.user_cumulative_times:
            self.user_cumulative_times[meeting_id] = {}
        
        current = self.user_cumulative_times[meeting_id].get(user_id, 0)
        
        # Overlap 제외하고 더함
        if current > 0:
            overlap_ms = int(AudioProcessor.OVERLAP_SECONDS * 1000)
            self.user_cumulative_times[meeting_id][user_id] = current + duration_ms - overlap_ms
        else:
            # 첫 청크
            self.user_cumulative_times[meeting_id][user_id] = duration_ms
        
        logger.info(
            f"[User {user_id}] Cumulative time updated: "
            f"{self.user_cumulative_times[meeting_id][user_id]}ms"
        )

    
    # 음성 청크 업로드 및 STT 처리
    async def upload_audio_chunk(
        self,
        meeting_id: str,
        audio_file: UploadFile,
        user_id: int,
        chunk_index: int,
        background_tasks: BackgroundTasks,
        db: Session
    ) -> AudioChunkUploadResponse:
        
        logger.info(f"Audio chunk upload: Meeting={meeting_id}, User={user_id}, Chunk={chunk_index}")
        
        # 1. 파일 읽기
        file_data = await audio_file.read()
        file_size_mb = len(file_data) / (1024 * 1024)
        logger.info(f"  File size: {file_size_mb:.2f} MB")
        
        # 2. 파일 검증
        validation = AudioProcessor.validate_audio_file(file_data)
        if not validation["is_valid"]:
            raise ValueError("Invalid audio format")
        
        # 사용자 확인
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        # 참가자 검증
        participant = (
            db.query(MeetingParticipant)
            .filter(
                MeetingParticipant.meeting_id == meeting_id,
                MeetingParticipant.user_id == user_id,
                MeetingParticipant.is_active == 1
            )
            .first()
        )
        if not participant:
            raise ValueError("User is not participating in this meeting")

        # 파일 저장
        chunk_path = AudioProcessor.save_chunk_file(
            meeting_id, user_id, chunk_index, file_data
        )
        
        # 이전 청크 경로 (겹침 처리용)
        chunk_dir = PathManager.get_user_chunk_dir(meeting_id, str(user_id))
        prev_chunk_path = chunk_dir / f"chunk_{chunk_index - 1}.wav" if chunk_index > 0 else None

        # 누적 시간 가져오기
        cumulative_time_ms = self._get_cumulative_time(meeting_id, user_id)
        
        # 백그라운드 STT 처리
        background_tasks.add_task(
            self._process_stt_background,
            meeting_id = meeting_id,
            user_id = user_id,
            chunk_index = chunk_index,
            chunk_path = chunk_path,
            prev_chunk_path = prev_chunk_path,
            speaker_name = user.name,
            cumulative_time_ms = cumulative_time_ms
        )
        
        return AudioChunkUploadResponse(
            meeting_id = meeting_id,
            user_id = user_id,
            chunk_index = chunk_index
        )
    
    # 백그라운드 STT 처리
    async def _process_stt_background(
        self,
        meeting_id: str,
        user_id: int,
        chunk_index: int,
        chunk_path: Path,
        prev_chunk_path: Path,
        speaker_name: str,
        cumulative_time_ms: int
    ):
        logger.info(f"[STT] User {user_id}, Chunk {chunk_index} started")
        db = SessionLocal()
        
        try:
            # 1. STT 처리
            stt_result = await self.audio_processor.transcribe_chunk_with_overlap(
                chunk_path = chunk_path,
                prev_chunk_path = prev_chunk_path,
                user_id = user_id,
                chunk_index = chunk_index,
                speaker_name = speaker_name,
                cumulative_time_ms = cumulative_time_ms
            )

            # 2. 누적시간 업데이트
            self._update_cumulative_time(
                meeting_id,
                user_id,
                stt_result["duration_ms"]
            )

            # 3. 각 segment를 개별적으로 DB에 저장
            saved_count = 0
            for seg in stt_result["segments"]:
                # 후처리 : 빈 텍스트 제외
                if not seg["text"] or len(seg["text"]) < 2 :
                    logger.debug(f"빈 segment 건너뛰기 : {seg}")
                    continue

                # 후처리 : 너무 짧은 segment 제외
                duration_ms = seg["end_time_ms"] - seg["start_time_ms"]
                if duration_ms < 500 :  # 0.5초 미만
                    logger.debug(f"짧은 segment 건너뛰기 ({duration_ms}ms) : {seg}")
                    continue

                # segment_id 생성
                segment_id = (
                    f"seg_{meeting_id}_{user_id}_"
                    f"{chunk_index}_{seg['segment_index']}"
                )

                # confidence 조정
                text_length = len(seg["text"])
                adjusted_confidence = min(
                    0.95, 
                    seg["confidence"] + (text_length / 100) * 0.1
                )
            
                # DB 저장
                db_segment = STTSegment(
                    segment_id = segment_id,
                    meeting_id = meeting_id,
                    user_id = user_id,
                    chunk_index = chunk_index,
                    text = seg["text"],
                    confidence = adjusted_confidence,
                    start_time_ms = seg["start_time_ms"],
                    end_time_ms = seg["end_time_ms"],
                    source_chunks = stt_result["source_chunks"],
                    is_overlapped = stt_result["is_overlapped"]
                )
                db.add(db_segment)
                saved_count += 1

            db.commit()
            
            logger.info(
                f"[STT] User {user_id}, Chunk {chunk_index} 완료\n"
                f"   저장된 segments: {saved_count}"
            )
        
        except Exception as e:
            logger.error(f"[STT] Failed: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()