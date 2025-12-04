# scripts/insert_dummy_chatlogs.py
import sys
from pathlib import Path

# 이 파일 기준으로 프로젝트 루트 계산
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parents[2]   # .../MumulMumul
sys.path.append(str(ROOT_DIR))

import csv
import random
from datetime import datetime, timedelta, time

from pymongo import MongoClient
from sqlalchemy.orm import sessionmaker

from app.core.mongodb import LearningChatLog
from app.core.schemas import Camp, init_db
from app.config import MONGO_URL, MONGO_DB_NAME, SQLITE_URL


CSV_PATH = r"C:\Potenup\MumulMumul\app\sql\learning_chat_logs_dummy.csv"   # CSV 파일 경로


# ---------- 주차 기반 random datetime 생성 유틸 ----------

def random_datetime_in_week(camp, week_index: int) -> datetime:
    """
    camp.start_date / camp.end_date 와 CSV의 week 값("Week 1" 형태)을 활용해서
    해당 주차 내의 평일 중 랜덤한 날짜 + 시간 생성
    """
    if not camp.start_date or not camp.end_date:
        # 캠프 기간 정보가 없으면 그냥 지금 시간 반환 (혹은 raise 해도 됨)
        return datetime.utcnow()

    camp_start = camp.start_date.date()
    camp_end = camp.end_date.date()

    # 해당 주차의 이론상 범위
    # 1주차: start ~ start+6
    # 2주차: start+7 ~ start+13 ...
    week_start_date = camp_start + timedelta(days=(week_index - 1) * 7)
    week_end_date = week_start_date + timedelta(days=6)

    # 캠프 전체 기간 안으로 클램프
    effective_start = max(week_start_date, camp_start)
    effective_end = min(week_end_date, camp_end)

    if effective_start > effective_end:
        # 주차 계산이 캠프 기간을 벗어나는 경우 → 그냥 캠프 시작일 기준
        effective_start = camp_start
        effective_end = min(camp_start + timedelta(days=6), camp_end)

    # 평일만 추출
    candidate_days = []
    cur = effective_start
    while cur <= effective_end:
        if cur.weekday() < 5:  # 0=월 ~ 4=금
            candidate_days.append(cur)
        cur += timedelta(days=1)

    if not candidate_days:
        candidate_days = [effective_start]

    day = random.choice(candidate_days)

    # 09:00 ~ 18:00 사이 랜덤 시간
    hour = random.randint(9, 18)
    minute = random.choice([0, 15, 30, 45])

    return datetime.combine(day, time(hour, minute))


def insert_dummy_chatlogs():
    # --- SQLite 연결 (캠프 기간 조회용) ---
    engine = init_db(SQLITE_URL)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    # camp_id → Camp 매핑
    camps = {c.camp_id: c for c in db.query(Camp).all()}

    # --- Mongo 연결 ---
    client = MongoClient(MONGO_URL)
    db_mongo = client[MONGO_DB_NAME]
    coll = db_mongo["learning_chat_logs"]

    inserted_count = 0

    # --- CSV 읽기 ---
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                camp_id = 1 # int(row["camp_id"]) if row.get("camp_id") else None
                camp = camps.get(camp_id) if camp_id else None

                # CSV의 week 컬럼 사용 (없으면 "Week 1"로 간주)
                week_index = row.get("curriculum_week") or 1

                created_at = random_datetime_in_week(camp, int(week_index))
                id = int(row["user_id"].split("_")[-1]) + 7

                record = LearningChatLog(
                    user_id=id,
                    session_id=id,
                    camp_id=camp_id,
                    role="user",#row["role"],
                    content=row["question"],
                    created_at=created_at,
                ).model_dump()

                coll.insert_one(record)
                inserted_count += 1

            except Exception as e:
                print(f"❌ Error inserting row: {row}")
                print(e)

    db.close()
    client.close()

    print(f"🎉 Done! Inserted {inserted_count} chat logs.")


if __name__ == "__main__":
    insert_dummy_chatlogs()
