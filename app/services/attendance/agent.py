# app/services/attendance/agent.py

from datetime import date
from sqlalchemy.orm import Session

from app.services.attendance.service import build_attendance_structure
from app.services.attendance.llm import generate_ai_insights
from app.services.attendance.schemas import AttendanceReportPayload


def generate_attendance_report(
    db: Session,
    camp_id: int,
    start_date: date,
    end_date: date,
) -> AttendanceReportPayload:
    """
    1) 출결 통계를 집계하고
    2) LLM으로 ai_insights를 생성하여
    3) 최종 AttendanceReportPayload로 리턴
    """
    attendance_struct = build_attendance_structure(
        db=db,
        camp_id=camp_id,
        start_date=start_date,
        end_date=end_date,
    )

    ai_insights = generate_ai_insights(attendance_struct)

    payload = AttendanceReportPayload(
        summary_cards=attendance_struct["summary_cards"],
        charts=attendance_struct["charts"],
        tables=attendance_struct["tables"],
        ai_insights=ai_insights,
    )

    return payload
