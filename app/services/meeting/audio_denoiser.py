import noisereduce as nr
import soundfile as sf
import numpy as np
from pathlib import Path
from typing import Optional
from app.core.logger import setup_logger

logger = setup_logger(__name__)


class AudioDenoiser:
    """음성 잡음 제거 서비스 (noisereduce)"""

    @classmethod
    def initialize(cls):
        """초기화 (noisereduce는 초기화 불필요)"""
        logger.info("AudioDenoiser 초기화 완료 (noisereduce)")

    @classmethod
    def denoise_audio(
        cls,
        audio_path: Path,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        음성 파일 잡음 제거

        Args:
            audio_path: 원본 오디오 경로
            output_path: 출력 경로 (None이면 원본 덮어쓰기)
        
        Returns:
            처리된 오디오 경로
        """
        try:
            logger.debug(f"잡음 제거 시작 : {audio_path.name}")

            # 1. 오디오 로드
            audio, sr = sf.read(str(audio_path))

            # 2. 스테레오 -> 모노 변환
            if len(audio.shape) == 2:
                audio = audio.mean(axis=1)

            # 3. 잡음 제거
            reduced = nr.reduce_noise(
                y = audio,
                sr = sr,
                stationary = True,
                prop_decrease = 1.0
            )

            # 4. 저장
            if output_path is None:
                output_path = audio_path

            sf.write(str(output_path), reduced, sr)

            logger.debug(f"잡음 제거 완료 : {output_path.name}")

            return output_path

        except Exception as e:
            logger.error(f"잡음 제거 실패 : {e}", exc_info = True)
            logger.warning("원본 오디오 사용")
            return audio_path
        
    @classmethod
    def shutdown(cls):
        """종료 (noisereduce는 종료 처리 불필요)"""
        pass