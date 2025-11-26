from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import Camp, User
from app.services.attendance.agent import generate_attendance_report
from app.services.attendance.schemas import AttendanceReportPayload  # 이미 만든 페이로드

router = APIRouter()

@router.get("/camps")
def list_camps(db: Session = Depends(get_db)):
    """
    캠프(반) 목록 조회 API
    - 별도 Pydantic 모델 없이 dict 리스트로 리턴
    """
    camps = db.query(Camp).order_by(Camp.camp_id.asc()).all()
    result = []
    for c in camps:
        result.append(
            {
                "camp_id": c.camp_id,
                "name": c.name,
                "start_date": c.start_date.date().isoformat() if c.start_date else None,
                "end_date": c.end_date.date().isoformat() if c.end_date else None,
            }
        )
    print("????????")
    print(result)
    return result


@router.get("/camps/{camp_id}/students")
def list_students_by_camp(
    camp_id: int,
    db: Session = Depends(get_db),
):
    """
    특정 캠프(반)의 유저(학생) 목록 조회 API
    - 이것도 dict 리스트로 심플하게
    """
    camp = db.query(Camp).filter(Camp.camp_id == camp_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="캠프를 찾을 수 없음")

    users = (
        db.query(User)
        .filter(User.camp_id == camp_id)
        .order_by(User.user_id.asc())
        .all()
    )

    result = []
    for u in users:
        result.append(
            {
                "user_id": u.user_id,
                "name": u.name,
                "login_id": u.login_id,
                "email": u.email,
                "camp_id": u.camp_id,
            }
        )
    return result


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

    payload = generate_attendance_report(
        db=db,
        camp_id=camp_id,
        start_date=start_date,
        end_date=end_date,
    )
    return payload