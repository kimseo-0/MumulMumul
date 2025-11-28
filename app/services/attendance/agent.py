# app/services/attendance/agent.py

from app.services.attendance.llm import generate_ai_insights


def attach_ai_insights(attendance_struct: dict) -> dict:
    """
    출결 구조(dict)에 ai_insights만 붙여서 dict로 반환.
    """
    insights = generate_ai_insights(attendance_struct)
    attendance_struct["ai_insights"] = insights
    return attendance_struct
