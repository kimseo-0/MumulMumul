from typing import TypedDict, List, Dict

class ChatbotState(TypedDict):
    query: str
    meeting_id: str
    group_id: str

    # 검색 결과
    relevant_segments: List[dict]
    meeting_context: Dict

    # 답변
    answer: str
    confidence: float
    sources: List[str]

    search_performed: bool
    needs_more_info: bool
