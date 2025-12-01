# app/services/curriculum/enrich_runner.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from pymongo.database import Database

from app.core.mongodb import get_mongo_db
from app.services.db_service.learning_chat_log import update_weekly_log
from .llm import enrich_logs_with_llm

mongo_db: Database = get_mongo_db()
chat_col = mongo_db["learning_chat_logs"]

def compute_curriculum_insights_for_week(
    camp_id: int,
    week_start: datetime,
    week_end: datetime,
    batch_size: int = 20,
) -> None:
    """
    특정 캠프, 특정 주차 범위에 해당하는 로그들 중
    아직 curriculum_judge 필드가 없는 문서에 대해
    LLM으로 분류/패턴 태깅을 수행하고 MongoDB에 저장한다.
    """

    query = {
        "camp_id": camp_id,
        "created_at": {"$gte": week_start, "$lt": week_end},
        "curriculum_judge": {"$exists": False},
    }

    cursor = chat_col.find(query)

    batch: List[Dict[str, Any]] = []
    for doc in cursor:
        batch.append(doc)
        if len(batch) >= batch_size:
            compute_curriculum_insights_batch(batch)
            batch = []

    if batch:
        compute_curriculum_insights_batch(batch)

def compute_curriculum_insights_batch(batch_docs: List[Dict[str, Any]]) -> None:
    if not batch_docs:
        return

    enriched_list = enrich_logs_with_llm(batch_docs)
    if not enriched_list:
        return

    enriched_by_id = {str(item["id"]): item for item in enriched_list if "id" in item}

    for doc in batch_docs:
        doc_id_str = str(doc["_id"])
        info = enriched_by_id.get(doc_id_str)
        if not info:
            continue

        curriculum_topic = info.get("curriculum_topic") or "기타"
        curriculum_scope = "in" if info.get("curriculum_scope") == "in" else "out"
        pattern_tags = info.get("pattern_tags") or []
        intent = info.get("intent")

        data = {
            "curriculum_judge": {
                "topic": curriculum_topic,
                "scope": curriculum_scope,
                "pattern_tags": pattern_tags,
                "intent": intent,
            }
        }
        update_weekly_log(doc["_id"], data)