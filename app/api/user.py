# app/api/user_router.py

import sys

sys.path.append("../..")

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.schemas import User, UserType
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
    tendencyTypeCode: Optional[int] = None

class SurveyResultRequest(BaseModel):
    # 성향 분석 문항 응답 저장
    userId: int
    result: list[int]

class SurveyResultResponse(BaseModel):
    userId: int
    typeCode: str


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
        tendencyTypeCode=user.tendency_type_code,
    )

import json
from pathlib import Path
from app.config import PERSONAL_SURVEY_CONFIG_PATH

def load_trait_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def calculate_personality_type(result, config):
    questions = config["questions"]

    # 1) 총점 계산
    score = 0
    for i, user_choice in enumerate(result):
        choice_value = questions[i]["choices"][user_choice]["value"]
        score += choice_value

    # 2) 점수 구간에 따른 캐릭터 매핑
    if score >= 27:
        type_code = "analyst"       # 2.6 초과 (27~30)
    elif score >= 23:
        type_code = "pillar"        # 2.2 초과 ~ 2.6 이하 (23~26)
    elif score >= 19:
        type_code = "balancer"      # 1.8 초과 ~ 2.2 이하 (19~22)
    elif score >= 15:
        type_code = "supporter"     # 1.4 초과 ~ 1.8 이하 (15~18)
    else:
        type_code = "doer"          # 1.4 이하 (10~14)

    return type_code, score

@router.get("/survey", response_model=dict)
def get_survey_questions():
    """
    personal_survey.json 기반 성향 분석 문항 반환
    """
    personal_survey_config = load_trait_config(PERSONAL_SURVEY_CONFIG_PATH)
    return {
        "characters": personal_survey_config["characters"],
        "questions": personal_survey_config["questions"]
    }


@router.post("/survey-result", response_model=SurveyResultResponse)
def submit_survey_result(payload: SurveyResultRequest, db: Session = Depends(get_db)):
    """
    personal_survey.json 기반 성향 분석 결과 저장
    점수대별로 type_code 부여 (analyst, doer, balancer, supporter, pillar)
    """
    user = db.query(User).filter(User.user_id == payload.userId).first()

    personal_survey_config = load_trait_config(PERSONAL_SURVEY_CONFIG_PATH)

    result = payload.result

    if len(result) != len(personal_survey_config["questions"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "errorCode": "INVALID_SURVEY_RESULT",
                "message": "설문 문항 수와 응답 수가 일치하지 않습니다.",
            }
        )

    type_code, score = calculate_personality_type(result, personal_survey_config)

    user.tendency_completed = 1
    user.tendency_type_code = type_code
    db.commit()

    return SurveyResultResponse(
        userId=user.user_id,
        typeCode=type_code,
    )

