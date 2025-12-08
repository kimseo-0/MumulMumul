from pymongo.database import Database
from app.core.logger import setup_logger
from app.core.mongodb import MeetingTranscript, MeetingSummary
from typing import Optional

logger = setup_logger(__name__)


class MongoMeetingService:
    """MongoDB 회의 데이터 관리"""
    
    def __init__(self, db: Database):
        self.db = db
        self.transcripts = db["meeting_transcripts"]
        self.summaries = db["meeting_summaries"]
        logger.info("MongoDB Meeting Service 초기화 완료")
    
    # 회의 전사본 저장
    def save_transcript(self, transcript: MeetingTranscript):
        try:
            doc = transcript.model_dump()
            
            result = self.transcripts.update_one(
                {"meeting_id": transcript.meeting_id},
                {"$set": doc},
                upsert=True
            )
            logger.info(f"Transcript 저장: {transcript.meeting_id}")
            return result
        except Exception as e:
            logger.error(f"Transcript 저장 실패: {e}", exc_info=True)
            raise
    
    # 회의 요약본 저장
    def save_summary(self, summary: MeetingSummary):
        try:
            doc = summary.model_dump()
            
            result = self.summaries.update_one(
                {"meeting_id": summary.meeting_id},
                {"$set": doc},
                upsert=True
            )
            logger.info(f"Summary 저장: {summary.meeting_id}")
            return result
        except Exception as e:
            logger.error(f"Summary 저장 실패: {e}", exc_info=True)
            raise
    
    # 전사본 조회
    def get_transcript(self, meeting_id: str) -> Optional[MeetingTranscript]:
        try:
            doc = self.transcripts.find_one({"meeting_id": meeting_id})
            if doc:
                # _id 제거 (MongoDB ObjectId는 Pydantic에서 처리 안됨)
                doc.pop("_id", None)
                return MeetingTranscript(**doc)
            return None
        except Exception as e:
            logger.error(f"Transcript 조회 실패: {e}", exc_info=True)
            return None
    
    # 요약본 조회
    def get_summary(self, meeting_id: str) -> Optional[MeetingSummary]:
        try:
            doc = self.summaries.find_one({"meeting_id": meeting_id})
            if doc:
                # _id 제거
                doc.pop("_id", None)
                return MeetingSummary(**doc)
            return None
        except Exception as e:
            logger.error(f"Summary 조회 실패: {e}", exc_info=True)
            return None
    
    # 전사본 목록 조회
    def list_transcripts(
        self, 
        organizer_id: Optional[int] = None, 
        limit: int = 10
    ) -> list[MeetingTranscript]:
        try:
            query = {}
            if organizer_id:
                query["organizer_id"] = organizer_id
            
            docs = self.transcripts.find(query).sort("created_at", -1).limit(limit)
            
            results = []
            for doc in docs:
                doc.pop("_id", None)
                results.append(MeetingTranscript(**doc))
            
            return results
        except Exception as e:
            logger.error(f"Transcript 목록 조회 실패: {e}", exc_info=True)
            return []