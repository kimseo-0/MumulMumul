from datetime import datetime, date, timedelta
from collections import defaultdict

from sqlalchemy.orm import Session
from app.core.schemas import User, UserType, Camp, SessionActivityLog


def build_attendance_structure(db: Session, camp_id: int, start_date: date, end_date: date):
    # 1) 캠프 & 학생 목록 가져오기
    camp = db.query(Camp).filter(Camp.camp_id == camp_id).first()
    students = db.query(User).join(
        UserType, User.user_type_id == UserType.type_id
        ).filter(
        User.camp_id == camp_id,
        UserType.type_name == "학생").all()
    student_ids = [s.user_id for s in students]
    student_by_id = {s.user_id: s for s in students}

    # 2) 기간 내 출결 로그 가져오기
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    logs = (
        db.query(SessionActivityLog)
        .filter(
            SessionActivityLog.user_id.in_(student_ids),
            SessionActivityLog.join_at >= start_dt,
            SessionActivityLog.join_at <= end_dt,
        )
        .all()
    )

    # 3) 날짜 리스트 (평일만)
    all_days = []
    cur = start_date
    while cur <= end_date:
        if cur.weekday() < 5:  # 0~4: 평일
            all_days.append(cur)
        cur += timedelta(days=1)

    # 4) 학생별 날짜별 출석 여부 기록
    #    attendance_map[student_id][date] = True/False
    attendance_map = {sid: {} for sid in student_ids}
    for log in logs:
        d = log.join_at.date()
        attendance_map[log.user_id][d] = True

    # 5) 학생별 출석률 / 최근 7일 접속일수 / 위험도, 패턴 타입 계산
    today = end_date
    last7_start = today - timedelta(days=6)

    student_rows = []

    for sid in student_ids:
        att_by_day = attendance_map[sid]

        # 전체 기간 출석일 수
        present_days = [d for d in all_days if att_by_day.get(d, False)]
        total_days = len(all_days) if len(all_days) > 0 else 1
        attendance_rate = len(present_days) / total_days  # 0~1

        # 최근 7일 접속일수
        days_active_7d = 0
        cur = last7_start
        while cur <= today:
            if att_by_day.get(cur, False):
                days_active_7d += 1
            cur += timedelta(days=1)

        # 아주 단순한 규칙 기반 위험도
        if attendance_rate >= 0.7 and days_active_7d >= 4:
            risk_level = "정상"
        elif attendance_rate >= 0.4:
            risk_level = "주의"
        else:
            risk_level = "고위험"

        # 간단 패턴 라벨
        if attendance_rate >= 0.8:
            pattern_type = "안정적 고출석"
        elif attendance_rate <= 0.4:
            pattern_type = "저출석/이탈 위험"
        else:
            pattern_type = "중간 수준 출석"

        stu = student_by_id[sid]

        student_rows.append(
            {
                "user_id": sid,
                "name": stu.name,
                "class_id": camp.name if camp else "",
                "days_active_7d": days_active_7d,
                "minutes_online_7d": 0,      # 나중에 회의/시간 계산 붙일 예정
                "meetings_attended_7d": 0,   # 나중에 추가
                "chatbot_questions_7d": 0,   # 나중에 추가
                "risk_level": risk_level,
                "pattern_type": pattern_type,
            }
        )

    # 6) 주차별 출석률 타임시리즈 (Week 1, Week 2 ...)
    week_buckets = defaultdict(lambda: [0, 0])  # week_idx -> [present_sum, total_slots]

    for d in all_days:
        week_idx = ((d - start_date).days // 7) + 1
        present_cnt = 0
        for sid in student_ids:
            if attendance_map[sid].get(d, False):
                present_cnt += 1
        week_buckets[week_idx][0] += present_cnt
        week_buckets[week_idx][1] += len(student_ids)

    timeseries = []
    for week_idx in sorted(week_buckets.keys()):
        present_sum, total_slots = week_buckets[week_idx]
        if total_slots == 0:
            rate = 0
        else:
            rate = round(100 * present_sum / total_slots)
        timeseries.append(
            {
                "week_label": f"Week {week_idx}",
                "attendance_rate": rate,
            }
        )

    # 7) summary_cards / top_risk_students 집계
    if len(timeseries) > 0:
        avg_attendance_rate = sum(t["attendance_rate"] for t in timeseries) // len(timeseries)
    else:
        avg_attendance_rate = 0

    num_low_access_3days = sum(1 for r in student_rows if r["days_active_7d"] <= 3)
    num_risky = sum(1 for r in student_rows if r["risk_level"] == "고위험")
    num_warning = sum(1 for r in student_rows if r["risk_level"] == "주의")

    # 위험도 기준 정렬 (고위험/주의 위쪽으로)
    risk_rank = {"고위험": 2, "주의": 1, "정상": 0}
    sorted_students = sorted(
        student_rows,
        key=lambda r: (risk_rank[r["risk_level"]] * -1, r["days_active_7d"]),
        reverse=False,
    )

    top_risk_students = [
        {
            "user_id": r["user_id"],
            "name": r["name"],
            "class_id": r["class_id"],
            "days_active_7d": r["days_active_7d"],
            "risk_level": r["risk_level"],
        }
        for r in sorted_students
        if r["risk_level"] in ("주의", "고위험")
    ][:3]

    # 최종 payload(dict)
    report = {
        "summary_cards": {
            "avg_attendance_rate": avg_attendance_rate,
            "num_low_access_3days": num_low_access_3days,
            "num_risky": num_risky,
            "num_warning": num_warning,
        },
        "charts": {
            "attendance_timeseries": timeseries,
        },
        "tables": {
            "top_risk_students": top_risk_students,
            "student_list": student_rows,
            "per_student_actions": [],  # 나중에 LLM 붙일 때 채우기
        },
    }

    return report
