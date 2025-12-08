from langchain_chroma import Chroma
from langchain_core.documents import Document
from app.core.db import SessionLocal
from app.config import settings
from app.services.meeting.embedding_service import EmbeddingService
from typing import List, Dict, Optional
from app.core.logger import setup_logger
from app.core.timezone import format_datetime, timestamp_to_datetime
from app.core.schemas import Meeting

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
                        "meeting_id": meeting_id,
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

    # group_id 기반 검색
    def search_by_group_id(
        self,
        group_id: str,
        query: str,
        k: int = 5
    ) -> List[Document]:
        """
        chat_room_id(groupId)로 여러 회의 검색
        
        1. SQLite에서 해당 groupId의 모든 meeting_id 조회
        2. 각 meeting_id의 vectorstore에서 검색
        3. 결과 병합 및 relevance score 기준 정렬
        """
        try:
            logger.info(f"[VectorStore] Group 검색 : {group_id}")

            # 1. SQLite에서 해당 groupId의 모든 meeting_id 조회
            db = SessionLocal()
            meetings = db.query(Meeting).filter(
                Meeting.chat_room_id == group_id
            ).all()
            db.close()

            if not meetings:
                logger.warning(f"Group {group_id}에 해당하는 회의가 없습니다.")
                return []
            
            meeting_ids = [m.meeting_id for m in meetings]
            logger.info(f"발견된 회의 : {len(meeting_ids)}개 - {meeting_ids}")

            # 2. 각 meeting의 vectorstore에서 검색
            all_results = []
            for meeting_id in meeting_ids:
                try:
                    vectorStore = self.get_segments_vectorstore(meeting_id)
                    results = vectorStore.similarity_search_with_score(
                        query=query,
                        k=k
                    )

                    for doc, score in results:
                        all_results.append((doc, score, meeting_id))
                except Exception as e:
                    logger.warning(f"회의 {meeting_id} 검색 실패 : {e}")
                    continue

            if not all_results:
                logger.warning("모든 회의에서 검색 결과 없음")
                return []
            
            # 3. relevance score 기준 정렬 (낮을수록 유사)
            all_results.sort(key=lambda x: x[1])

            # 4. 상위 k개 반환
            top_results = all_results[:k]

            logger.info(
                f"검색 완료: {len(all_results)}개 중 상위 {len(top_results)}개 반환"
            )

            # Documents 반환
            return [doc for doc, score, meeting_id in top_results]

        except Exception as e:
            logger.error(f"Group 검색 실패 : {e}", exc_info=True)
            return []
        
        
    
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


    # group_id의 여러 회의 요약본 검색
    def search_summaries_by_group(
        self,
        group_id: str,
        query: str,
        k: int = 3
    ) -> List[Document]:
        try:
            logger.info(f"[VectorStore] Group 요약 검색: {group_id}")

            # 1. SQLite에서 meeting_ids 조회
            db = SessionLocal()
            meetings = db.query(Meeting).filter(
                Meeting.chat_room_id == group_id
            ).all()
            db.close()
            
            if not meetings:
                return []
            
            meeting_ids = [m.meeting_id for m in meetings]
            
            # 2. Global summaries vectorstore에서 검색
            vectorstore = self.get_summaries_vectorstore()
            
            # 3. meeting_id 필터 적용
            results = vectorstore.similarity_search(
                query=query,
                k=k * len(meeting_ids),
                filter={"meeting_id": {"$in": meeting_ids}}
            )
            
            # 상위 k개만 반환
            return results[:k]

        except Exception as e:
            logger.error(f"Group 요약 검색 실패: {e}", exc_info=True)
            return []