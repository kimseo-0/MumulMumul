# app/services/attendance/repository.py
from datetime import datetime, date
from typing import List
from sqlalchemy.orm import Session
from app.core.schemas import SessionActivityLog, User

def get_logs_for_period(
    db: Session,
    camp_id: int,
    start_date: date,
    end_date: date,
) -> List[SessionActivityLog]:
    return (
        db.query(SessionActivityLog)
        .join(User, SessionActivityLog.user_id == User.user_id)
        .filter(
            User.camp_id == camp_id,
            SessionActivityLog.join_at >= datetime.combine(start_date, datetime.min.time()),
            SessionActivityLog.join_at < datetime.combine(end_date, datetime.max.time()),
        )
        .all()
    )
