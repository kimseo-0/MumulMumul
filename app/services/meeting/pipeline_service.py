import json
import os
from pathlib import Path
from sqlalchemy.orm import Session
from app.core.logger import setup_logger
from app.core.db import SessionLocal
from app.core.mongodb import get_mongo_db, MeetingTranscript, MeetingSegment, OverlapInfo, MeetingSummary
from app.core.schemas import Meeting
from app.services.meeting.timeline_service import TimelineService
from app.services.meeting.chat_service import ChatService
from app.services.meeting.text_processor import TextProcessor
from app.services.meeting.mongodb_service import MongoMeetingService
from app.services.meeting.vectorStore_service import VectorStoreService
from app.services.meeting.rag_service import RAGService
from app.services.meeting.paths import PathManager
from datetime import datetime

logger = setup_logger(__name__)


class RAGPipelineService:
    """회의 종료 후 전체 RAG 파이프라인"""
    
    def __init__(self):
        self.timeline_service = TimelineService()
        self.text_processor = TextProcessor()
        self.vector_store = VectorStoreService()
        self.rag_service = RAGService()
        self.mongo_db = get_mongo_db()
        self.mongo_service = MongoMeetingService(self.mongo_db)
    
    async def run_rag_pipeline(self, meeting_id: str):
        """
        전체 RAG 파이프라인 실행
        
        [Phase 1] 타임라인 병합
        1. SQLite에서 모든 segment 조회
        2. 시간순 정렬 및 겹침 처리
        
        [Phase 1.5] 텍스트 후처리
        3. 규칙 기반 정리
        4. LLM 기반 보정
        
        [Phase 2] 데이터 저장
        5. MongoDB에 전사본 저장
        6. ChromaDB에 임베딩 저장
        
        [Phase 3] LLM 분석
        7. LLM으로 요약 생성
        8. 요약본 4곳 저장
        """
        logger.info(f"RAG Pipeline 시작: {meeting_id}")
        
        db = SessionLocal()
        
        try:
            # ===== 1. 회의 정보 조회 =====
            meeting = db.query(Meeting).filter(
                Meeting.meeting_id == meeting_id
            ).first()

            if not meeting:
                raise ValueError(f"Meeting not found: {meeting_id}")
            
            # ===== 2. 채팅 메시지 조회 =====
            chat_service = ChatService()
            chat_messages = []

            if meeting.chat_room_id:
                logger.info(f"채팅 메시지 조회: {meeting.chat_room_id}")

                chat_messages = chat_service.get_meeting_chat_messages(
                    room_id = meeting.chat_room_id,
                    start_timestamp = meeting.start_server_timestamp,
                    end_timestamp = meeting.start_server_timestamp + meeting.duration_ms
                )

                logger.info(f"채팅 메시지: {len(chat_messages)}개")

            # ===== 3. 음성 + 채팅 타임라인 병합 =====
            logger.info("타임라인 병합 (음성 + 채팅)")
            merged_data = self.timeline_service.merge_timeline(
                db = db,
                meeting_id = meeting_id,
                chat_messages = chat_messages
            )
            
            if not merged_data["segments"]:
                logger.warning("segment가 없어서 파이프라인 종료")
                return
            
            logger.info(
                f"병합 완료: {merged_data['total_segments']}개 "
                f"(음성 {merged_data['voice_segments']} + "
                f"채팅 {merged_data['chat_segments']})"
            )

            # ===== 4. 텍스트 후처리 =====
            logger.info("4. 텍스트 후처리")
            
            processed_segments = await self.text_processor.process_segments(
                segments=merged_data["segments"],
                use_llm=True  # LLM 보정 사용
            )
            
            # 후처리된 segment로 교체
            merged_data["segments"] = processed_segments
            merged_data["total_segments"] = len(processed_segments)
            
            # 전체 텍스트도 재생성
            merged_data["full_text"] = self._regenerate_full_text(processed_segments)
            
            logger.info(f"후처리 완료: {len(processed_segments)}개 segment")

            # ===== 5. 데이터 저장 =====
            logger.info("2. MongoDB & ChromaDB 저장")
            
            # MongoDB 전사본 저장
            transcript = self._create_transcript(db, meeting_id, merged_data)
            self.mongo_service.save_transcript(transcript)
            logger.info("MongoDB에 전사본 저장")
            
            # ChromaDB 임베딩 저장
            self.vector_store.add_segments_batch(
                meeting_id=meeting_id,
                segments=merged_data["segments"]
            )
            logger.info("ChromaDB에 segment 임베딩 저장")
            

            # ===== 6. LLM 분석 =====
            logger.info("3. LLM 요약 생성")
            
            summary = await self.rag_service.generate_meeting_summary(
                meeting_id=meeting_id,
                full_text=transcript.full_text,
                segments=merged_data["segments"],
                speakers=merged_data["speakers"]
            )
            logger.info("요약 생성 완료")
            
            # 요약본 4곳 저장
            await self._save_summary_all_stores(
                db, meeting_id, summary, transcript
            )
            logger.info("요약본 모든 저장소에 저장 완료")
            
            logger.info("="*60)
            logger.info(f"RAG Pipeline 완료: {meeting_id}")
            logger.info(f"   Segments: {merged_data['total_segments']}")
            logger.info(f"   Speakers: {len(merged_data['speakers'])}")
            logger.info(f"   Overlaps: {len(merged_data['overlaps'])}")
            logger.info("="*60)
        
        except Exception as e:
            logger.error(f"RAG Pipeline 실패: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    def _regenerate_full_text(self, segments: list) -> str:
        """후처리된 segment로 전체 텍스트 재생성"""
        lines = []
        
        for seg in segments:
            relative_ms = seg["start_time_ms"]
            minutes = relative_ms // 60000
            seconds = (relative_ms % 60000) // 1000
            
            timestamp_str = f"[{minutes:02d}:{seconds:02d}]"
            line = f"{timestamp_str} [{seg['speaker_name']}] {seg['text']}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def _create_transcript(
        self,
        db: Session,
        meeting_id: str,
        merged_data: dict
    ) -> MeetingTranscript:
        """MongoDB용 전사본 객체 생성"""
        
        meeting = db.query(Meeting).filter(
            Meeting.meeting_id == meeting_id
        ).first()
        
        # MeetingSegment 변환
        mongo_segments = []
        for seg in merged_data["segments"]:
            # 타임스탬프 표시 형식 생성 ([00:05])
            relative_ms = seg["start_time_ms"]
            minutes = relative_ms // 60000
            seconds = (relative_ms % 60000) // 1000
            timestamp_display = f"[{minutes:02d}:{seconds:02d}]"
            
            mongo_segments.append(
                MeetingSegment(
                    segment_id=seg["segment_id"],
                    user_id=seg["user_id"],
                    speaker_name=seg["speaker_name"],
                    text=seg["text"],
                    start_time_ms=seg["start_time_ms"],
                    end_time_ms=seg["end_time_ms"],
                    absolute_start_ms=seg["absolute_start_ms"],
                    absolute_end_ms=seg["absolute_end_ms"],
                    confidence=seg["confidence"],
                    timestamp_display=timestamp_display
                )
            )
        
        # 겹침 정보 변환
        overlap_infos = [
            OverlapInfo(**overlap) for overlap in merged_data["overlaps"]
        ]
        
        return MeetingTranscript(
            meeting_id=meeting_id,
            title=meeting.title,
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            duration_ms=meeting.duration_ms,
            participant_count=meeting.participant_count,
            organizer_id=meeting.organizer_id,
            full_text=merged_data["full_text"],
            segments=mongo_segments,
            overlaps=overlap_infos,
            total_segments=merged_data["total_segments"],
            speakers=merged_data["speakers"]
        )
    
    async def _save_summary_all_stores(
        self,
        db: Session,
        meeting_id: str,
        summary: dict,
        transcript: MeetingTranscript
    ):
        """요약본을 4곳에 저장"""
        
        logger.info("요약본 저장 중...")
        
        # 1. MongoDB 저장
        mongo_summary = MeetingSummary(
            meeting_id=meeting_id,
            summary_text=summary["summary_text"],
            key_points=summary.get("key_points", []),
            action_items=summary.get("action_items", []),
            next_agenda=summary.get("next_agenda", []),
            decisions=summary.get("decisions", []),
            model_used=summary.get("model", "gpt-4o-mini")
        )
        self.mongo_service.save_summary(mongo_summary)
        logger.info("MongoDB")
        
        # 2. ChromaDB 임베딩
        self.vector_store.add_summary(
            meeting_id=meeting_id,
            summary_text=summary["summary_text"],
            metadata={
                "title": transcript.title,
                "date": transcript.start_time,
                "participant_count": transcript.participant_count,
                "duration_ms": transcript.duration_ms
            }
        )
        logger.info("ChromaDB")
        
        # 3. SQLite 저장 (TODO: 나중에 추가)
        logger.info("SQLite (TODO)")
        
        # 4. JSON 파일 저장
        summary_dir = PathManager.get_meeting_dir(meeting_id) / "summaries"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        summary_path = summary_dir / "summary.json"
        
        summary_data = {
            "meeting_id": meeting_id,
            "title": transcript.title,
            "summary": summary,
            "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "model": summary.get("model", "gpt-4o-mini"),
            "total_segments": transcript.total_segments,
            "speakers": transcript.speakers
            }
        }

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
    
        logger.info(f"JSON: {summary_path}")