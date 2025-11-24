from typing import List, Optional
from sqlalchemy.orm import Session
from app.core.schemas import User
from .repository import get_user_by_id, get_users_by_camp

def login(id, password):
    return True

def get_student_list_by_camp(db: Session, camp_id: int) -> List[User]:
    """출결/리포트에서 사용할 '해당 캠프 학생 목록'"""
    return get_users_by_camp(db, camp_id)

def find_user_profile(db: Session, user_id: int) -> Optional[User]:
    """유저 상세 정보 조회 (나중에 성향 등 묶어서 확장 가능)"""
    return get_user_by_id(db, user_id)
