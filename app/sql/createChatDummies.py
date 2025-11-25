# scripts/insert_dummy_chatlogs.py
import sys
from pathlib import Path

# 이 파일 기준으로 프로젝트 루트 계산
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parents[2]   # .../MumulMumul

sys.path.append(str(ROOT_DIR))

import csv
from datetime import datetime
from pymongo import MongoClient
from app.core.mongodb import LearningChatLog
from app.config import MONGO_URL, MONGO_DB_NAME


CSV_PATH = r"C:\Potenup\MumulMumul\app\sql\learning_chat_logs_dummy.csv"   # CSV 파일 경로

def insert_dummy_chatlogs():
    # --- Mongo 연결 ---
    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB_NAME]
    coll = db["learning_chat_logs"]

    inserted_count = 0

    # --- CSV 읽기 ---
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                # CSV → Pydantic 모델 → dict 변환
                record = LearningChatLog(
                    user_id=int(row["user_id"]),
                    camp_id=int(row["camp_id"]) if row.get("camp_id") else None,
                    role=row["role"],
                    content=row["content"],
                    curriculum_scope=row.get("curriculum_scope"),
                    question_category=row.get("question_category"),
                    created_at=datetime.fromisoformat(row["created_at"])
                ).model_dump()

                # MongoDB insert
                coll.insert_one(record)
                inserted_count += 1

            except Exception as e:
                print(f"❌ Error inserting row: {row}")
                print(e)

    print(f"🎉 Done! Inserted {inserted_count} chat logs.")


if __name__ == "__main__":
    insert_dummy_chatlogs()
