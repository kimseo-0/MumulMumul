from langchain_chroma import Chroma
from langchain_core.documents import Document
from app.config import settings
from app.services.meeting.embedding_service import EmbeddingService
from typing import List, Dict, Optional
from app.core.logger import setup_logger
from app.core.timezone import format_datetime, timestamp_to_datetime

logger = setup_logger(__name__)


class VectorStoreService:
    """ChromaDB 벡터 저장소 서비스"""
    
    def __init__(self):
        """ChromaDB 초기화"""
        self.embedding_function = EmbeddingService.get_instance()
        self.persist_directory = str(settings.VECTORSTORE_DIR / "meetings")
        logger.info(f"VectorStore 초기화: {self.persist_directory}")
    
    # ===== Segment 벡터 저장소 (회의별) =====
    def get_segments_vectorstore(self, meeting_id: str) -> Chroma:
        """
        회의별 segment 벡터저장소 가져오기
        
        Collection: segments_{meeting_id}
        경로: storage/vectorstore/
        """
        collection_name = f"segments_{meeting_id}"
        
        logger.debug(f"Getting vectorstore: {collection_name}")

        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self.embedding_function,
            persist_directory=self.persist_directory,
            collection_metadata={
                "meeting_id": meeting_id,
                "type": "segments"
            }
        )
        return vectorstore
    
    def add_segments_batch(
        self,
        meeting_id: str,
        segments: List[Dict]
    ):
        """배치로 segment 추가"""
        try:
            vectorstore = self.get_segments_vectorstore(meeting_id)

            documents = []
            ids = []
            
            for seg in segments:
                doc = Document(
                    page_content=seg["text"],
                    metadata={
                        "segment_id": seg["segment_id"],
                        "user_id": seg["user_id"],
                        "speaker_name": seg["speaker_name"],
                        "absolute_start_ms": seg["absolute_start_ms"],
                        "absolute_end_ms": seg["absolute_end_ms"],
                        "confidence": seg["confidence"],
                        "timestamp": format_datetime(
                            timestamp_to_datetime(seg["absolute_start_ms"]),
                            "%Y-%m-%d %H:%M:%S"
                        )
                    }
                )
                documents.append(doc)
                ids.append(seg["segment_id"])

            # 배치 추가
            vectorstore.add_documents(
                documents=documents,
                ids=ids
            )

            logger.info(f"ChromaDB에 {len(documents)}개 segment 임베딩 추가")

        except Exception as e:
            logger.error(f"Segment 추가 실패: {e}", exc_info=True)
            raise

    def search_segments(
        self,
        meeting_id: str,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict] = None
    ) -> List[Document]:
        """회의 내 segment 검색"""
        try:
            vectorstore = self.get_segments_vectorstore(meeting_id)
            
            if filter_dict:
                results = vectorstore.similarity_search(
                    query=query,
                    k=k,
                    filter=filter_dict
                )
            else:
                results = vectorstore.similarity_search(query=query, k=k)
            
            logger.info(f"Segment 검색 완료: {len(results)}개 결과")
            return results
        
        except Exception as e:
            logger.error(f"Segment 검색 실패: {e}", exc_info=True)
            raise
    
    # ===== 요약본 벡터 저장소 (전체) =====
    def get_summaries_vectorstore(self) -> Chroma:
        """
        전체 요약본 벡터 저장소
        
        Collection: summaries_global
        경로: storage/vectorstore/
        """
        vectorstore = Chroma(
            collection_name="summaries_global",
            embedding_function=self.embedding_function,
            persist_directory=self.persist_directory,
            collection_metadata={"type": "global_summaries"}
        )
        return vectorstore
    
    def add_summary(
        self,
        meeting_id: str,
        summary_text: str,
        metadata: Dict
    ):
        """요약본 추가"""
        try:
            vectorstore = self.get_summaries_vectorstore()

            doc = Document(
                page_content=summary_text,
                metadata={
                    "meeting_id": meeting_id,
                    **metadata
                }
            )

            vectorstore.add_documents(
                documents=[doc],
                ids=[f"summary_{meeting_id}"]
            )

            logger.info(f"ChromaDB에 summary 임베딩 추가: {meeting_id}")

        except Exception as e:
            logger.error(f"Summary 추가 실패: {e}", exc_info=True)
            raise

    def search_summaries(
        self,
        query: str,
        k: int = 5
    ) -> List[Document]:
        """전체 요약본에서 검색"""
        try:
            vectorstore = self.get_summaries_vectorstore()
            results = vectorstore.similarity_search(query=query, k=k)
            
            logger.info(f"Summary 검색 완료: {len(results)}개 결과")
            return results

        except Exception as e:
            logger.error(f"Summary 검색 실패: {e}", exc_info=True)
            raise