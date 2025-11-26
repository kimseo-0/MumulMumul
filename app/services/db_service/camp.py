# app/services/common/repository.py

from sqlalchemy.orm import Session
from app.core.schemas import Camp


def get_camp_by_id(db: Session, camp_id: int) -> Camp | None:
    """
    camp_id로 Camp 객체 1개를 조회하는 가장 기본적인 Repository 함수.
    """
    return db.query(Camp).filter(Camp.camp_id == camp_id).first()


def get_camp_name_by_id(db: Session, camp_id: int) -> str | None:
    """
    camp_id → camp_name만 가져오는 helper repo.
    """
    camp = db.query(Camp).filter(Camp.camp_id == camp_id).first()
    return camp.name if camp else None
