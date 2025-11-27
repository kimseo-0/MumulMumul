import asyncio
import soundfile as sf
import numpy as np
import whisper
import io
from pathlib import Path
from typing import List, Dict, Tuple
from app.core.logger import setup_logger
from app.services.meeting.paths import PathManager

logger = setup_logger(__name__)

class AudioProcessor:
    """음성 청크 처리 서비스"""
    
    def __init__(self):
        # Whisper 모델 로드 (첫 초기화 시에만)
        logger.info("Loading Whisper model...")
        self.whisper_model = whisper.load_model("large", device="cpu")
        logger.info("Whisper model loaded")
    
    @staticmethod
    def save_chunk_file(
        meeting_id: str,
        user_id: int,
        chunk_index: int,
        file_data: bytes
    ) -> Path:
        """
        음성 청크 파일 저장
        저장 경로: storage/meetings/{meeting_id}/audio/chunks/{user_id}/chunk_{chunk_index}.wav
        """
        try:
            chunk_dir = PathManager.get_user_chunk_dir(meeting_id, str(user_id))
            chunk_path = chunk_dir / f"chunk_{chunk_index}.wav"
            
            # 파일 저장
            with open(chunk_path, 'wb') as f:
                f.write(file_data)
            
            file_size_kb = len(file_data) / 1024
            logger.info(
                f"Audio chunk saved\n"
                f"   Path: {chunk_path}\n"
                f"   Size: {file_size_kb:.2f} KB"
            )
            
            return chunk_path
        
        except Exception as e:
            logger.error(f"Failed to save chunk: {e}")
            raise
    
    @staticmethod
    def validate_audio_file(file_data: bytes) -> Dict:
        """
        음성 파일 검증 (OPUS/WAV 모두 지원)
        """
        try:
            audio_buffer = io.BytesIO(file_data)
            data, sample_rate = sf.read(audio_buffer)
            
            if len(data.shape) == 1:
                channels = 1
            else:
                channels = data.shape[1]
            
            duration_ms = int((len(data) / sample_rate) * 1000)
            
            logger.info(
                f"Audio validated\n"
                f"   Duration: {duration_ms}ms\n"
                f"   Sample Rate: {sample_rate}Hz\n"
                f"   Channels: {channels}"
            )
            
            return {
                "is_valid": True,
                "duration_ms": duration_ms,
                "sample_rate": sample_rate,
                "channels": channels
            }
        
        except Exception as e:
            logger.error(f"Audio validation failed: {e}")
            return {
                "is_valid": False,
                "error": str(e)
            }
    