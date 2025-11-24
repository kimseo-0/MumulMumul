from sqlalchemy import create_engine, text

def drop_camp_table(db_url="sqlite:///mumul.db"):
    engine = create_engine(db_url, echo=True, future=True)
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS camp"))
        conn.commit()
        print("camp 테이블 삭제 완료")

drop_camp_table()
