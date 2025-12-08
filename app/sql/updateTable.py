import sys
from pathlib import Path

# 이 파일 기준으로 프로젝트 루트 계산
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parents[2]   # .../MumulMumul

from sqlalchemy import create_engine, text


def update_meeting_table(meeting_id, db_url="sqlite:///storage/mumul.db"):
    engine = create_engine(db_url, echo=True, future=True)
    with engine.connect() as conn:
        conn.execute(
            text(f"UPDATE meeting SET status = 'in_progress' where meeting_id = :meeting_id"),
            {"meeting_id": meeting_id}
        )
        conn.commit()
        print(f"테이블 업데이트 완료")

update_meeting_table("251204_a1f36")