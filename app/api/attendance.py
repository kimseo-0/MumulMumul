from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import Camp, User
from app.services.attendance.service import create_attendance_report
from app.services.attendance.schemas import AttendanceReportPayload  # 이미 만든 페이로드

router = APIRouter()

@router.get("/report", response_model=AttendanceReportPayload)
def get_attendance_report(
    camp_id: int = Query(..., description="리포트를 조회할 캠프 ID"),
    start_date: date = Query(..., description="분석 시작일 (YYYY-MM-DD)"),
    end_date: date = Query(..., description="분석 종료일 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """
    출결 리포트 생성 API
    - AttendanceReportPayload 그대로 리턴
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date 가 end_date 이후임")

    payload = create_attendance_report(
        db=db,
        camp_id=camp_id,
        start_date=start_date,
        end_date=end_date,
    )
    return payload