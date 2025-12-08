# app/services/feedback_board/calculator.py

from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

from app.core.mongodb import FeedbackBoardPost


def parse_posts(docs: List[Dict[str, Any]]) -> List[FeedbackBoardPost]:
    return [FeedbackBoardPost(**d) for d in docs]


def aggregate_feedback_stats(posts: List[FeedbackBoardPost]) -> Dict[str, Any]:
    """
    2, 3, 4번을 위한 기반 통계/텍스트 집계
    """

    total_posts = len(posts)

    # 카테고리별 카운트
    category_counter = Counter()
    # 위험도 / 독성 카운트
    toxic_count = 0
    high_risk_count = 0

    # 카테고리별 텍스트(워드클라우드용)
    wc_text_by_category: Dict[str, List[str]] = defaultdict(list)

    # 우선순위 산정용 (importance_score + risk_level)
    priority_candidates: List[Dict[str, Any]] = []

    for p in posts:
        cat = p.analysis.category
        category_counter[cat] += 1

        if p.moderation.is_toxic:
            toxic_count += 1
        if p.moderation.risk_level == "high":
            high_risk_count += 1

        # 워드클라우드는 안전한 텍스트만 사용하는게 좋음
        if not p.moderation.is_toxic and not p.moderation.has_realname:
            wc_text_by_category[cat].append(
                p.analysis.normalized_text or p.raw_text
            )

        # 우선순위 후보 저장
        priority_candidates.append(
            {
                "id": str(p.id),
                "category": cat,
                "raw_text": p.raw_text,
                "normalized_text": p.analysis.normalized_text,
                "topic_tags": p.analysis.topic_tags,
                "importance_score": p.analysis.importance_score,
                "risk_level": p.moderation.risk_level,
            }
        )

    # 카테고리별 카운트 정리
    posts_by_category = [
        {"category": cat, "count": cnt}
        for cat, cnt in category_counter.most_common()
    ]

    return {
        "total_posts": total_posts,
        "posts_by_category": posts_by_category,
        "toxic_count": toxic_count,
        "high_risk_count": high_risk_count,
        "wc_text_by_category": wc_text_by_category,
        "priority_candidates": priority_candidates,
    }
