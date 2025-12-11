from typing import List, Dict, Tuple
from app.core.logger import setup_logger

logger = setup_logger(__name__)


class OverlapHandler:
    """동시 발화 처리 서비스"""

    # 겹침 임계값
    SHORT_OVERLAP_MS = 2000     # 2초 미만 : 무시
    LONG_OVERLAP_MS = 5000      # 5초 이상 : 선택

    @staticmethod
    def detect_all_overlaps(
        segments: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        모든 겹침 구간 감지 (음성-음성, 음성-채팅)
        """
        voice_voice_overlaps = []
        voice_chat_overlaps = []

        # 음성 segment만 분리
        voice_segs = [s for s in segments if s["type"] == "voice"]
        chat_segs = [s for s in segments if s["type"] == "chat"]

        # 1. 음성-음성 겹침 감지
        for i in range(len(voice_segs) - 1):
            current = voice_segs[i]
            next_seg = voice_segs[i + 1]

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

                if overlap_duration > 0:
                    voice_voice_overlaps.append({
                        "segment1_id": current["segment_id"],
                        "segment2_id": next_seg["segment_id"],
                        "speaker1": current["speaker_name"],
                        "speaker2": next_seg["speaker_name"],
                        "overlap_duration_ms": overlap_duration,
                        "overlap_start_ms": overlap_start,
                        "overlap_end_ms": overlap_end
                    })
        
        # 2. 음성-채팅 겹침 감지
        for voice_seg in voice_segs:
            for chat_seg in chat_segs:
                # 채팅 시간이 음성 구간 안에 있으면
                if (voice_seg["absolute_start_ms"] <= chat_seg["absolute_start_ms"] <= voice_seg["absolute_end_ms"]):
                    voice_chat_overlaps.append({
                        "voice_segment_id": voice_seg["segment_id"],
                        "chat_segment_id": chat_seg["segment_id"],
                        "voice_speaker": voice_seg["speaker_name"],
                        "chat_speaker": chat_seg["speaker_name"],
                        "chat_timestamp_ms": chat_seg["absolute_start_ms"],
                        "voice_start_ms": voice_seg["absolute_start_ms"],
                        "voice_end_ms": voice_seg["absolute_end_ms"]
                    })
        
        logger.info(
            f"겹침 감지 완료\n"
            f"  음성-음성: {len(voice_voice_overlaps)}개\n"
            f"  음성-채팅: {len(voice_chat_overlaps)}개"
        )

        return {
            "voice_voice": voice_voice_overlaps,
            "voice_chat": voice_chat_overlaps
        }
    

    @staticmethod
    def process_overlaps(
        segments: List[Dict],
        overlaps: List[Dict]
    ) -> List[Dict]:
        """
        겹침 구간 처리

        전략:
        - 음성-음성 : 기존 로직 (짧은/중간/긴 겹침)
        - 음성-채팅 : 항상 둘 다 유지, 채팅에 마커만 추가
        """
        logger.info(f"겹침 처리 시작")

        voice_voice = overlaps.get("voice_voice", [])
        voice_chat = overlaps.get("voice_chat", [])
        
        # segment를 dict로 변환 (빠른 조회)
        segment_dict = {seg["segment_id"] : seg for seg in segments}

        # 제거할 segment ID 추적
        segments_to_remove = set()

        # 1. 음성-음성
        for overlap in voice_voice:
            duration = overlap["overlap_duration_ms"]
            seg1_id = overlap["segment1_id"]
            seg2_id = overlap["segment2_id"]
            
            seg1 = segment_dict.get(seg1_id)
            seg2 = segment_dict.get(seg2_id)
            
            if not seg1 or not seg2:
                continue

            # 1) 짧은 겹침 (<2초) : 무시
            if duration < OverlapHandler.SHORT_OVERLAP_MS:
                logger.debug(
                    f"짧은 겹침 무시: {duration}ms "
                    f"({seg1['speaker_name']} <-> {seg2['speaker_name']})"
                )
                continue

            # 2) 중간 겹침 (2~5초) : 두 발화 모두 유지, 마커 추가
            elif duration < OverlapHandler.LONG_OVERLAP_MS:
                logger.info(
                    f"중간 겹침 감지: {duration}ms "
                    f"({seg1['speaker_name']} <-> {seg2['speaker_name']})"
                )
                
                # 두 segment 모두 유지하되 마커 추가
                seg1["overlap_marker"] = "simultaneous_voice"
                seg2["overlap_marker"] = "simultaneous_voice"
                
                # 텍스트에 마커 추가
                if not seg1["text"].startswith("[동시 발화]"):
                    seg1["text"] = f"[동시 발화] {seg1['text']}"
                if not seg2["text"].startswith("[동시 발화]"):
                    seg2["text"] = f"[동시 발화] {seg2['text']}"

            # 3) 긴 겹침 (>5초) : confidence 비교
            else:
                logger.warning(
                    f"긴 겹침 감지: {duration}ms "
                    f"({seg1['speaker_name']} <-> {seg2['speaker_name']})"
                )
                
                conf1 = seg1.get("confidence", 0.0)
                conf2 = seg2.get("confidence", 0.0)
                
                # confidence 낮은 것 제거
                if conf1 > conf2:
                    logger.info(f"  → {seg2['speaker_name']} 발화 제거")
                    segments_to_remove.add(seg2_id)
                else:
                    logger.info(f"  → {seg1['speaker_name']} 발화 제거")
                    segments_to_remove.add(seg1_id)
        
        # 2. 음성-채팅
        for overlap in voice_chat:
            voice_seg_id = overlap["voice_segment_id"]
            chat_seg_id = overlap["chat_segment_id"]
            
            voice_seg = segment_dict.get(voice_seg_id)
            chat_seg = segment_dict.get(chat_seg_id)
            
            if not voice_seg or not chat_seg:
                continue
            
            logger.debug(
                f"[음성-채팅] 겹침 감지: "
                f"{voice_seg['speaker_name']} 발화 중 "
                f"{chat_seg['speaker_name']} 채팅"
            )
            
            # 두 segment 모두 유지, 채팅에만 마커 추가
            chat_seg["overlap_marker"] = "during_voice"
            chat_seg["during_speaker"] = voice_seg["speaker_name"]
            
            # 채팅 텍스트에 컨텍스트 추가
            if not chat_seg["text"].startswith("[발화 중]"):
                chat_seg["text"] = f"[발화 중] {chat_seg['text']}"

        # 3. 제거할 segment 필터링
        if segments_to_remove:
            logger.info(f"제거할 segment: {len(segments_to_remove)}개")
            segments = [
                seg for seg in segments 
                if seg["segment_id"] not in segments_to_remove
            ]

        logger.info(f"겹침 처리 완료: 최종 {len(segments)}개 segment")
        return segments


    # @staticmethod
    # def merge_overlapping_segments(
    #     seg1: Dict,
    #     seg2: Dict
    # ) -> Dict:
    #     """
    #     두 겹치는 segment를 하나로 병합

    #     전략 : 두 발화를 "/" 또는 개행으로 연결
    #     """

    #     merged_text = f"{seg1['text']} / {seg2['text']}"

    #     return {
    #         **seg1,
    #         "text": merged_text,
    #         "speaker_name": f"{seg1['speaker_name']}, {seg2['speaker_name']}",
    #         "confidence": (seg1["confidence"] + seg2["confidence"]) / 2,
    #         "end_time_ms": max(seg1["end_time_ms"], seg2["end_time_ms"]),
    #         "absolute_end_ms": max(seg1["absolute_end_ms"], seg2["absolute_end_ms"]),
    #         "overlap_marker": "merged"
    #     }
    

    @staticmethod
    def format_overlapping_text(segments: List[Dict]) -> str:
        """
        겹침 구간 시각화 (음성 + 채팅)

        예시:
        [00:10] [홍길동] API 개발은...
        [00:20] [홍길동] ...진행 중입니다
                ├─ [동시 발화]
                └─ [김철수] 일정이 촉박합니다
        """
        lines = []
        prev_voice_overlap = None

        for i, seg in enumerate(segments):
            relative_ms = seg["start_time_ms"]
            minutes = relative_ms // 60000
            seconds = (relative_ms % 60000) // 1000
            timestamp = f"[{minutes:02d}:{seconds:02d}]"

            type_marker = "💬" if seg["type"] == "chat" else "🎤"

            # 음성-음성 동시 발화
            if seg.get("overlap_marker") == "simultaneous_voice":
                if prev_voice_overlap != seg["start_time_ms"]:
                    # 첫 번째 동시 발화
                    lines.append(f"{timestamp} [{type_marker} {seg['speaker_name']}] {seg['text']}")
                    lines.append("        ├─ [동시 발화 감지]")
                    prev_voice_overlap = seg["start_time_ms"]
                else:
                    # 두 번째 동시 발화
                    lines.append(f"        └─ [{type_marker} {seg['speaker_name']}] {seg['text']}")
                    prev_voice_overlap = None

            # 음성 중 채팅
            elif seg.get("overlap_marker") == "during_voice":
                lines.append(f"{timestamp}     └─ [{type_marker} {seg['speaker_name']}] {seg['text']}")

            else:
                lines.append(f"{timestamp} [{type_marker} {seg['speaker_name']}] {seg['text']}")
                prev_voice_overlap = None
        
        return "\n".join(lines)
