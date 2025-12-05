from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.core.logger import setup_logger
from typing import Dict, List
import json

logger = setup_logger(__name__)


class RAGService:
    """LLM 기반 요약 및 분석"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3
        )
    
    async def generate_meeting_summary(
        self,
        meeting_id: str,
        full_text: str,
        segments: List[Dict],
        speakers: List[Dict]
    ) -> Dict:
        """회의 요약 생성"""
        
        logger.info(f"요약 생성 시작: {meeting_id}")
        
        # 화자 정보 요약
        speaker_info = "\n".join([
            f"- {s['name']}: {s['segment_count']}개 발화, "
            f"{s['total_duration_ms']//1000}초 발화"
            for s in speakers
        ])
        
        # 프롬프트 템플릿
        prompt = ChatPromptTemplate.from_messages([
            ("system", 
            """당신은 회의록 전문 분석가입니다. 
            주어진 회의 내용을 분석하여 JSON 형식으로 요약하세요.

            다음 JSON 구조를 반드시 따르세요:
            {{
            "summary_text": "전체 요약 (3-5문장)",
            "key_points": ["핵심 포인트 1", "핵심 포인트 2", ...],
            "action_items": ["실행 항목 1", "실행 항목 2", ...],
            "decisions": ["결정 사항 1", "결정 사항 2", ...],
            "next_agenda": ["다음 회의 안건 1", "다음 회의 안건 2", ...]
            }}

            명확하고 간결하게 작성하세요."""),
            
            ("human", 
            """회의 정보:
            참석자:
            {speaker_info}

            회의 내용:
            {transcript}

            위 회의 내용을 JSON 형식으로 요약해주세요.""")
        ])
        
        chain = prompt | self.llm
        
        try:
            # 토큰 제한 고려하여 텍스트 자르기
            max_chars = 12000  # 약 3000 토큰
            transcript_text = full_text[:max_chars]
            if len(full_text) > max_chars:
                transcript_text += "\n\n... (이하 생략)"
            
            response = await chain.ainvoke({
                "speaker_info": speaker_info,
                "transcript": transcript_text
            })
            
            # JSON 파싱
            content = response.content
            
            # ```json ... ``` 제거
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            summary_data = json.loads(content)
            summary_data["model"] = settings.LLM_MODEL
            
            logger.info("요약 생성 완료")
            logger.info(f"  Key points: {len(summary_data.get('key_points', []))}")
            logger.info(f"  Action items: {len(summary_data.get('action_items', []))}")
            
            return summary_data
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.error(f"응답 내용: {content}")
            
            # Fallback: 전체 텍스트를 summary_text로 사용
            return {
                "summary_text": content,
                "key_points": [],
                "action_items": [],
                "decisions": [],
                "next_agenda": [],
                "model": settings.LLM_MODEL
            }
        
        except Exception as e:
            logger.error(f"요약 생성 실패: {e}", exc_info=True)
            raise