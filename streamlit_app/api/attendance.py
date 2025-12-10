# streamlit_app/api/attendance.py
import datetime
import os
import requests

API_BASE = os.environ.get("MUMUL_API_BASE", "http://localhost:8020")


def get_camps():
    """캠프 리스트 가져오기"""
    return requests.get(f"{API_BASE}/attendance/camps").json()


def get_attendance_report(camp_id, target_date):
    resp = requests.get(
        f"{API_BASE}/attendance/report",
        params={"camp_id": camp_id, "target_date": target_date},
        timeout=10,
    )
    # resp.raise_for_status()
    return resp.json()

def generate_attendance_report(camp_id: int, target_date: datetime):
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