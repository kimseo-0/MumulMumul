# app/services/attendance/calculator.py

from datetime import date, datetime, timedelta
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

    # --- 날짜 리스트 (월~금만) ---
    all_days: list[date] = []
    cur = start_date
    while cur <= end_date:
        if cur.weekday() < 5:
            all_days.append(cur)
        cur += timedelta(days=1)

    # --- 유저별 로그 묶기 ---
    logs_by_user: dict[int, list[SessionActivityLog]] = {sid: [] for sid in student_ids}
    for log in logs:
        if log.user_id in logs_by_user:
            logs_by_user[log.user_id].append(log)

    # --- 출석 여부 맵 (해당 날짜에 한 번이라도 접속하면 True) ---
    attendance_map: dict[int, dict[date, bool]] = {sid: {} for sid in student_ids}
    for log in logs:
        if log.user_id not in attendance_map:
            continue
        if not log.join_at:
            continue
        join_day = log.join_at.date()
        # 분석 기간 안에 들어오는 날만 표시
        if start_date <= join_day <= end_date and join_day in all_days:
            attendance_map[log.user_id][join_day] = True

    # --- 학생별 통계 ---
    today = end_date
    last7 = today - timedelta(days=6)

    # 7일 구간을 datetime 단위로 (세션 duration 계산용)
    last7_start_dt = datetime.combine(last7, datetime.min.time())
    today_end_dt = datetime.combine(today, datetime.max.time())

    student_rows: list[dict[str, Any]] = []
    for sid in student_ids:
        att = attendance_map[sid]
        present_days = [d for d in all_days if att.get(d)]
        total_days = len(all_days) or 1
        attendance_rate = len(present_days) / total_days

        # 최근 7일 접속일수
        days7 = sum(
            1
            for d in (last7 + timedelta(days=i) for i in range(7))
            if att.get(d)
        )

        # 최근 7일 온라인 시간(분) 계산
        total_seconds_7d = 0
        for log in logs_by_user.get(sid, []):
            if not log.join_at:
                continue
            start_dt = log.join_at
            end_dt = log.leave_at or log.join_at  # leave_at 없으면 0분 세션 처리

            # 7일 구간과 겹치지 않으면 스킵
            if end_dt < last7_start_dt or start_dt > today_end_dt:
                continue

            # 7일 구간으로 클램핑
            if start_dt < last7_start_dt:
                start_dt = last7_start_dt
            if end_dt > today_end_dt:
                end_dt = today_end_dt

            diff = (end_dt - start_dt).total_seconds()
            if diff > 0:
                total_seconds_7d += diff

        minutes_online_7d = int(total_seconds_7d // 60)

        # 리스크 레벨
        if attendance_rate >= 0.7 and days7 >= 4:
            risk = "정상"
        elif attendance_rate >= 0.4:
            risk = "주의"
        else:
            risk = "고위험"

        # 패턴 타입 (간이 버전)
        if attendance_rate >= 0.8:
            pattern_type = "안정적 고출석"
        elif attendance_rate <= 0.4:
            pattern_type = "저출석/이탈 위험"
        else:
            pattern_type = "중간 수준 출석"

        user = student_by_id[sid]

        student_rows.append(
            {
                "user_id": sid,
                "name": user.name,
                "class_id": camp.name if camp else "",
                "days_active_7d": days7,
                "minutes_online_7d": minutes_online_7d,
                # TODO: 회의/챗봇별 로그 테이블 분리되면 여기서 실제 값으로 계산
                "meetings_attended_7d": 0,
                "chatbot_questions_7d": 0,
                "risk_level": risk,
                "pattern_type": pattern_type,
            }
        )

    # --- 주차별 출석률 ---
    week_map: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for d in all_days:
        week = ((d - start_date).days // 7) + 1
        present_count = sum(
            1 for sid in student_ids if attendance_map[sid].get(d, False)
        )
        week_map[week][0] += present_count
        week_map[week][1] += len(student_ids)

    timeseries: list[dict[str, Any]] = []
    for week_idx in sorted(week_map.keys()):
        present, total = week_map[week_idx]
        rate = round(present * 100 / total) if total else 0
        timeseries.append(
            {
                "week_label": f"Week {week_idx}",
                "attendance_rate": rate,
            }
        )

    # --- summary cards ---
    avg_attendance = (
        sum(t["attendance_rate"] for t in timeseries) // len(timeseries)
        if timeseries
        else 0
    )

    num_low3 = sum(1 for r in student_rows if r["days_active_7d"] <= 3)
    num_risky = sum(1 for r in student_rows if r["risk_level"] == "고위험")
    num_warning = sum(1 for r in student_rows if r["risk_level"] == "주의")

    # --- top risk ---
    risk_rank = {"고위험": 2, "주의": 1, "정상": 0}
    top_risk = sorted(
        student_rows,
        key=lambda r: (risk_rank[r["risk_level"]], r["days_active_7d"]),
        reverse=True,
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
            "per_student_actions": [],  # 룰/LLM 붙이면 여기 채우기
        },
    }
