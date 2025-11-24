from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import DB_URL

# SQLite
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},  # SQLite 필수
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
