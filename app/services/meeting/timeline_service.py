from sqlalchemy.orm import Session
from app.core.schemas import STTSegment, User, Meeting
from app.core.logger import setup_logger
from typing import List, Dict
from collections import defaultdict
import os

logger = setup_logger(__name__)


class TimelineService:
    """타임라인 병합 및 정리 서비스"""

    OVERLAP_THRESHOLD_MS = 1000     # 1초이내 겹침은 동시 발화로 간주

    # 모든 사용자의 segment를 시간순으로 병합
    @staticmethod
    def merge_timeline(
        db: Session,
        meeting_id: str,
        chat_messages: List[Dict] = None
    ) -> Dict:
        logger.info(f"타임라인 병합 시작 : {meeting_id}")

        # 회의 정보 조회
        meeting = db.query(Meeting).filter(
            Meeting.meeting_id == meeting_id
        ).first()

        if not meeting:
            raise ValueError(f"회의를 찾을 수 없음: {meeting_id}")
        
        # -------------------------------
        # 1. 음성 segment 조회 (시간순 정렬)
        # -------------------------------
        segments_raw = (
            db.query(STTSegment, User.name)
            .join(User, STTSegment.user_id == User.user_id)
            .filter(STTSegment.meeting_id == meeting_id)
            .order_by(STTSegment.start_time_ms)
            .all()
        )

        if not segments_raw:
            logger.warning("segment가 없음")
            return {
                "segments": [],
                "full_text": "",
                "total_segments": 0,
                "speakers": [],
                "overlaps": []
            }
        
        logger.info(f"로드된 segment: {len(segments_raw)}개")

        # 음성 segment 변환
        voice_segments = []
        for seg, speaker_name in segments_raw:
            # 절대시간 = 회의시작 timestamp + segment의 상대시간
            absolute_start_ms = meeting.start_server_timestamp + seg.start_time_ms
            absolute_end_ms = meeting.start_server_timestamp + seg.end_time_ms

            voice_segments.append({
                "type": "voice",
                "segment_id": seg.segment_id,
                "user_id": seg.user_id,
                "speaker_name": speaker_name,
                "text": seg.text.strip(),
                "confidence": seg.confidence,
                "start_time_ms": seg.start_time_ms,
                "end_time_ms": seg.end_time_ms,
                "absolute_start_ms": absolute_start_ms,
                "absolute_end_ms": absolute_end_ms,
                "chunk_index": seg.chunk_index,
                "is_overlapped": seg.is_overlapped
            })

        # -------------------------------
        # 2. 채팅 메시지 변환
        # -------------------------------
        chat_segments = []
        if chat_messages:
            logger.info(f"채팅 메시지: {len(chat_messages)}개")

            for i, msg in enumerate(chat_messages):
                relative_ms = msg["timestamp_ms"] - meeting.start_server_timestamp

                chat_segments.append({
                    "type" : "chat",
                    "segment_id" : f"chat_{meeting_id}_{i}",
                    "user_id" : msg["user_id"],
                    "speaker_name": msg["user_name"],
                    "text": msg["message"],
                    "confidence": 1.0,
                    "start_time_ms": relative_ms,
                    "end_time_ms": relative_ms,
                    "absolute_start_ms": msg["timestamp_ms"],
                    "absolute_end_ms": msg["timestamp_ms"],
                    "chunk_index": None,
                    "is_overlapped": False
                })

        # -------------------------------
        # 3. 음성 + 채팅 통합 및 시간순 정렬
        # -------------------------------
        all_segments = voice_segments + chat_segments
        all_segments.sort(key=lambda x: x["start_time_ms"])

        logger.info(
            f"통합 타임라인 : {len(all_segments)}개"
            f"(음성 {len(voice_segments)} + 채팅 {len(chat_segments)})"
        )

        # 4. 겹침 구간 감지 (음성끼리만)
        overlaps = TimelineService._detect_overlaps(voice_segments)
        if overlaps:
            logger.info(f"감지된 겹침 구간 : {len(overlaps)}개")

        # 5. 전체 텍스트 생성 (음성 + 채팅)
        full_text = TimelineService._generate_full_text(all_segments)
        logger.info(f"전체 텍스트 : {full_text}")

        # 6. 화자 통계 (음성 + 채팅)
        speakers = TimelineService._calculate_speaker_stats(all_segments)

        result = {
            "segments": all_segments,
            "full_text": full_text,
            "total_segments": len(all_segments),
            "voice_segments": len(voice_segments),
            "chat_segments": len(chat_segments),
            "speakers": speakers,
            "overlaps": overlaps
        }

        # 문서 저장 (storage/meetings/{meeting_id}/summaries/full_text.txt)
        summary_dir = f"storage/meetings/{meeting_id}/summaries"
        os.makedirs(summary_dir, exist_ok = True)

        file_path = os.path.join(summary_dir, "full_text.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        logger.info(f"Full text 저장 완료: {file_path}")

        logger.info(
            f"타임라인 병합 완료\n"
            f"  Total segments: {result['total_segments']}\n"
            f"  Speakers: {len(result['speakers'])}\n"
            f"  Overlaps: {len(result['overlaps'])}"
        )

        return result


    # 겹치는 구간 감지
    @staticmethod
    def _detect_overlaps(segments: List[Dict]) -> List[Dict]:
        overlaps = []

        for i in range(len(segments) - 1):
            current = segments[i]
            next_seg = segments[i + 1]

            # 다른 화자이면서 시간이 겹치는 경우
            if current["user_id"] != next_seg["user_id"]:
                overlap_start = max(
                    current["absolute_start_ms"], 
                    next_seg["absolute_start_ms"]
                )
                overlap_end = min(
                    current["absolute_end_ms"], 
                    next_seg["absolute_end_ms"]
                )

                overlap_duration = overlap_end - overlap_start

                # 실제 겹침이 있는 경우
                if overlap_duration > 0:
                    overlaps.append({
                        "segment1_id": current["segment_id"],
                        "segment2_id": next_seg["segment_id"],
                        "speaker1": current["speaker_name"],
                        "speaker2": next_seg["speaker_name"],
                        "overlap_duration_ms": overlap_duration,
                        "overlap_start_ms": overlap_start,
                        "overlap_end_ms": overlap_end
                    })

        return overlaps


    # 전체 대화 텍스트 생성 (타임스탬프 포함)
    @staticmethod
    def _generate_full_text(segments: List[Dict]) -> str:
        lines = []

        for seg in segments:
            # 상대시간 계산
            relative_ms = seg["start_time_ms"]
            minutes = relative_ms // 60000
            seconds = (relative_ms % 60000) // 1000

            timestamp_str = f"[{minutes:02d}:{seconds:02d}]"

            # 타입 표시
            type_maker = "[💬]" if seg["type"] == "chat" else "[🎤]"

            # 형식 : [00:05] [화자명] 발화 내용
            line = f"{timestamp_str} {type_maker} [{seg['speaker_name']}] {seg['text']}"
            lines.append(line)
        
        return "\n".join(lines)


    # 화자별 통계 계산
    @staticmethod
    def _calculate_speaker_stats(segments: List[Dict]) -> List[Dict]:
        speaker_stats = defaultdict(lambda: {
            "segment_count": 0,
            "voice_count": 0,
            "chat_count": 0,
            "total_duration_ms": 0,
            "word_count": 0
        })
        
        for seg in segments:
            uid = seg["user_id"]
            name = seg["speaker_name"]

            speaker_stats[uid]["user_id"] = uid
            speaker_stats[uid]["name"] = name
            speaker_stats[uid]["segment_count"] += 1

            if seg["type"] == "voice":
                speaker_stats[uid]["voice_count"] += 1
                speaker_stats[uid]["total_duration_ms"] += (
                    seg["end_time_ms"] - seg["start_time_ms"]
                )
            else:
                speaker_stats[uid]["chat_count"] += 1

            speaker_stats[uid]["word_count"] += len(seg["text"])

        return list(speaker_stats.values())