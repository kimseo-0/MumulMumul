import sys
from pathlib import Path

# 이 파일 기준으로 프로젝트 루트 계산
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parents[2]   # .../MumulMumul

sys.path.append(str(ROOT_DIR))

from sqlalchemy.orm import sessionmaker
from app.core.schemas import UserType, User, Camp, init_db
from app.config import SQLITE_URL
from datetime import datetime, timedelta, time


def seed_dummy_data():
    engine = init_db(SQLITE_URL)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    # 1. user type
    admin_type = UserType(type_name="운영진", permissions="all")
    instructor_type = UserType(type_name="강사", permissions="camp_scoped")
    student_type = UserType(type_name="학생", permissions="camp_member")

    session.add_all([admin_type, instructor_type, student_type])
    session.commit()

    # 2. camp
    ai_camp = Camp(name="AI 캠프", start_date=datetime(2025, 11, 3), end_date=datetime(2025, 11, 3) + timedelta(weeks=6))
    unreal_camp = Camp(name="언리얼 캠프", start_date=datetime(2025, 11, 3), end_date=datetime(2025, 11, 3) + timedelta(weeks=6))
    test_camp = Camp(name="머물머물 캠프", start_date=datetime(2025, 11, 3), end_date=datetime(2025, 11, 3) + timedelta(weeks=6))

    session.add_all([test_camp, ai_camp, unreal_camp])
    session.commit()

    # -----------------------------
    # 3. 운영진 3명
    # -----------------------------
    admins = []
    for i in range(1, 4):
        login_id = f"admin{i}"
        admins.append(
            User(
                login_id=login_id,
                password_hash=login_id,  # id와 비번 동일
                name=f"운영진{i}",
                email=f"admin{i}@mumul.com",
                user_type_id=admin_type.type_id,
                camp_id=None,
            )
        )
    session.add_all(admins)
    session.commit()

    # -----------------------------
    # 4. 캠프별 강사 2명씩
    # -----------------------------
    instructors = []

    # 백엔드 강사
    for i in range(1, 3):
        login_id = f"instructor_be{i}"
        instructors.append(
            User(
                login_id=login_id,
                password_hash=login_id,
                name=f"AI강사{i}",
                email=f"{login_id}@mumul.com",
                user_type_id=instructor_type.type_id,
                camp_id=ai_camp.camp_id,
            )
        )

    # 프론트 강사
    for i in range(1, 3):
        login_id = f"instructor_fe{i}"
        instructors.append(
            User(
                login_id=login_id,
                password_hash=login_id,
                name=f"언리얼강사{i}",
                email=f"{login_id}@mumul.com",
                user_type_id=instructor_type.type_id,
                camp_id=unreal_camp.camp_id,
            )
        )

    session.add_all(instructors)
    session.commit()

    # -----------------------------
    # 5. 학생 20명씩
    # -----------------------------
    students = []

    # 캠프 학생
    for i in range(1, 100):
        login_id = f"ai_student{i}"
        students.append(
            User(
                login_id=login_id,
                password_hash=login_id,
                name=f"AI학생{i}",
                email=f"{login_id}@mumul.com",
                user_type_id=student_type.type_id,
                camp_id=ai_camp.camp_id,
            )
        )

    # 프론트 캠프 학생
    for i in range(1, 100):
        login_id = f"ur_student{i}"
        students.append(
            User(
                login_id=login_id,
                password_hash=login_id,
                name=f"언리얼학생{i}",
                email=f"{login_id}@mumul.com",
                user_type_id=student_type.type_id,
                camp_id=unreal_camp.camp_id,
            )
        )

    # 테스트 캠프 학생
    login_ids = ["test1", "test2", "test3", "test4", "test5"]
    test_name = ["김해찬", "윤여민", "김서영", "이성윤", "차요준"]
    for i in range(5):
        login_id = login_ids[i]
        test_user = [
                User(
                    login_id=login_id,
                    password_hash=login_id,
                    name=f"{test_name[i]}",
                    email=f"{login_id}@mumul.com",
                    user_type_id=student_type.type_id,
                    camp_id=test_camp.camp_id,
                )
        ]
        students.append(test_user)

    session.add_all(students)
    session.commit()

    session.close()
    print("🎉 더미 데이터 삽입 완료 (id = 비밀번호)!")


if __name__ == "__main__":
    seed_dummy_data()
