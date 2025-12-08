# app/services/db_service/attendance_report.py
from datetime import datetime
from typing import Optional
from pymongo.database import Database

from app.core.mongodb import get_mongo_db
from app.core.mongodb import AttendanceReport, AttendanceSummary, AttendanceStudentStat

mongo_db: Database = get_mongo_db()
report_col = mongo_db["attendance_reports"]


def get_attendance_report(
    camp_id: int,
    target_date: datetime.date,
) -> Optional[AttendanceReport]:
    doc =report_col.find_one(
        {
            "camp_id": camp_id,
            "target_date": target_date,  # date 타입 그대로 저장
        }
    )
    if not doc:
        return None
    return AttendanceReport(**doc)


def upsert_attendance_report(
    report: AttendanceReport,
) -> AttendanceReport:
    payload = report.model_dump()
    # payload["updated_at"] = datetime.utcnow()

    report_col.update_one(
        {
            "camp_id": report.camp_id,
            "target_date": report.target_date.isoformat(),
        },
        {"$set": payload},
        upsert=True,
    )
    return report