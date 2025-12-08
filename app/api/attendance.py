# app/api/attendance.py
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.attendance.service import generate_attendance_report
from app.services.db_service.attendance_report import get_attendance_report
from app.core.mongodb import AttendanceReport

router = APIRouter()

@router.get("/report", response_model=AttendanceReport)
def fetch_attendance_report(
    camp_id: int = Query(..., description="리포트를 조회할 캠프 ID"),
    target_date: date = Query(..., alias="target_date", description="리포트를 조회할 날짜"),
):
    """
    출결 리포트 조회 API
    """
    payload = get_attendance_report(
        camp_id=camp_id,
        target_date=target_date,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Attendance report not found")
    return payload


@router.post("/report/generate", response_model=AttendanceReport)
def create_attendance_report(
    camp_id: int = Query(..., description="리포트를 생성할 캠프 ID"),
    target_date: date = Query(..., alias="target_date", description="리포트를 생성할 날짜"),
    db: Session = Depends(get_db)
):
    """
    출결 리포트 생성 API
    """
    payload = generate_attendance_report(
        camp_id=camp_id,
        target_date=target_date,
        db=db,
    )
    return payload
