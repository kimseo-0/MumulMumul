import re
from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)


class TextProcessor:
    """STT 텍스트 후처리 서비스"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model = "gpt-4o-mini",
            api_key = settings.OPENAI_API_KEY,
            temperature = 0.1
        )

    # -----------------
    # 규칙기반 전처리
    # -----------------
    @staticmethod
    def rule_based_cleaning(text: str) -> str:
        """규칙 기반 텍스트 정리"""
        
        if not text:
            return text
        
        original_text = text
        
        # 1. 공백 정규화
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # 2. 반복 문자 제거 (3회 이상)
        # "네네네네" → "네"
        text = re.sub(r'(.)\1{2,}', r'\1', text)
        
        # 3. 불필요한 추임새 제거
        fillers = [
            r'\b음+\b', r'\b어+\b', r'\b그+\b', r'\b저+\b',
            r'\b아+\b', r'\b이+\b', r'\b으+\b'
        ]
        for filler in fillers:
            text = re.sub(filler, '', text, flags=re.IGNORECASE)
        
        # 4. 반복 단어 제거
        # "네 네 네" → "네"
        text = re.sub(r'\b(\w+)(\s+\1){2,}\b', r'\1', text)
        
        # 5. 특수문자 정리
        text = re.sub(r'[ㅋㅎㅠㅜㅡ]+', '', text)  # ㅋㅋㅋ, ㅎㅎㅎ 제거
        
        # 6. 다시 공백 정규화
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        if original_text != text:
            logger.debug(f"규칙 정리: '{original_text}' → '{text}'")
        
        return text
    
    @staticmethod
    def is_meaningful_text(text: str, min_length: int = 3) -> bool:
        """의미있는 텍스트인지 확인"""
        
        if not text or len(text) < min_length:
            return False
        
        # 너무 짧은 단어들만 있으면 제외
        words = text.split()
        if all(len(w) <= 1 for w in words):
            return False
        
        # 숫자/특수문자만 있으면 제외
        if re.match(r'^[\d\s\W]+$', text):
            return False
        
        return True
    

    
    # -----------------
    # LLM 기반 보정
    # -----------------

    # LLM으로 문맥 보정
    async def llm_based_correction(
        self,
        segments: List[Dict],
        batch_size: int = 10
    ) -> List[Dict]:
        
        logger.info(f"LLM 기반 텍스트 보정 시작 (총 {len(segments)}개)")

        corrected_segments = []

        # 배치로 처리
        for i in range(0, len(segments), batch_size):
            batch = segments[i : i+batch_size]

            try:
                corrected_batch = await self._correct_batch(batch)
                corrected_segments.extend(corrected_batch)

                logger.info(f"진행: {len(corrected_segments)} / {len(segments)}")


            except Exception as e:
                logger.error(f"배치 보정 실패 : {e}")
                corrected_segments.extend(batch)

        logger.info("LLM 텍스트 보정 완료")
        return corrected_segments
    

    # 배치단위 보정
    async def _correct_batch(self, segments: List[Dict]) -> List[Dict]:
        # 프롬프트 구성
        segment_texts = []
        for idx, seg in enumerate(segments):
            segment_texts.append(
                f"{idx+1}. [{seg['speaker_name']}] {seg['text']}"
            )

        segments_str = "\n".join(segment_texts)

        prompt = ChatPromptTemplate.from_messages([
            ("system",
            """
            당신은 회의록 텍스트 교정 전문가입니다.

            다음 규칙에 따라 텍스트를 수정하세요:
                1. **띄어쓰기 교정**: 잘못된 띄어쓰기 수정
                2. **맞춤법 교정**: 오타나 잘못된 표현 수정
                3. **문장 완성**: 불완전한 문장 보완 (단, 의미 변경 금지)
                4. **영어 표기**: "에이피아이" → "API", "씨에스에스" → "CSS"
                5. **원본 유지**: 화자명과 번호는 절대 변경 금지
                6. **의미 유지**: 원래 의미를 절대 바꾸지 말 것

            출력 형식:
            1. [화자명] 수정된 텍스트
            2. [화자명] 수정된 텍스트
            ...
            **중요**: 반드시 원본과 동일한 개수의 문장을 출력하세요.
            """),
            ("human", "{segments}")
        ])

        chain = prompt | self.llm

        response = await chain.ainvoke({"segments" : segments_str})

        # 응답 파싱
        corrected_lines = response.content.strip().split("\n")

        # 각 segment에 보정된 텍스트 적용
        corrected_segments = []
        for idx, seg in enumerate(segments):
            if idx < len(corrected_lines):
                corrected_line = corrected_lines[idx]
                
                # "1. [화자명] 텍스트" 형식에서 텍스트 추출
                match = re.search(r'\d+\.\s*\[.+?\]\s*(.+)', corrected_line)
                if match:
                    corrected_text = match.group(1).strip()
                    
                    # 보정된 텍스트 적용
                    seg_copy = seg.copy()
                    seg_copy["text"] = corrected_text
                    seg_copy["original_text"] = seg["text"]  # 원본 보관
                    corrected_segments.append(seg_copy)
                else:
                    # 파싱 실패 시 원본 사용
                    corrected_segments.append(seg)
            else:
                corrected_segments.append(seg)
        
        return corrected_segments
    

    # -----------------
    # 통합 처리
    # -----------------
    
    async def process_segments(
        self,
        segments: List[Dict],
        use_llm: bool = True
    ) -> List[Dict]:

        logger.info(f"텍스트 후처리 시작 (총 {len(segments)}개)")
        
        processed_segments = []
        
        # 1단계: 규칙 기반 정리
        logger.info("1단계: 규칙 기반 정리")
        for seg in segments:
            cleaned_text = self.rule_based_cleaning(seg["text"])
            
            # 의미있는 텍스트인지 확인
            if self.is_meaningful_text(cleaned_text):
                seg_copy = seg.copy()
                seg_copy["text"] = cleaned_text
                processed_segments.append(seg_copy)
            else:
                logger.debug(f"의미없는 텍스트 제외: '{seg['text']}'")
        
        logger.info(f"{len(processed_segments)}개 segment 유지 (원본 {len(segments)}개)")
        
        # 2단계: LLM 보정 (선택적)
        if use_llm and processed_segments:
            logger.info("2단계: LLM 기반 보정")
            processed_segments = await self.llm_based_correction(processed_segments)
        
        logger.info(f"텍스트 후처리 완료: {len(processed_segments)}개")
        
        return processed_segments