
from datetime import datetime

from requests import Session
from app.core.mongodb import FeedbackBoardPost, mongo_db

from app.core.schemas import Camp
from app.services.db_service.camp import get_camp_by_user_id

feedback_col = mongo_db["feedback_board_posts"]

def add_feedback_post(db: Session, user_id: int, raw_text: str) -> FeedbackBoardPost:
    """
    새로운 피드백 게시글을 생성하여 MongoDB에 저장합니다.
    """
    camp: Camp = get_camp_by_user_id(db, user_id)

    new_post = FeedbackBoardPost(
        camp_id=camp.camp_id if camp else None,
        author_id=user_id,
        raw_text=raw_text,
        created_at=datetime.utcnow(),
    )
    result = feedback_col.insert_one(new_post.model_dump())
    new_post.id = result.inserted_id
    return new_post

# moderation 및 analysis 필드 업데이트 함수 등 추가 가능
def update_feedback_post_analysis(
    post_id: str,
    analysis: dict,
    moderation: dict,
) -> None:
    """
    특정 피드백 게시글의 분석 및 검열 결과를 업데이트합니다.
    """
    feedback_col.update_one(
        {"_id": post_id},
        {
            "$set": {
                "analysis": analysis,
                "moderation": moderation,
            }
        }
    )