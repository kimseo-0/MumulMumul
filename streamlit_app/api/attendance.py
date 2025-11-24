import os
import requests
from datetime import date

API_BASE = os.environ.get("MUMUL_API_BASE", "http://localhost:8020")


def get_camps():
    """캠프 리스트 가져오기"""
    return requests.get(f"{API_BASE}/attendance/camps").json()


def get_attendance_report(camp_id: int, start_date: date, end_date: date):
    """출결 리포트 가져오기"""
    params = {
        "camp_id": camp_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    return requests.get(f"{API_BASE}/attendance/report", params=params).json()
