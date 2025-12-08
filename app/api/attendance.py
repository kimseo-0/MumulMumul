from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import Camp, User
from app.services.attendance.service import generate_attendance_report
from app.services.db_service.attendance_report import get_attendance_report
from app.core.mongodb import AttendanceReport

router = APIRouter()

@router.get("/report", response_model=AttendanceReport)
def fetch_attendance_report(
    camp_id: int = Query(..., description="리포트를 조회할 캠프 ID"),
    date = Query(..., description="리포트를 생성할 날짜"),
    db: Session = Depends(get_db),
):
    """
    출결 리포트 조회 API
    - AttendanceReportPayload 그대로 리턴
    """
    payload = get_attendance_report(
        camp_id=camp_id,
        date=date,
    )
    return payload

@router.get("/report/generate", response_model=AttendanceReport)
def create_attendance_report(
    camp_id: int = Query(..., description="리포트를 조회할 캠프 ID"),
    date = Query(..., description="리포트를 생성할 날짜"),
    db: Session = Depends(get_db),
):
    """
    출결 리포트 생성 API
    - AttendanceReportPayload 그대로 리턴
    """
    payload = generate_attendance_report(
        db=db,
        camp_id=camp_id,
        date=date,
    )
    return payload