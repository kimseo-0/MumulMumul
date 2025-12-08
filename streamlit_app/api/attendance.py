# streamlit_app/api/attendance.py
import os
import requests
from datetime import date

API_BASE = os.environ.get("MUMUL_API_BASE", "http://localhost:8020")


def get_camps():
    """캠프 리스트 가져오기"""
    return requests.get(f"{API_BASE}/attendance/camps").json()


def get_attendance_report(camp_id: int, target_date: date):
    """출결 리포트 가져오기"""
    params = {
        "camp_id": camp_id,
        "target_date": target_date.isoformat(),
    }
    return requests.get(f"{API_BASE}/attendance/report", params=params)

def generate_attendance_report(camp_id: int, target_date: date):
    params = {
        "camp_id": camp_id,
        "target_date": target_date.isoformat(),  # "2025-01-10"
    }
    res = requests.post(
        f"{API_BASE}/attendance/report/generate",
        params=params, 
        timeout=10,
    )
    res.raise_for_status()
    return res.json()