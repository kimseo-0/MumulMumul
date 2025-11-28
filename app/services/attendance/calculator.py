# app/services/attendance/calculator.py

from datetime import date, timedelta
from collections import defaultdict
from typing import List, Dict, Any

from app.core.schemas import Camp, User, SessionActivityLog


def calculate_attendance_struct(
    camp: Camp | None,
    students: List[User],
    logs: List[SessionActivityLog],
    start_date: date,
    end_date: date,
) -> Dict[str, Any]:

    student_ids = [s.user_id for s in students]
    student_by_id = {s.user_id: s for s in students}

    # --- 날짜 리스트 ---
    all_days = []
    cur = start_date
    while cur <= end_date:
        if cur.weekday() < 5:
            all_days.append(cur)
        cur += timedelta(days=1)

    # --- 출석 여부 ---
    attendance_map = {sid: {} for sid in student_ids}
    for log in logs:
        attendance_map[log.user_id][log.join_at.date()] = True

    # --- 학생별 통계 ---
    today = end_date
    last7 = today - timedelta(days=6)

    student_rows = []
    for sid in student_ids:
        att = attendance_map[sid]
        present_days = [d for d in all_days if att.get(d)]
        total_days = len(all_days) or 1
        attendance_rate = len(present_days) / total_days

        days7 = sum(
            1 for d in (last7 + timedelta(days=i) for i in range(7))
            if att.get(d)
        )

        if attendance_rate >= 0.7 and days7 >= 4:
            risk = "정상"
        elif attendance_rate >= 0.4:
            risk = "주의"
        else:
            risk = "고위험"

        if attendance_rate >= 0.8:
            pattern_type = "안정적 고출석"
        elif attendance_rate <= 0.4:
            pattern_type = "저출석/이탈 위험"
        else:
            pattern_type = "중간 수준 출석"

        user = student_by_id[sid]

        student_rows.append({
            "user_id": sid,
            "name": user.name,
            "class_id": camp.name if camp else "",
            "days_active_7d": days7,
            "risk_level": risk,
            "pattern_type": pattern_type,
        })

    # --- 주차별 출석률 ---
    week_map = defaultdict(lambda: [0, 0])
    for d in all_days:
        week = ((d - start_date).days // 7) + 1
        present_count = sum(attendance_map[sid].get(d, False) for sid in student_ids)
        week_map[week][0] += present_count
        week_map[week][1] += len(student_ids)

    timeseries = []
    for week_idx in sorted(week_map.keys()):
        present, total = week_map[week_idx]
        rate = round(present * 100 / total) if total else 0
        timeseries.append({
            "week_label": f"Week {week_idx}",
            "attendance_rate": rate,
        })

    # --- summary cards ---
    avg_attendance = (
        sum(t["attendance_rate"] for t in timeseries) // len(timeseries)
        if timeseries else 0
    )

    num_low3 = sum(1 for r in student_rows if r["days_active_7d"] <= 3)
    num_risky = sum(1 for r in student_rows if r["risk_level"] == "고위험")
    num_warning = sum(1 for r in student_rows if r["risk_level"] == "주의")

    # --- top risk ---
    risk_rank = {"고위험": 2, "주의": 1, "정상": 0}
    top_risk = sorted(
        student_rows,
        key=lambda r: (risk_rank[r["risk_level"]], r["days_active_7d"]),
        reverse=True
    )[:3]

    return {
        "summary_cards": {
            "avg_attendance_rate": avg_attendance,
            "num_low_access_3days": num_low3,
            "num_risky": num_risky,
            "num_warning": num_warning,
        },
        "charts": {
            "attendance_timeseries": timeseries,
        },
        "tables": {
            "top_risk_students": top_risk,
            "student_list": student_rows,
            "per_student_actions": [],
        },
    }
