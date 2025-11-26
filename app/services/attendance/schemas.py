from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# -----------------------------
# 1) 하위 단위 모델들
# -----------------------------
class SummaryCards(BaseModel):
    """상단 metric 카드 4개"""
    avg_attendance_rate: int = Field(..., description="평균 출석률(%)")
    num_low_access_3days: int = Field(..., description="최근 7일 중 접속일수 3일 이하 인원 수")
    num_risky: int = Field(..., description="고위험 학습자 수")
    num_warning: int = Field(..., description="주의 학습자 수")


class AttendanceTimeseriesPoint(BaseModel):
    """주차별 출석률 시계열 포인트"""
    week_label: str = Field(..., description="예: 'Week 1'")
    attendance_rate: int = Field(..., description="해당 주차 출석률(%)")


class TopRiskStudentRow(BaseModel):
    """위험 학습자 상위 N명 리스트 row"""
    user_id: int
    name: str
    class_id: str
    days_active_7d: int = Field(..., description="최근 7일 접속일수")
    risk_level: Literal["정상", "주의", "고위험"]


class StudentRow(BaseModel):
    """전체 학습자 리스트 row"""
    user_id: int
    name: str
    class_id: str
    days_active_7d: int
    minutes_online_7d: int
    meetings_attended_7d: int
    chatbot_questions_7d: int
    risk_level: Literal["정상", "주의", "고위험"]
    pattern_type: str = Field(
        ...,
        description="예: '안정적 고참여형', '고활동→급감형', '형식적 출석형', '저활동-지속형' 등",
    )


class PerStudentActionRow(BaseModel):
    """개별 학습자 액션 제안 row"""
    user_id: int
    name: str
    risk_level: Literal["정상", "주의", "고위험"]
    pattern_type: str
    recommended_action: str
    priority: Literal["high", "medium", "low"]
    suggested_channel: Literal["DM", "이메일", "1:1 미팅", "기타"]


# -----------------------------
# 2) charts / tables / ai_insights
# -----------------------------
class Charts(BaseModel):
    attendance_timeseries: List[AttendanceTimeseriesPoint]


class Tables(BaseModel):
    top_risk_students: List[TopRiskStudentRow]
    student_list: List[StudentRow]
    per_student_actions: List[PerStudentActionRow]

class AIInsights(BaseModel):
    """
    출결 리포트에서 LLM이 생성할 텍스트 요약 영역.
    말투는 보고서형(~임/~함 체)로 작성하도록 유도함.
    """

    summary_one_line: str = Field(
        ...,
        description="이 반의 출석/참여 상황을 한 문장으로 요약한 문장.",
        max_length=200,
    )

    attendance_summary: str = Field(
        ...,
        description=(
            "분석 기간 동안의 출석률 흐름과 특징을 정리한 본문.\n"
            "- 주차별 출석률 변동, 평균 출석률, 특징적인 구간 등을 포함.\n"
            "말투는 '~임/~함' 체."
        ),
        max_length=1200,
    )

    risk_signals_summary: str = Field(
        ...,
        description=(
            "고위험/주의 학습자와 최근 7일 저활동 인원을 중심으로 이탈 위험 신호를 정리한 본문.\n"
            "말투는 '~임/~함' 체."
        ),
        max_length=1200,
    )

    short_term_actions: str = Field(
        ...,
        description=(
            "1~2주 안에 실행할 수 있는 구체적인 액션 리스트.\n"
            "- 각 줄은 '- ' 로 시작하는 불릿 리스트 형태.\n"
            "말투는 '~함' 체."
        ),
    )

    mid_term_actions: str = Field(
        ...,
        description=(
            "3주 이상을 바라보고 설계할 중기 개선 방향.\n"
            "- 각 줄은 '- ' 로 시작하는 불릿 리스트 형태.\n"
            "말투는 '~함' 체."
        ),
    )

# -----------------------------
# 3) 최상위 Payload 모델
# -----------------------------
class AttendanceReportPayload(BaseModel):
    summary_cards: SummaryCards
    charts: Charts
    tables: Tables
    ai_insights: AIInsights


# -----------------------------
# 4) 사용 예시
# -----------------------------
if __name__ == "__main__":
    attendance_report_payload = {
        "summary_cards": {
            # 화면 상단 metric 카드 4개에 들어갈 핵심 숫자 요약
            "avg_attendance_rate": 82,      # 현재 기간 기준 평균 출석률(%)
            "num_low_access_3days": 5,      # 최근 7일 동안 접속일수 3일 이하인 학습자 수
            "num_risky": 3,                 # 고위험(risk_level='고위험') 학습자 수
            "num_warning": 4,               # 주의(risk_level='주의') 학습자 수
        },

        "charts": {
            # Altair 그래프에 바로 넣을 수 있는 시계열/분포 데이터들
            "attendance_timeseries": [
                # 주차별 출석률 시계열 (라인 그래프용)
                {"week_label": "Week 1", "attendance_rate": 88},
                {"week_label": "Week 2", "attendance_rate": 86},
                {"week_label": "Week 3", "attendance_rate": 84},
                # ...
            ],
            # 필요하면 나중에 다른 차트들도 추가 가능:
            # "daily_activity_timeseries": [...],
            # "class_comparison": [...],
        },

        "tables": {
            # 화면에 표로 보여줄 데이터들 모음

            "top_risk_students": [
                # 위험 학습자 상위 N명 (예: 3명)
                # 요약 탭의 "위험 학생 리스트" + AI 인사이트 일부에서 같이 사용
                {
                    "user_id": 2,
                    "name": "이서연",
                    "class_id": "2반",
                    "days_active_7d": 2,   # 최근 7일 접속일수
                    "risk_level": "고위험",
                },
                # ...
            ],

            "student_list": [
                # 반 기준 전체 학습자 리스트 (필터링 후)
                # 출결/참여 관련 상세 테이블을 구성하는 핵심 지표 포함
                {
                    "user_id": 1,
                    "name": "김지훈",
                    "class_id": "1반",
                    "days_active_7d": 6,          # 최근 7일 접속일수
                    "minutes_online_7d": 540,     # 최근 7일 총 접속 시간(분)
                    "meetings_attended_7d": 5,    # 최근 7일 회의 참석 횟수
                    "chatbot_questions_7d": 9,    # 최근 7일 챗봇 질문 수
                    "risk_level": "정상",         # 정상 / 주의 / 고위험
                    "pattern_type": "안정적 고참여형",  # 고활동→급감형 / 형식적 출석형 / 저활동-지속형 등
                },
                # ...
            ],

            "per_student_actions": [
                # AI가 생성한 개별 학습자 액션 제안
                # 보통은 주의/고위험 학습자 위주로 노출
                {
                    "user_id": 2,
                    "name": "이서연",
                    "risk_level": "고위험",
                    "pattern_type": "고활동→급감형",
                    "recommended_action": (
                        "이탈 전 단계로 판단됨. 안부 중심의 1:1 메시지로 최근 어려움을 확인하고, "
                        "필요시 과제·일정 조정을 함께 논의하는 것이 필요함."
                    ),
                    "priority": "high",        # high / medium / low 등 우선순위
                    "suggested_channel": "DM", # DM / 이메일 / 1:1 미팅 등
                },
                # ...
            ],
        },

        "ai_insights": {
            # 반(코호트) 단위로 LLM이 생성한 텍스트 요약들

            "summary_one_line": (
                "출석률은 유지되지만 최근 일주일간 활동 급감이 일부 확인되는 반임."
            ),  # 가장 짧은 핵심 한 줄 요약

            "attendance_summary": (
                "지난 6주간 평균 출석률은 82% 수준으로 안정적임. "
                "다만 특정 주차 이후 일부 학습자의 접속일수와 회의 참석이 점진적으로 감소하는 패턴이 관찰됨."
            ),  # 출석/참여 경향 전체 설명

            "risk_signals_summary": (
                "최근 7일 기준 3일 이하 접속 학습자가 5명 존재하며, "
                "이 중 3명은 고위험으로 분류됨. "
                "이 구간에서 이탈 가능성이 높아 면밀한 모니터링이 필요함."
            ),  # 주의 신호/이탈 신호 요약

            "short_term_actions": (
                "- 고위험 학습자 3명을 우선 케어 대상으로 지정하고, 이번 주 내 1:1 안부 확인을 진행함.\n"
                "- 3일 이하 접속 학습자에게는 '이번 주 3일 접속'과 같은 작은 목표를 제안함.\n"
                "- 회의 참여 문턱을 낮추기 위해 음성/채팅 기반 참여도 허용함."
            ),  # 당장 1~2주 내 실행할 액션

            "mid_term_actions": (
                "- 특정 주차 이후 반복적으로 출석률이 떨어지는 구간이 있는지 확인하고, 해당 구간의 커리큘럼 난이도와 과제량을 점검함.\n"
                "- 반별로 2~4주 간격의 정기 상태 점검 미팅(리더/멘토 동반)을 도입하는 것을 검토함.\n"
                "- 장기간 저활동-지속형 학습자를 위한 별도 트랙(보충 세션·요약 자료 제공 등)을 설계함."
            ),  # 3주~이상 중기 전략
        },
    }

    payload = AttendanceReportPayload(**attendance_report_payload)
    print(payload)
