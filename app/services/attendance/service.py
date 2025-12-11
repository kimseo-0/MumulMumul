# app/services/attendance/service.py

from datetime import datetime, timedelta
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

from datetime import datetime, timedelta, time
from typing import List
from sqlalchemy.orm import Session
from app.core.schemas import User, DailyAttendance  # 상단 import 정리 추천


def build_daily_attendance(
    db: Session,
    camp_id: int,
    target_dt: datetime,
    students: List[User],
):
    from app.core.schemas import SessionActivityLog, DailyAttendance

    results = []

    # 날짜 기준점: 해당 날짜의 00:00:00 ~ 다음날 00:00:00
    day_start = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    # 기준 시간
    start_time = time(9, 0, 0)
    end_time = time(18, 0, 0)
    FULL_DAY_MINUTES = 8 * 60

    for student in students:
        logs = (
            db.query(SessionActivityLog)
            .filter(
                SessionActivityLog.user_id == student.user_id,
                SessionActivityLog.join_at >= day_start,
                SessionActivityLog.join_at < day_end,
            )
            .all()
        )

        if not logs:
            # 결석
            daily = DailyAttendance(
                user_id=student.user_id,
                camp_id=camp_id,
                date=day_start,        # ✅ 항상 00:00:00 로 normalize 된 datetime
                status="결석",
                total_minutes=0,
            )
            db.add(daily)
            results.append(daily)
            continue

        # 그날 가장 빠른 입실 / 마지막 퇴실
        join_at = min(log.join_at for log in logs)
        leave_at = max(log.leave_at for log in logs)

        total_minutes = int((leave_at - join_at).total_seconds() // 60)

        # 상태 판단
        if total_minutes <= 0:
            status = "결석"
        elif join_at.time() > start_time:
            status = "지각"
        elif leave_at.time() < end_time:
            status = "조퇴"
        else:
            # Enum에 "정상" 없으면 None으로 두는 게 안전
            status = "정상"

        daily = DailyAttendance(
            user_id=student.user_id,
            camp_id=camp_id,
            date=day_start,
            status=status,
            total_minutes=total_minutes,
            morning_minutes=0,    # 추후 개선 가능
            afternoon_minutes=0,  # 추후 개선 가능
            note="",
        )
        db.add(daily)
        results.append(daily)

    db.commit()
    return results

from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from app.core.schemas import DailyAttendance
from app.services.db_service.camp import get_students_by_camp


def _fetch_daily_attendance_for_range(
    db: Session,
    camp_id: int,
    start_date: datetime,
    end_date: datetime,
) -> List[DailyAttendance]:
    # 기준일을 모두 00:00:00 로 normalize
    start_dt = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1) 기존 DailyAttendance 가져오기
    rows = (
        db.query(DailyAttendance)
        .filter(
            DailyAttendance.camp_id == camp_id,
            DailyAttendance.date >= start_dt,
            DailyAttendance.date <= end_dt,
        )
        .all()
    )

    # 해당 기간의 모든 날짜(datetime, 00:00:00) 리스트
    date_range = [
        start_dt + timedelta(days=i)
        for i in range((end_dt - start_dt).days + 1)
    ]

    # 2) 캠프 학생 목록
    students = get_students_by_camp(db, camp_id)

    # 3) 날짜별 누락된 데이터 생성
    #    DailyAttendance.date도 datetime이므로, 같은 날짜는 00:00:00으로 맞춰서 키 생성
    existing_dates = {
        datetime.combine(row.date, datetime.min.time())
        for row in rows
    }

    for day_start in date_range:
        if day_start not in existing_dates:
            # DailyAttendance 자동 생성 (해당 날짜 전체)
            new_rows = build_daily_attendance(
                db=db,
                camp_id=camp_id,
                target_dt=day_start,
                students=students,
            )
            rows.extend(new_rows)

    return rows


def _build_attendance_report_struct(
    camp: Camp,
    students: List[User],
    daily_rows: List[DailyAttendance],
    target_date: datetime,
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
    target_date: datetime,
    db: Session,
) -> AttendanceReport:
    """
    출결 리포트 생성/갱신
    - camp.start_date ~ target_date까지 누적 분석
    """
    camp: Camp = get_camp_by_id(db, camp_id)

    if not hasattr(camp, "start_date") or camp.start_date is None:
        raise ValueError("Camp.start_date가 설정되어 있지 않습니다.")

    # target_date가 캠프 기간 밖이면 클램핑(선택)
    if target_date < camp.start_date or target_date > camp.end_date:
        # 필요하면 HTTPException 으로 올려도 되고, ValueError 로 두고 상위에서 처리해도 됨
        raise ValueError(
            f"target_date {target_date} is out of camp range "
            f"({camp.start_date} ~ {camp.end_date})"
        )

    students: List[User] = get_students_by_camp(db, camp_id)
    daily_rows = _fetch_daily_attendance_for_range(db, camp_id, camp.start_date, camp.end_date)

    report = _build_attendance_report_struct(
        camp=camp,
        students=students,
        daily_rows=daily_rows,
        target_date=target_date,
    )

    upsert_attendance_report(report)
    return report
