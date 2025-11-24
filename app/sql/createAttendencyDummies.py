import sys
from pathlib import Path

# 이 파일 기준으로 프로젝트 루트 계산
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parents[2]   # .../MumulMumul

sys.path.append(str(ROOT_DIR))

import random
from datetime import datetime, timedelta, time

from sqlalchemy.orm import sessionmaker

from app.core.schemas import User, Camp, SessionActivityLog, init_db
from app.config import DB_URL


DAYS_TO_GENERATE = 21  # 3주
CLASS_START_AM = time(9, 0)
CLASS_END_AM = time(12, 0)
CLASS_START_PM = time(13, 0)
CLASS_END_PM = time(18, 0)


def combine_dt(day: datetime, t: time) -> datetime:
    return datetime.combine(day.date(), t)


def jitter_minutes(dt: datetime, min_offset: int, max_offset: int) -> datetime:
    return dt + timedelta(minutes=random.randint(min_offset, max_offset))


# -----------------------------
# 패턴별 로그 생성 로직
# -----------------------------
def generate_logs_for_student_pattern(
    user_id: int,
    start_day: datetime,
    pattern: str,
) -> list[SessionActivityLog]:
    logs: list[SessionActivityLog] = []

    for i in range(DAYS_TO_GENERATE):
        day = start_day - timedelta(days=i)

        # 주말은 스킵 (원하면 주말도 포함하게 바꿔도 됨)
        if day.weekday() >= 5:  # 5=토, 6=일
            continue

        # 기본 정상 출석 시간
        join_dt = combine_dt(day, CLASS_START_AM)
        leave_dt = combine_dt(day, CLASS_END_PM)

        # 각 패턴별로 출석 여부/시간 결정
        if pattern == "stable_good":
            # 90% 출석, 10% 결석
            if random.random() < 0.1:
                continue
            join_dt = jitter_minutes(join_dt, -5, 10)
            leave_dt = jitter_minutes(leave_dt, -10, 10)

        elif pattern == "mild_late":
            # 80% 출석, 20% 결석
            if random.random() < 0.2:
                continue
            # 오전 지각 (10~11시 사이 랜덤)
            late_start = time(random.randint(10, 11), random.choice([0, 15, 30, 45]))
            join_dt = combine_dt(day, late_start)
            leave_dt = jitter_minutes(leave_dt, -10, 10)

        elif pattern == "early_leave":
            # 80% 출석, 20% 결석
            if random.random() < 0.2:
                continue
            join_dt = jitter_minutes(join_dt, -5, 10)
            # 오후 일찍 나감 (14~17시 사이)
            early_end = time(random.randint(14, 17), random.choice([0, 15, 30, 45]))
            leave_dt = combine_dt(day, early_end)

        elif pattern == "part_timer":
            # 주 2~3회만 출석
            if random.random() < 0.65:
                continue
            join_dt = jitter_minutes(join_dt, -10, 20)
            leave_dt = jitter_minutes(leave_dt, -20, 0)

        elif pattern == "front_loaded_then_drop":
            # 1주차: 거의 정상, 2주차: 반타작, 3주차: 거의 결석
            if i < 7:
                # 1주차
                if random.random() < 0.1:
                    continue
                join_dt = jitter_minutes(join_dt, -10, 10)
                leave_dt = jitter_minutes(leave_dt, -10, 10)
            elif i < 14:
                # 2주차
                if random.random() < 0.5:
                    continue
                # 출석해도 지각/조퇴 섞기
                if random.random() < 0.5:
                    late_start = time(
                        random.randint(10, 11), random.choice([0, 30])
                    )
                    join_dt = combine_dt(day, late_start)
                if random.random() < 0.5:
                    early_end = time(
                        random.randint(15, 17), random.choice([0, 30])
                    )
                    leave_dt = combine_dt(day, early_end)
            else:
                # 3주차
                if random.random() < 0.8:
                    continue
                # 출석해도 2~3시간만
                short_start = time(random.randint(10, 14), random.choice([0, 30]))
                join_dt = combine_dt(day, short_start)
                leave_dt = join_dt + timedelta(hours=random.randint(1, 3))

        elif pattern == "noisy_random":
            # 완전 랜덤 들락날락
            if random.random() < 0.5:
                continue
            # 아무 시간대나 1~4시간
            start_hour = random.randint(9, 16)
            start_min = random.choice([0, 15, 30, 45])
            join_dt = combine_dt(day, time(start_hour, start_min))
            leave_dt = join_dt + timedelta(hours=random.randint(1, 4))

        elif pattern == "almost_dropout":
            # 3주 동안 3~5일만 출석
            # 일단 기본적으로 거의 결석
            if random.random() < 0.85:
                continue
            # 출석할 때도 짧게
            start_hour = random.randint(10, 15)
            start_min = random.choice([0, 30])
            join_dt = combine_dt(day, time(start_hour, start_min))
            leave_dt = join_dt + timedelta(hours=random.randint(1, 3))

        else:
            # 정의 안 된 패턴이면 건너뛰기
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
# 캠프별 패턴 분포 설정
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
    """캠프 이름에 따라 좋은/나쁜 패턴 분포에서 하나 선택"""
    if "프론트" in camp_name:
        patterns = list(GOOD_CAMP_PATTERNS.keys())
        weights = list(GOOD_CAMP_PATTERNS.values())
    elif "백엔드" in camp_name:
        patterns = list(BAD_CAMP_PATTERNS.keys())
        weights = list(BAD_CAMP_PATTERNS.values())
    else:
        # 디폴트는 중간 정도
        patterns = list(GOOD_CAMP_PATTERNS.keys())
        weights = list(GOOD_CAMP_PATTERNS.values())

    return random.choices(patterns, weights=weights, k=1)[0]


def generate_dummy_attendance():
    engine = init_db(DB_URL)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    today = datetime.today()

    # 캠프/학생 로드
    camps = {c.camp_id: c for c in session.query(Camp).all()}
    students = (
        session.query(User)
        .join(Camp, User.camp_id == Camp.camp_id)
        .filter(User.user_type.has(type_name="학생"))  # user_type 관계 쓸 수 있으면 이렇게
        .all()
    )

    all_logs: list[SessionActivityLog] = []

    print(f"🎯 총 {len(students)}명 학생에 대해 3주 출결 더미 생성 시작")

    for stu in students:
        camp = camps.get(stu.camp_id)
        if not camp:
            continue

        pattern = choose_pattern_for_student(camp.name)
        logs = generate_logs_for_student_pattern(
            user_id=stu.user_id,
            start_day=today,
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
