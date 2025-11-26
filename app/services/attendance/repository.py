# app/services/attendance/repository.py
from datetime import datetime, date
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.core.schemas import Camp, User, UserType, SessionActivityLog


def get_camp_and_students(db: Session, camp_id: int) -> Tuple[Camp | None, List[User]]:
    """
    캠프 1개 + 해당 캠프에 속한 '학생' 유저 목록만 조회
    """
    camp = db.query(Camp).filter(Camp.camp_id == camp_id).first()

    students = (
        db.query(User)
        .join(UserType, User.user_type_id == UserType.type_id)
        .filter(
            User.camp_id == camp_id,
            UserType.type_name == "학생",
        )
        .all()
    )

    return camp, students


def get_logs_for_period(
    db: Session,
    student_ids: List[int],
    start_date: date,
    end_date: date,
) -> List[SessionActivityLog]:
    """
    특정 학생들에 대한 기간 내 session_activity_log 전부 가져오기
    """
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    return (
        db.query(SessionActivityLog)
        .filter(
            SessionActivityLog.user_id.in_(student_ids),
            SessionActivityLog.join_at >= start_dt,
            SessionActivityLog.join_at <= end_dt,
        )
        .all()
    )
