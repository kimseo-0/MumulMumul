# app/services/attendance/service.py

from datetime import date
from sqlalchemy.orm import Session

from app.services.attendance.repository import get_camp_and_students, get_logs_for_period
from app.services.attendance.calculator import calculate_attendance_struct
from app.services.attendance.agent import attach_ai_insights
from app.services.attendance.schemas import AttendanceReportPayload


def create_attendance_report(
    db: Session,
    camp_id: int,
    start_date: date,
    end_date: date,
) -> AttendanceReportPayload:

    # 1) DB → camp, students, logs
    camp, students = get_camp_and_students(db, camp_id)
    student_ids = [s.user_id for s in students]

    logs = get_logs_for_period(
        db=db,
        student_ids=student_ids,
        start_date=start_date,
        end_date=end_date,
    )

    # 2) 계산 로직 실행
    struct = calculate_attendance_struct(
        camp=camp,
        students=students,
        logs=logs,
        start_date=start_date,
        end_date=end_date,
    )

    # 3) agent 호출 → ai_insights 삽입
    ai_insight = attach_ai_insights(struct)

    struct['ai_insights'] = ai_insight

    # 4) 최종 Payload 생성
    return AttendanceReportPayload(**struct)
