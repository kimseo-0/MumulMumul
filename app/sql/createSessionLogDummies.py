import sys
from pathlib import Path
from datetime import datetime, timedelta

from sqlalchemy.orm import sessionmaker

# 이 파일 기준으로 프로젝트 루트 계산
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parents[2]   # .../MumulMumul
sys.path.append(str(ROOT_DIR))

from app.core.schemas import User, Camp, SessionActivityLog, init_db
from app.config import SQLITE_URL


def daterange(start, end):
    """날짜 범위 생성기 (start~end inclusive)"""
    for n in range((end - start).days + 1):
        yield start + timedelta(days=n)


# ---------------------------
# 유저별 패턴 생성 함수들
# ---------------------------

def generate_user1(date: datetime):
    """user1 (김해찬) – 성실 패턴: 09:00~18:00 거의 정상 출석"""
    join = date.replace(hour=9, minute=0, second=0) + timedelta(minutes=0)
    leave = date.replace(hour=18, minute=0, second=0) + timedelta(minutes=0)
    return join, leave


def generate_user2(date: datetime):
    """user2 (윤여민) – 지각/조퇴 패턴"""
    join = date.replace(hour=10, minute=10, second=0)  # 10시 조금 넘어서
    leave = date.replace(hour=16, minute=30, second=0)  # 16:30 정도
    return join, leave


def generate_user3(date: datetime):
    """user3 (김서영) – 결석 & 중간 이탈 패턴"""
    # 40% 결석
    import random
    if random.random() < 0.4:
        return None, None

    join = date.replace(hour=9, minute=10, second=0)
    leave = join + timedelta(hours=3)   # 3시간 정도 있다가 나감
    return join, leave


def generate_user4(date: datetime):
    """user4 (이성윤) – 주 2~3회만 출석(저빈도)"""
    import random
    # 70% 결석
    if random.random() < 0.7:
        return None, None

    join = date.replace(hour=9, minute=20, second=0)
    leave = date.replace(hour=18, minute=10, second=0)
    return join, leave


def generate_user5(date: datetime):
    """
    user5 (차요준) – 후반부 급격 이탈 패턴
    - 11월은 거의 정상 출석
    - 12월 들어가면서 결석 점점 증가
    """
    import random

    if date.month == 12:
        # 12월은 날짜가 뒤로 갈수록 결석 확률 증가
        days_into_dec = date.day
        absent_prob = min(0.2 + days_into_dec * 0.04, 0.9)
        if random.random() < absent_prob:
            return None, None

    join = date.replace(hour=9, minute=5, second=0)
    leave = date.replace(hour=18, minute=5, second=0)
    return join, leave


def seed_session_activity_log():
    # ---------------------------
    # DB 세션 생성
    # ---------------------------
    engine = init_db(SQLITE_URL)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    try:
        # ---------------------------
        # 1. 머물머물 캠프 찾기
        # ---------------------------
        test_camp: Camp | None = (
            session.query(Camp)
            .filter(Camp.name == "머물머물 캠프")
            .first()
        )
        if test_camp is None:
            print("❌ '머물머물 캠프'를 찾을 수 없습니다. 먼저 seed_dummy_data를 실행했는지 확인하세요.")
            return

        # 캠프 기간
        start_date: datetime = test_camp.start_date
        end_date: datetime = test_camp.end_date

        # ---------------------------
        # 2. user1 ~ user5 조회
        # ---------------------------
        login_ids = ["user1", "user2", "user3", "user4", "user5"]
        users = (
            session.query(User)
            .filter(User.login_id.in_(login_ids))
            .all()
        )
        user_by_login = {u.login_id: u for u in users}

        # 다 안 나오면 오류 안내
        missing = [lid for lid in login_ids if lid not in user_by_login]
        if missing:
            print(f"❌ 다음 login_id 유저를 찾을 수 없습니다: {missing}")
            return

        pattern_funcs = {
            "user1": generate_user1,
            "user2": generate_user2,
            "user3": generate_user3,
            "user4": generate_user4,
            "user5": generate_user5,
        }

        print("🚀 session_activity_log 더미 생성 시작...")

        # 기존 더미를 지우고 싶으면 아래 주석 해제
        # session.query(SessionActivityLog).delete()
        # session.commit()

        for current_date in daterange(start_date, end_date):
            # 주말 제외하고 싶으면 주석 해제
            # if current_date.weekday() >= 5:
            #     continue

            for login_id in login_ids:
                func = pattern_funcs[login_id]
                join_at, leave_at = func(current_date)

                if join_at is None or leave_at is None:
                    # 결석
                    continue

                user = user_by_login[login_id]

                log = SessionActivityLog(
                    user_id=user.user_id,
                    join_at=join_at,
                    leave_at=leave_at,
                )
                session.add(log)

        session.commit()
        print("✅ session_activity_log 더미 생성 완료!")

    finally:
        session.close()


if __name__ == "__main__":
    seed_session_activity_log()
