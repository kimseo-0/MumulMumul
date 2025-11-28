import asyncio
import soundfile as sf
import numpy as np
import whisper
import torch
import io
from pathlib import Path
from typing import List, Dict, Tuple
from app.core.logger import setup_logger
from app.services.meeting.paths import PathManager

logger = setup_logger(__name__)

class AudioProcessor:
    """음성 청크 처리 서비스"""
    
    # 클래스 변수 (한 번만 로드)
    whisper_model = None
    CHUNK_DURATION_MS = 60000
    OVERLAP_MS = 10000
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    @classmethod
    def initialize_whisper(cls, model_name: str = "large"):
        if cls.whisper_model is None:
            logger.info(f"Loading Whisper model: {model_name}... device: {cls.device}")
            cls.whisper_model = whisper.load_model(model_name, device=cls.device)
            logger.info(f"Whisper model loaded")
    
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
        
    @classmethod
    async def transcribe_chunk_with_overlap(
        cls,
        chunk_path: Path,
        prev_chunk_path: Path = None,
        user_id: int = None,
        chunk_index: int = None,
        speaker_name: str = None
    ) -> Dict:
        """
        겹침 처리를 통한 STT
        
        Parameters:
        - chunk_path: 현재 청크 파일 경로
        - prev_chunk_path: 이전 청크 파일 경로 (있으면 겹침 처리)
        - user_id: 사용자 ID
        - chunk_index: 청크 인덱스
        - speaker_name: 화자 이름
        
        Returns:
            STT 결과 딕셔너리
        """
        
        logger.info(
            f"Starting STT with overlap\n"
            f"   User: {user_id}\n"
            f"   Chunk: {chunk_index}"
        )
        
        try:
            if not chunk_path.exists():
                raise FileNotFoundError(f"Audio file not found: {chunk_path}")
            
            # ===== 1단계: 겹침 처리 (이전 청크 뒷부분 추가) =====
            combined_audio = None
            source_chunks = [chunk_index]
            is_overlapped = False
            
            if prev_chunk_path and prev_chunk_path.exists():
                logger.info("prev_chunk_path exists!!!")
                try:
                    prev_data, prev_sr = sf.read(str(prev_chunk_path))
                    curr_data, curr_sr = sf.read(str(chunk_path))
                    
                    # 겹침 부분 계산 (10초)
                    overlap_samples = int((cls.OVERLAP_MS / 1000) * prev_sr)
                    
                    # 이전 청크의 뒷부분(10초) + 현재 청크 전체
                    prev_overlap = prev_data[-overlap_samples:]
                    combined_audio = np.concatenate([prev_overlap, curr_data])
                    
                    source_chunks = [chunk_index - 1, chunk_index]
                    is_overlapped = True
                    
                    logger.debug(
                        f"   Combined with previous chunk\n"
                        f"      Total duration: {len(combined_audio) / curr_sr:.2f}s"
                    )
                
                except Exception as e:
                    logger.warning(f"   Failed to combine with previous: {e}")
                    combined_audio = None
            
            # 겹침 처리 실패 시 현재 청크만 사용
            if combined_audio is None:
                combined_audio, _ = sf.read(str(chunk_path))
                is_overlapped = False
            
            # ===== 2단계: Whisper STT 실행 =====
            result = await asyncio.to_thread(
                cls.whisper_model.transcribe,
                str(chunk_path),  # 원본 청크로 STT (겹침은 참고용)
                language="ko",
                verbose=False
            )
            
            text = result['text'].strip()
            
            logger.info(
                f"   STT completed\n"
                f"      Text: {text[:100]}...\n"
                f"      Overlapped: {is_overlapped}"
            )
            
            # ===== 3단계: 시간 정보 계산 =====
            if is_overlapped:
                # 겹침이 있는 경우: 이전 청크의 뒷부분(30초) 제외
                start_time_ms = chunk_index * cls.CHUNK_DURATION_MS + (cls.CHUNK_DURATION_MS - cls.OVERLAP_MS)
            else:
                # 겹침이 없는 경우: 정상 시간
                start_time_ms = chunk_index * cls.CHUNK_DURATION_MS
            
            end_time_ms = start_time_ms + cls.CHUNK_DURATION_MS
            
            return {
                "chunk_index": chunk_index,
                "user_id": user_id,
                "speaker_name": speaker_name,
                "text": text,
                "start_time_ms": start_time_ms,
                "end_time_ms": end_time_ms,
                "source_chunks": ",".join(map(str, source_chunks)),
                "is_overlapped": is_overlapped
            }
        
        except Exception as e:
            logger.error(f"STT failed: {e}", exc_info=True)
            raise


    @staticmethod
    def post_process_segment(stt_result: Dict) -> Dict:
        """
        후처리: STT 결과 정제
        
        1. 너무 짧은 텍스트 필터링
        2. 빈 텍스트 필터링
        3. 신뢰도 보정 (텍스트 길이 기반)
        4. 세그먼트 ID 생성
        """
        
        text = stt_result['text'].strip()
        duration_ms = stt_result['end_time_ms'] - stt_result['start_time_ms']
        
        # ===== 필터링 =====
        MIN_DURATION_MS = 500
        
        if duration_ms < MIN_DURATION_MS:
            logger.warning(f"Filtered: too short ({duration_ms}ms)")
            return None
        
        if not text or len(text) < 2:
            logger.warning(f"Filtered: empty text")
            return None
        
        # ===== 신뢰도 보정 =====
        # 텍스트가 길수록 신뢰도 높음 (0.7 ~ 0.95)
        text_length = len(text)
        adjusted_confidence = min(0.95, 0.7 + (text_length / 100) * 0.25)
        
        logger.debug(
            f"   Post-processed\n"
            f"      Adjusted confidence: {adjusted_confidence}\n"
            f"      Text length: {text_length}"
        )
        
        # ===== 세그먼트 생성 =====
        return {
            "segment_id": f"seg_{stt_result['user_id']}_{stt_result['chunk_index']}",
            "user_id": stt_result['user_id'],
            "speaker_name": stt_result['speaker_name'],
            "text": text,
            "confidence": adjusted_confidence,
            "start_time_ms": stt_result['start_time_ms'],
            "end_time_ms": stt_result['end_time_ms'],
            "source_chunks": stt_result['source_chunks'],
            "is_overlapped": stt_result['is_overlapped']
        }
    