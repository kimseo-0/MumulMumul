import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parents[2]
sys.path.append(str(ROOT_DIR))

import random
from datetime import datetime, timedelta, time

from sqlalchemy.orm import sessionmaker

from app.core.schemas import User, Camp, SessionActivityLog, init_db
from app.config import SQLITE_URL


# ======= 설정값 =======
CLASS_START_AM = time(9, 0)
CLASS_END_AM = time(12, 0)
CLASS_START_PM = time(13, 0)
CLASS_END_PM = time(18, 0)


def combine_dt(day: datetime, t: time) -> datetime:
    return datetime.combine(day.date(), t)


def jitter_minutes(dt: datetime, min_offset: int, max_offset: int) -> datetime:
    return dt + timedelta(minutes=random.randint(min_offset, max_offset))


# -----------------------------
# 캠프 기간 기반으로 날짜 리스트 생성
# -----------------------------
def generate_date_range(start_date: datetime, end_date: datetime):
    """
    캠프 시작일 ~ 종료일 사이의 날짜를 생성하여 반환
    (주말 제외)
    """
    days = []
    cur = start_date
    while cur <= end_date:
        if cur.weekday() < 5:  # 0=월 ~ 4=금
            days.append(cur)
        cur += timedelta(days=1)
    return days


# -----------------------------
# 패턴별 로그 생성 로직
# -----------------------------
def generate_logs_for_student_pattern(
    user_id: int,
    day_list: list[datetime],
    pattern: str,
) -> list[SessionActivityLog]:
    logs = []

    for idx, day in enumerate(day_list):

        join_dt = combine_dt(day, CLASS_START_AM)
        leave_dt = combine_dt(day, CLASS_END_PM)

        # -----------------------------
        # 패턴별 조건 적용
        # -----------------------------
        if pattern == "stable_good":
            if random.random() < 0.1:
                continue
            join_dt = jitter_minutes(join_dt, -5, 10)
            leave_dt = jitter_minutes(leave_dt, -10, 10)

        elif pattern == "mild_late":
            if random.random() < 0.2:
                continue
            late_start = time(random.randint(10, 11), random.choice([0, 15, 30, 45]))
            join_dt = combine_dt(day, late_start)
            leave_dt = jitter_minutes(leave_dt, -10, 10)

        elif pattern == "early_leave":
            if random.random() < 0.2:
                continue
            join_dt = jitter_minutes(join_dt, -5, 10)
            early_end = time(random.randint(14, 17), random.choice([0, 15, 30, 45]))
            leave_dt = combine_dt(day, early_end)

        elif pattern == "part_timer":
            if random.random() < 0.65:
                continue
            join_dt = jitter_minutes(join_dt, -10, 20)
            leave_dt = jitter_minutes(leave_dt, -20, 0)

        elif pattern == "front_loaded_then_drop":
            # 1주차 / 2주차 / 3주차 이후를 day_list 인덱스로 판정
            if idx < 5:
                # 첫 주: 매우 좋은 출석
                if random.random() < 0.1:
                    continue
                join_dt = jitter_minutes(join_dt, -10, 10)
                leave_dt = jitter_minutes(leave_dt, -10, 10)

            elif idx < 10:
                # 두 번째 주: 절반만 출석
                if random.random() < 0.5:
                    continue
                if random.random() < 0.5:
                    late_start = time(random.randint(10, 11), random.choice([0, 30]))
                    join_dt = combine_dt(day, late_start)
                if random.random() < 0.5:
                    early_end = time(random.randint(15, 17), random.choice([0, 30]))
                    leave_dt = combine_dt(day, early_end)

            else:
                # 세 번째 주 이후: 거의 결석
                if random.random() < 0.8:
                    continue
                short_start = time(random.randint(10, 14), random.choice([0, 30]))
                join_dt = combine_dt(day, short_start)
                leave_dt = join_dt + timedelta(hours=random.randint(1, 3))

        elif pattern == "noisy_random":
            if random.random() < 0.5:
                continue
            start_hour = random.randint(9, 16)
            start_min = random.choice([0, 15, 30, 45])
            join_dt = combine_dt(day, time(start_hour, start_min))
            leave_dt = join_dt + timedelta(hours=random.randint(1, 4))

        elif pattern == "almost_dropout":
            if random.random() < 0.85:
                continue
            short_start = time(random.randint(10, 15), random.choice([0, 30]))
            join_dt = combine_dt(day, short_start)
            leave_dt = join_dt + timedelta(hours=random.randint(1, 3))

        else:
            continue

        logs.append(
            SessionActivityLog(
                user_id=user_id,
                join_at=join_dt,
                leave_at=leave_dt,
            )
        )

    return logs


# -----------------------------
# 패턴 분포
# -----------------------------
GOOD_CAMP_PATTERNS = {
    "stable_good": 0.5,
    "mild_late": 0.2,
    "early_leave": 0.15,
    "part_timer": 0.1,
    "front_loaded_then_drop": 0.05,
}

BAD_CAMP_PATTERNS = {
    "stable_good": 0.1,
    "mild_late": 0.15,
    "early_leave": 0.15,
    "part_timer": 0.25,
    "front_loaded_then_drop": 0.15,
    "noisy_random": 0.1,
    "almost_dropout": 0.1,
}


def choose_pattern_for_student(camp_name: str) -> str:
    if "프론트" in camp_name:
        patterns = list(GOOD_CAMP_PATTERNS.keys())
        weights = list(GOOD_CAMP_PATTERNS.values())
    elif "백엔드" in camp_name:
        patterns = list(BAD_CAMP_PATTERNS.keys())
        weights = list(BAD_CAMP_PATTERNS.values())
    else:
        patterns = list(GOOD_CAMP_PATTERNS.keys())
        weights = list(GOOD_CAMP_PATTERNS.values())
    return random.choices(patterns, weights=weights, k=1)[0]


# -----------------------------
# 최종 실행
# -----------------------------
def generate_dummy_attendance():
    engine = init_db(SQLITE_URL)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    # 캠프 / 학생 로드
    camps = {c.camp_id: c for c in session.query(Camp).all()}
    students = (
        session.query(User)
        .join(Camp, User.camp_id == Camp.camp_id)
        .filter(User.user_type.has(type_name="학생"))
        .all()
    )

    all_logs = []

    print(f"🎯 총 {len(students)}명 학생 출결 더미 생성 시작")

    for stu in students:
        camp = camps.get(stu.camp_id)
        if not camp or not camp.start_date or not camp.end_date:
            continue

        # 캠프 날짜 기반 생성
        day_list = generate_date_range(camp.start_date, camp.end_date)

        # 패턴 선택
        pattern = choose_pattern_for_student(camp.name)

        # 패턴 기반 로그 생성
        logs = generate_logs_for_student_pattern(
            user_id=stu.user_id,
            day_list=day_list,
            pattern=pattern,
        )
        all_logs.extend(logs)

    print(f"📦 생성된 출결 로그 수: {len(all_logs)}")

    session.add_all(all_logs)
    session.commit()
    session.close()

    print("✅ session_activity_log 더미 데이터 생성 완료!")


if __name__ == "__main__":
    generate_dummy_attendance()
