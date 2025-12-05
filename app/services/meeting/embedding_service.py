from langchain_openai import OpenAIEmbeddings
from app.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class EmbeddingService:
    """LangChain 기반 임베딩 서비스 (OpenAI Embeddings)"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            logger.info(f"Initializing OpenAI embedding model: {settings.EMBEDDING_MODEL}")
            
            # OpenAI 임베딩 모델 초기화
            cls._instance = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                api_key=settings.OPENAI_API_KEY
            )

            logger.info("OpenAI Embedding model initialized")
        
        return cls._instance