# app/api/user_router.py

import sys
sys.path.append("../..")

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.schemas import User, TendencyProfile, UserType
from app.core.db import get_db

router = APIRouter()


# ===========================
# Pydantic Schemas
# ===========================
class LoginRequest(BaseModel):
    loginId: str
    password: str


class LoginResponse(BaseModel):
    userId: int
    name: str
    campId: Optional[int] = None
    userType: str
    tendencyCompleted: bool


class SurveyResultRequest(BaseModel):
    userId: int
    typeCode: str
    profileSummary: Optional[str] = None


class SurveyResultResponse(BaseModel):
    userId: int
    typeCode: str
    saved: bool


class SurveyStatusResponse(BaseModel):
    userId: int
    hasResult: bool
    typeCode: Optional[str] = None
    profileSummary: Optional[str] = None


# ===========================
# API Endpoints
# ===========================

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    로그인 + 성향분석 완료 여부 반환
    """
    user: User | None = (
        db.query(User)
        .join(UserType)
        .filter(User.login_id == payload.loginId)
        .first()
    )

    if not user or not payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "errorCode": "LOGIN_FAILED",
                "message": "아이디 또는 비밀번호가 잘못되었습니다.",
            },
        )

    return LoginResponse(
        userId=user.user_id,
        name=user.name,
        userType=user.user_type.type_name,
        campId=user.camp_id,
        tendencyCompleted=bool(user.tendency_completed),
    )