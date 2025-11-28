from pathlib import Path
from app.config import settings

class PathManager:
    """로컬 파일 시스템 경로 관리"""
    
    @staticmethod
    def get_meeting_dir(meeting_id: str) -> Path:
        """특정 회의 디렉토리"""
        meeting_dir = settings.MEETINGS_DIR / meeting_id
        meeting_dir.mkdir(parents=True, exist_ok=True)
        return meeting_dir
    
    @staticmethod
    def get_raw_audio_dir(meeting_id: str) -> Path:
        """회의 raw_audio 디렉토리"""
        raw_dir = PathManager.get_meeting_dir(meeting_id) / "raw_audio"
        raw_dir.mkdir(parents=True, exist_ok=True)
        return raw_dir
    
    @staticmethod
    def get_audio_chunks_dir(meeting_id: str) -> Path:
        """회의 audio_chunks 디렉토리"""
        chunks_dir = PathManager.get_meeting_dir(meeting_id) / "audio" / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        return chunks_dir
    
    @staticmethod
    def get_user_chunk_dir(meeting_id: str, user_id: str) -> Path:
        """특정 사용자 chunk 디렉토리"""
        user_dir = PathManager.get_audio_chunks_dir(meeting_id) / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    
    @staticmethod
    def get_chunk_path(meeting_id: str, user_id: str, chunk_index: int) -> Path:
        """특정 chunk 파일 경로"""
        return PathManager.get_user_chunk_dir(meeting_id, user_id) / f"chunk_{chunk_index}.wav"
    

path_manager = PathManager()