import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta

# 프로젝트 루트 설정
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parents[2]
sys.path.append(str(ROOT_DIR))

from sqlalchemy.orm import sessionmaker
from app.core.schemas import Meeting, init_db
from app.config import DB_URL


def seed_dummy_meetings():
    engine = init_db(DB_URL)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    now = datetime.utcnow()
    statuses = ["in_progress", "completed", "cancelled"]

    dummy_meetings = []

    for i in range(5):
        start_time = now - timedelta(days=i, hours=1)
        date_str = start_time.strftime("%Y%m%d")

        # UUID 랜덤 생성
        random_uuid = uuid.uuid4().hex[:8]  # 8자리만 사용

        meeting_id = f"meeting_{date_str}_{random_uuid}"

        end_time = start_time + timedelta(hours=1)
        status = statuses[i % len(statuses)]

        meeting = Meeting(
            meeting_id=meeting_id,
            title=f"더미 회의 {i+1}",
            organizer_id=i+1,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            start_client_timestamp=int(start_time.timestamp()),
            start_server_timestamp=int(start_time.timestamp() + 2),
            time_offset=2,
            status=status,
            agenda=f"더미 회의 {i+1}의 아젠다입니다.",
            description=f"더미 회의 {i+1}에 대한 간단한 설명입니다.",
            duration_ms=3600000,
            participant_count=3 + i,
            created_at=start_time.isoformat(),
            updated_at=end_time.isoformat(),
        )

        dummy_meetings.append(meeting)

    session.add_all(dummy_meetings)
    session.commit()
    session.close()
    print("더미 meeting 데이터 5개 삽입 완료!")


if __name__ == "__main__":
    seed_dummy_meetings()
