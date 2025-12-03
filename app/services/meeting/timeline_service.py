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
    def merge_timeline(db: Session, meeting_id: str) -> Dict:
        logger.info(f"타임라인 병합 시작 : {meeting_id}")

        # 회의 정보 조회
        meeting = db.query(Meeting).filter(
            Meeting.meeting_id == meeting_id
        ).first()

        if not meeting:
            raise ValueError(f"회의를 찾을 수 없음: {meeting_id}")
        
        # 모든 segment 조회 (시간순 정렬)
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

        # 변환
        segments_list = []
        for seg, speaker_name in segments_raw:
            # 절대시간 = 회의시작 timestamp + segment의 상대시간
            absolute_start_ms = meeting.start_server_timestamp + seg.start_time_ms
            absolute_end_ms = meeting.start_server_timestamp + seg.end_time_ms

            segments_list.append({
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

        # 겹침 구간 감지
        overlaps = TimelineService._detect_overlaps(segments_list)
        if overlaps:
            logger.info(f"감지된 겹침 구간 : {len(overlaps)}개")

        # 전체 텍스트 생성
        full_text = TimelineService._generate_full_text(segments_list)
        logger.info(f"전체 텍스트 : {full_text}")

        # 화자 통계
        speakers = TimelineService._calculate_speaker_stats(segments_list)

        result = {
            "segments": segments_list,
            "full_text": full_text,
            "total_segments": len(segments_list),
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

            # 형식 : [00:05] [화자명] 발화 내용
            line = f"{timestamp_str} [{seg['speaker_name']}] {seg['text']}"
            lines.append(line)
        
        return "\n".join(lines)


    # 화자별 통계 계산
    @staticmethod
    def _calculate_speaker_stats(segments: List[Dict]) -> List[Dict]:
        speaker_stats = defaultdict(lambda: {
            "segment_count": 0,
            "total_duration_ms": 0,
            "word_count": 0
        })
        
        for seg in segments:
            uid = seg["user_id"]
            name = seg["speaker_name"]

            speaker_stats[uid]["user_id"] = uid
            speaker_stats[uid]["name"] = name
            speaker_stats[uid]["segment_count"] += 1
            speaker_stats[uid]["total_duration_ms"] += (
                seg["end_time_ms"] - seg["start_time_ms"]
            )
            speaker_stats[uid]["word_count"] += len(seg["text"])

        return list(speaker_stats.values())