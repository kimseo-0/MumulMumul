# app/services/feedback_board/report_service.py

from typing import Dict, Any
from pymongo.database import Database

from app.services.feedbackBoard.generate_report.calculator import parse_posts, aggregate_feedback_stats
from .wordcloud import generate_wordclouds_per_category
from app.services.feedbackBoard.generate_report.llm import generate_feedback_ai_report

# app/services/feedback_board/service.py

from typing import List
from pymongo.database import Database
from datetime import datetime

from app.core.mongodb import FeedbackBoardPost, mongo_db
from app.services.feedbackBoard.analyze_feedback.llm import analyze_single_post

coll = mongo_db["feedback_board_posts"]

def attach_analysis_to_new_posts(camp_id: int) -> int:
    """
    아직 analysis / moderation 이 비어 있는 글들만 찾아서
    LLM으로 분석 결과를 채워준다.
    """

    cursor = coll.find({
        "camp_id": camp_id,
        "analysis.normalized_text": {"$in": [None, ""]},
    })

    updated = 0
    for doc in cursor:
        post = FeedbackBoardPost(**doc)
        result = analyze_single_post(post.raw_text)

        coll.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "analysis": result.analysis.model_dump(),
                    "moderation": result.moderation.model_dump(),
                }
            }
        )
        updated += 1

    return updated

def create_feedback_board_report(
    mongo_db: Database,
    camp_id: int,
    wordcloud_output_dir: str,
) -> Dict[str, Any]:
    # 0) 아직 분석 안 된 글들에 대해 analysis/moderation 채우기
    attach_analysis_to_new_posts(camp_id)

    # 1) 이 캠프의 모든 피드백 글 가져오기
    docs = list(coll.find({"camp_id": camp_id}))
    posts = parse_posts(docs)

    # 2) 집계/통계 생성
    stats = aggregate_feedback_stats(posts)

    # 3) 워드클라우드 이미지 생성
    wc_paths = generate_wordclouds_per_category(
        stats["wc_text_by_category"],
        output_dir=wordcloud_output_dir,
    )

    # 4) AI 기반 우선순위 + 액션 리포트 생성
    ai_report = generate_feedback_ai_report(stats)

    # 5) UI에서 바로 쓸 수 있는 payload로 구성
    summary = {
        "total_posts": stats["total_posts"],
        "toxic_count": stats["toxic_count"],
        "high_risk_count": stats["high_risk_count"],
        "posts_by_category": stats["posts_by_category"],
    }

    charts = {
        "wordcloud_paths": wc_paths,              # {category: path}
        "posts_by_category": stats["posts_by_category"],
    }

    # tables는 우선순위 Top3 리스트
    tables = {
        "priority_items": [
            item.model_dump() for item in ai_report.priority_items
        ]
    }

    ai_insights = ai_report.model_dump()

    return {
        "summary": summary,
        "charts": charts,
        "tables": tables,
        "ai_insights": ai_insights,
    }
