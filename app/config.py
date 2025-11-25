# config.py
import os
from dotenv import load_dotenv

# .env 파일 로드 (선택)
load_dotenv()

SQLITE_URL = os.getenv("DB_URL", "sqlite:///storage/mumul.db")
MONGO_URL = "mongodb://localhost:27017"
MONGO_DB_NAME = "mumul"

DAILY_SCHEDULE = {
    "morning": {"start": 9, "end": 12},
    "afternoon": {"start": 13, "end": 18},
}

MEETING_CONFIG = {
    "min_active_seconds": 60,   # 1분 미만 참여는 무효 처리 등
}
