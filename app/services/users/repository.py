from typing import List, Optional
from sqlalchemy.orm import Session
from app.core.schemas import User, UserType, Camp

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.user_id == user_id).first()

def get_users_by_camp(db: Session, camp_id: int) -> List[User]:
    return (
        db.query(User)
        .filter(User.camp_id == camp_id)
        .order_by(User.user_id)
        .all()
    )

def get_admins(db: Session) -> List[User]:
    return (
        db.query(User)
        .join(UserType, User.user_type_id == UserType.type_id)
        .filter(UserType.type_name == "운영진")
        .all()
    )
