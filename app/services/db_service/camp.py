# app/services/common/repository.py

from typing import List
from sqlalchemy.orm import Session
from app.core.schemas import Camp, User

def get_students_by_camp(db: Session, camp_id: int) -> List[User] | None:
    """
    캠프에 속한 모든 User 객체 리스트를 조회하는 Repository 함수.
    """
    camp = get_camp_by_id(db, camp_id)
    if not camp:
        return None
    
    users = (
        db.query(User)
        .join(Camp.users)
        .filter(Camp.camp_id == camp_id)
        .all()
    )
    return users

def get_camp_by_id(db: Session, camp_id: int) -> Camp | None:
    """
    camp_id로 Camp 객체 1개를 조회하는 가장 기본적인 Repository 함수.
    """
    return db.query(Camp).filter(Camp.camp_id == camp_id).first()
    
def get_camp_by_user_id(db: Session, user_id: int) -> Camp | None:
    """
    user_id로 Camp 객체 1개를 조회하는 Repository 함수.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return None
    return user.camp
    