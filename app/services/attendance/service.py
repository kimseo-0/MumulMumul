# app/services/attendance/service.py

from datetime import date, datetime
from typing import List

from fastapi import Depends
from sqlalchemy.orm import Session
from pymongo.database import Database

from app.core.db import get_db
from app.core.schemas import Camp, User, DailyAttendance
from app.core.mongodb import (
    AttendanceSummary,
    AttendanceStudentStat,
    AttendanceReport,
)
from app.services.db_service.attendance_report import (
    upsert_attendance_report,
)

from app.services.db_service.camp import (
    get_camp_by_id,
    get_students_by_camp,
)

FULL_DAY_MINUTES = 8 * 60

def _ensure_date(value: date | datetime) -> date:
    """datetime 이면 .date()로, 이미 date면 그대로 반환"""
    if isinstance(value, datetime):
        return value.date()
    return value

def _fetch_daily_attendance_for_range(
    db: Session,
    camp_id: int,
    start_date: date,
    end_date: date,
) -> List[DailyAttendance]:
    return (
        db.query(DailyAttendance)
        .filter(
            DailyAttendance.camp_id == camp_id,
            DailyAttendance.date >= start_date,
            DailyAttendance.date <= end_date,
        )
        .all()
    )


def _build_attendance_report_struct(
    camp: Camp,
    students: List[User],
    daily_rows: List[DailyAttendance],
    target_date: date,
) -> AttendanceReport:
    """
    SQL DailyAttendance → Mongo AttendanceReport
    - camp.start_date ~ target_date까지 누적 데이터를 이용
    """

    student_by_id = {s.user_id: s for s in students}
    days_set = {row.date for row in daily_rows}
    num_days = len(days_set) if days_set else 1

    student_stats: List[AttendanceStudentStat] = []

    for user_id, student in student_by_id.items():
        rows = [r for r in daily_rows if r.user_id == user_id]

        if not rows:
            attendance_rate = 0.0
            absent_count = num_days
            late_count = 0
            early_leave_count = 0
        else:
            total_ratio = 0.0
            absent_count = 0
            late_count = 0
            early_leave_count = 0

            for r in rows:
                day_ratio = min(r.total_minutes / float(FULL_DAY_MINUTES), 1.0)
                total_ratio += day_ratio

                if r.status == "결석":
                    absent_count += 1
                if r.status == "지각":
                    late_count += 1
                if r.status == "조퇴":
                    early_leave_count += 1

            attendance_rate = total_ratio / num_days

        if attendance_rate < 0.5 or absent_count >= 2:
            risk_level = "고위험"
        elif attendance_rate < 0.7 or absent_count == 1 or (late_count + early_leave_count) >= 3:
            risk_level = "위험"
        elif attendance_rate < 0.85 or (late_count + early_leave_count) >= 1:
            risk_level = "주의"
        else:
            risk_level = "정상"

        stat = AttendanceStudentStat(
            student_id=user_id,
            name=getattr(student, "name", f"수강생 {user_id}"),
            attendance_rate=attendance_rate,
            absent_count=absent_count,
            late_count=late_count,
            early_leave_count=early_leave_count,
            pattern_type=None,  # ✅ 나중에 LLM이 채울 부분
            risk_level=risk_level,
            trend=None,         # ✅ target_date 기준 N일 변화량 등
            ops_action=None,    # ✅ 개별 액션 제안 (LLM)
        )
        student_stats.append(stat)

    total_students = len(student_stats) or 1
    mean_attendance_rate = sum(s.attendance_rate for s in student_stats) / total_students

    high_risk_count = sum(1 for s in student_stats if s.risk_level == "고위험")
    warning_count = sum(
        1 for s in student_stats if s.risk_level in ("고위험", "위험", "주의")
    )

    total_late = sum(s.late_count for s in student_stats)
    late_rate = total_late / float(total_students * num_days) if num_days > 0 else 0.0

    summary = AttendanceSummary(
        attendance_rate=mean_attendance_rate,
        total_students=total_students,
        high_risk_count=high_risk_count,
        warning_count=warning_count,
        late_rate=late_rate,
    )

    report = AttendanceReport(
        camp_id=camp.camp_id,
        camp_name=camp.name,
        target_date=target_date,
        summary=summary,
        students=student_stats,
    )

    return report


def generate_attendance_report(
    camp_id: int,
    target_date: date,
    db: Session,
) -> AttendanceReport:
    """
    출결 리포트 생성/갱신
    - camp.start_date ~ target_date까지 누적 분석
    """
    camp: Camp = get_camp_by_id(db, camp_id)

    target = _ensure_date(target_date)
    camp_start = _ensure_date(camp.start_date)
    camp_end   = _ensure_date(camp.end_date)

    if not hasattr(camp, "start_date") or camp.start_date is None:
        raise ValueError("Camp.start_date가 설정되어 있지 않습니다.")

    # target_date가 캠프 기간 밖이면 클램핑(선택)
    if target < camp_start or target > camp_end:
        # 필요하면 HTTPException 으로 올려도 되고, ValueError 로 두고 상위에서 처리해도 됨
        raise ValueError(
            f"target_date {target} is out of camp range "
            f"({camp_start} ~ {camp_end})"
        )

    students: List[User] = get_students_by_camp(db, camp_id)
    daily_rows = _fetch_daily_attendance_for_range(db, camp_id, camp_start, camp_end)

    report = _build_attendance_report_struct(
        camp=camp,
        students=students,
        daily_rows=daily_rows,
        target_date=target_date,
    )

    upsert_attendance_report(report)
    return report
