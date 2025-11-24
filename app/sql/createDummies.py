import sys
sys.path.append("../..")

from sqlalchemy.orm import sessionmaker
from app.core.shcemas import UserType, User, Camp, init_db
from config import DB_URL


def seed_dummy_data():
    engine = init_db(DB_URL)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    # 1. user type
    admin_type = UserType(type_name="운영진", permissions="all")
    instructor_type = UserType(type_name="강사", permissions="camp_scoped")
    student_type = UserType(type_name="학생", permissions="camp_member")

    session.add_all([admin_type, instructor_type, student_type])
    session.commit()

    # 2. camp
    backend_camp = Camp(name="백엔드캠프")
    frontend_camp = Camp(name="프론트캠프")

    session.add_all([backend_camp, frontend_camp])
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
                password_hash=generate_password_hash(login_id),
                name=f"백엔드강사{i}",
                email=f"{login_id}@mumul.com",
                user_type_id=instructor_type.type_id,
                camp_id=backend_camp.camp_id,
            )
        )

    # 프론트 강사
    for i in range(1, 3):
        login_id = f"instructor_fe{i}"
        instructors.append(
            User(
                login_id=login_id,
                password_hash=generate_password_hash(login_id),
                name=f"프론트강사{i}",
                email=f"{login_id}@mumul.com",
                user_type_id=instructor_type.type_id,
                camp_id=frontend_camp.camp_id,
            )
        )

    session.add_all(instructors)
    session.commit()

    # -----------------------------
    # 5. 학생 20명씩
    # -----------------------------
    students = []

    # 백엔드 캠프 학생
    for i in range(1, 21):
        login_id = f"be_student{i}"
        students.append(
            User(
                login_id=login_id,
                password_hash=generate_password_hash(login_id),
                name=f"백엔드학생{i}",
                email=f"{login_id}@mumul.com",
                user_type_id=student_type.type_id,
                camp_id=backend_camp.camp_id,
            )
        )

    # 프론트 캠프 학생
    for i in range(1, 21):
        login_id = f"fe_student{i}"
        students.append(
            User(
                login_id=login_id,
                password_hash=generate_password_hash(login_id),
                name=f"프론트학생{i}",
                email=f"{login_id}@mumul.com",
                user_type_id=student_type.type_id,
                camp_id=frontend_camp.camp_id,
            )
        )

    session.add_all(students)
    session.commit()

    session.close()
    print("🎉 더미 데이터 삽입 완료 (id = 비밀번호)!")


if __name__ == "__main__":
    seed_dummy_data()
