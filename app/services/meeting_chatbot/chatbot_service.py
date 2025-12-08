from app.core.logger import setup_logger
from app.config import settings
from langchain_openai import ChatOpenAI

from .state import ChatbotState
from .graph_builder import build_graph

from app.core.mongodb import get_mongo_db
from app.services.meeting.mongodb_service import MongoMeetingService
from app.services.meeting.vectorStore_service import VectorStoreService

logger = setup_logger(__name__)

class MeetingChatbotService:

    def __init__(self):
        logger.info("Initializing MeetingChatbotService...")

        self.mongo_db = get_mongo_db()
        self.mongo_service = MongoMeetingService(self.mongo_db)

        self.vector_store = VectorStoreService()

        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3
        )

        self.graph = build_graph(
            llm=self.llm,
            vector_store=self.vector_store,
            mongo_service=self.mongo_service
        )

        logger.info("MeetingChatbotService initialized")

    async def ask(
            self, query: str, 
            meeting_id: str = None,
            group_id: str = None
            ) -> dict:
        logger.info(f"질문 처리: {query}")

        initial_state: ChatbotState = {
            "query": query,
            "meeting_id": meeting_id,
            "group_id": group_id,

            "relevant_segments": [],
            "meeting_context": {},

            "answer": "",
            "confidence": 0.0,
            "sources": [],

            "search_performed": False,
            "needs_more_info": False
        }

        final_state = await self.graph.ainvoke(initial_state)

        return {
            "answer": final_state["answer"],
            "confidence": final_state["confidence"],
            "sources": final_state["sources"],
            "relevant_segments": final_state["relevant_segments"]
        }
