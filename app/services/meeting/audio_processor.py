import asyncio
import time
import io
import numpy as np
import soundfile as sf
import multiprocessing as mp
from pathlib import Path
from typing import Dict, Optional
from concurrent.futures import ProcessPoolExecutor
from app.core.logger import setup_logger
from faster_whisper import WhisperModel
from app.services.meeting.paths import PathManager

logger = setup_logger(__name__)

# ===== 워커 함수 (별도 프로세스에서 실행) =====
def _whisper_worker_function(
    audio_path: str,
    model_size: str,
    device: str,
    compute_type: str,
    language: str
):
    logger.info("whisper_worker_function ::: ")
    try:
        # 각 프로세스마다 독립적인 모델 생성
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            num_workers=1
        )

        start_transcribe = time.time()
        
        # STT 수행
        segments_generator, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,  # Voice Activity Detection (침묵 제거)
            vad_parameters={
                "threshold": 0.5,
                "min_speech_duration_ms": 250,
                "min_silence_duration_ms": 2000
            }
        )

        transcribe_time = time.time() - start_transcribe
        logger.info(f"Transcribe call completed in {transcribe_time:.2f}s")

        start_convert = time.time()
        segments_list = list(segments_generator)
        convert_time = time.time() - start_convert
        logger.info(f"Converted {len(segments_list)} segments in {convert_time:.2f}s")

        # 세그먼트 수집
        all_segments = []
        full_text = ""
        
        for idx, segment in enumerate(segments_list):
            segment_data = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "confidence": segment.avg_logprob
            }
            all_segments.append(segment_data)
            full_text += segment.text + " "
            
            # 주기적 로그 (10개마다)
            if (idx + 1) % 10 == 0:
                logger.info(f"  Processed {idx + 1}/{len(segments_list)} segments")
        
        return {
            "success": True,
            "text": full_text.strip(),
            "segments": all_segments,
            "language": info.language,
            "duration": info.duration
        }
    
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

class AudioProcessor:
    """
    faster-whisper 기반 음성 처리 (프로세스 풀)
    whisper_model → executor (프로세스 풀)
    """
    
    executor = None  # ProcessPoolExecutor (기존: whisper_model)
    model_size = "large-v3"
    device = "cuda"
    compute_type = "float16"  # GPU: float16, CPU: int8
    max_workers = 2  # 동시 처리 프로세스 개수
    
    CHUNK_DURATION_MS = 60000
    # OVERLAP_MS = 10000
    OVERLAP_SECONDS = 5.0
    
    @classmethod
    def initialize_whisper(cls, max_workers: int = 2, model_size: str = "large-v3"):
        """
        프로세스 풀 초기화 (앱 시작 시 한 번만)
        
        기존: whisper.load_model()
        변경: ProcessPoolExecutor 생성
        
        Args:
            max_workers: 동시 처리 개수
                - GPU 1개: 1-2 권장
                - CPU: 4-8 권장
            model_size: Whisper 모델 크기
        """
        if cls.executor is None:
            cls.max_workers = max_workers
            cls.model_size = model_size
            
            logger.info("="*60)
            logger.info(f"Initializing faster-whisper Process Pool")
            logger.info(f"  Model: {cls.model_size}")
            logger.info(f"  Device: {cls.device}")
            logger.info(f"  Compute Type: {cls.compute_type}")
            logger.info(f"  Max Workers: {cls.max_workers}")
            logger.info("="*60)
            
            # 프로세스 풀 생성
            cls.executor = ProcessPoolExecutor(
                max_workers=cls.max_workers,
                mp_context=mp.get_context('spawn')
            )
            
            logger.info(f"Process pool ready")
    
    @classmethod
    def shutdown(cls):
        """프로세스 풀 종료 (앱 종료 시)"""
        if cls.executor:
            logger.info("Shutting down process pool...")
            cls.executor.shutdown(wait=True)
            cls.executor = None
            logger.info("Process pool shutdown complete")
    
    @staticmethod
    def save_chunk_file(
        meeting_id: str,
        user_id: int,
        chunk_index: int,
        file_data: bytes
    ) -> Path:
        """
        음성 청크 파일 저장
        """
        try:
            chunk_dir = PathManager.get_user_chunk_dir(meeting_id, str(user_id))
            chunk_path = chunk_dir / f"chunk_{chunk_index}.wav"
            
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
        음성 파일 검증
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
        
    
    @staticmethod
    def get_audio_duration_ms(audio_path: Path) -> int:
        """
        오디오 파일의 실제 길이 측정 (ms)
        """
        try:
            data, sample_rate = sf.read(str(audio_path))
            duration_seconds = len(data) / sample_rate
            duration_ms = int(duration_seconds * 1000)
            return duration_ms

        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 60000

    
    @classmethod
    async def transcribe_chunk_with_overlap(
        cls,
        chunk_path: Path,
        prev_chunk_path: Optional[Path] = None,
        user_id: int = None,
        chunk_index: int = None,
        speaker_name: str = None,
        cumulative_time_ms: int = 0
    ) -> Dict:
        """
        겹침 처리를 통한 STT
        """
        logger.info(
            f"Starting STT with overlap\n"
            f"   User: {user_id}\n"
            f"   Chunk: {chunk_index}"
        )
        
        try:
            if not chunk_path.exists():
                raise FileNotFoundError(f"Audio file not found: {chunk_path}")
            
            current_duration_ms = cls.get_audio_duration_ms(chunk_path)
            logger.info(f"Current chunk duration: {current_duration_ms}ms")
            
            # ===== 1단계: 겹침 처리 =====
            source_chunks = [chunk_index]
            is_overlapped = False
            stt_audio_path = chunk_path
            overlap_offset_ms = 0
            
            if prev_chunk_path and prev_chunk_path.exists() and chunk_index > 0:
                logger.info("prev_chunk_path exists!!!")
                try:
                    # 이전 청크와 현재 청크 읽기
                    prev_data, prev_sr = sf.read(str(prev_chunk_path))
                    curr_data, curr_sr = sf.read(str(chunk_path))

                    # overlap 샘플 수 계산 (5초)
                    overlap_samples = int(cls.OVERLAP_SECONDS * prev_sr)

                    # 이전 청크의 뒷부분 5초 + 현재 청크 전체
                    if len(prev_data) >= overlap_samples:
                        prev_overlap = prev_data[-overlap_samples:]
                        combined_audio = np.concatenate([prev_overlap, curr_data])

                        # 결합된 오디오를 임시 파일로 저장
                        temp_path = chunk_path.parent / f"temp_combined_{chunk_path.name}"
                        sf.write(str(temp_path), combined_audio, curr_sr)
                    
                        # STT는 결합된 파일로 수행
                        stt_audio_path = temp_path
                        source_chunks = [chunk_index - 1, chunk_index]
                        is_overlapped = True
                        overlap_offset_ms = int(cls.OVERLAP_SECONDS * 1000)

                        logger.info(f"Combined successfully")
                    else:
                        logger.warning(f"Previous chunk too short for overlap")
                
                except Exception as e:
                    logger.warning(f"Failed to combine with previous: {e}")
                    is_overlapped = False
            
            # ===== 2단계: 프로세스 풀에 STT 작업 제출 =====
            logger.info(f"[User {user_id}] Submitting to process pool...")
            
            start_time = time.perf_counter()
            
            # 기존: await asyncio.to_thread(cls.whisper_model.transcribe, ...)
            # 변경: 프로세스 풀 사용
            loop = asyncio.get_event_loop()

            result = await asyncio.wait_for(
                loop.run_in_executor(
                    cls.executor,
                    _whisper_worker_function,
                    str(stt_audio_path),
                    cls.model_size,
                    cls.device,
                    cls.compute_type,
                    "ko"
                ),
                timeout=300.0  # 5분
            )
            
            elapsed = time.perf_counter() - start_time
            
            # 임시 파일 삭제
            if is_overlapped and 'temp_path' in locals() and temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug(f"Deleted temp file")
                except Exception as e:
                    logger.warning(f"Failed to delete temp file: {e}")
            
            # ===== 3단계: 결과 확인 =====
            if not result["success"]:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"STT worker failed: {error_msg}")
                if "traceback" in result:
                    logger.error(f"Traceback:\n{result['traceback']}")
                raise Exception(f"STT error: {error_msg}")
            
            segments = result["segments"]

            if not segments:
                logger.warning(f"[User {user_id}] STT 결과 없음")
            
            logger.info(
                f"   STT completed\n"
                f"      Segments: {len(segments)}\n"
                f"      Overlapped: {is_overlapped}\n"
                f"      Processing time: {elapsed:.2f}s"
            )
            
            # ===== 4단계: 개별 segment 처리 =====
            processed_segments = []

            for idx, seg in enumerate(segments):
                # segment 원래 시간 (STT 오디오 기준)
                seg_start_in_audio = seg["start"] * 1000
                seg_end_in_audio = seg["end"] * 1000

                # Overlap 고려한 시간 계산
                if is_overlapped:
                    # 겹친 구간 제외 (앞 5초)
                    if seg_start_in_audio < overlap_offset_ms:
                        logger.debug(
                            f"Segment {idx}는 overlap 구간 내 → 건너뛰기"
                        )
                        continue

                    actual_start_ms = seg_start_in_audio - overlap_offset_ms
                    actual_end_ms = seg_end_in_audio - overlap_offset_ms
                else:
                    actual_start_ms = seg_start_in_audio
                    actual_end_ms = seg_end_in_audio

                # 누적시간 기준으로 절대시간 계산
                absolute_start_ms = cumulative_time_ms + actual_start_ms
                absolute_end_ms = cumulative_time_ms + actual_end_ms

                processed_segments.append({
                    "text": seg["text"].strip(),
                    "confidence": seg["confidence"],
                    "start_time_ms": int(absolute_start_ms),
                    "end_time_ms": int(absolute_end_ms),
                    "segment_index": idx
                })

            logger.info(
                f"처리 완료: {len(processed_segments)} segments "
                f"(원본 {len(segments)}에서 필터링)"
            )

            return {
                "chunk_index": chunk_index,
                "user_id": user_id,
                "speaker_name": speaker_name,
                "segments": processed_segments,
                "duration_ms": current_duration_ms,
                "source_chunks": ",".join(map(str, source_chunks)),
                "is_overlapped": is_overlapped,
                "total_segments": len(processed_segments)
            }
        
        except Exception as e:
            logger.error(f"STT failed: {e}", exc_info=True)
            raise