from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.connection import router as connection_router
from app.api.chatbot import router as chatbot_router
from app.api.attendance import router as attendance_router
from app.api.curriculum import router as curriculum_router
from app.api.user import router as user_router
from app.api.learning_chatbot import router as learning_chatbot_router
from app.core.mongodb import init_mongo, get_mongo_db
from app.core.schemas import init_db
from app.config import SQLITE_URL


# ------------------------------
# FastAPI 앱 생성
# ------------------------------
def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            print("DB 마이그레이션 적용")
            init_db(SQLITE_URL)
            init_mongo(get_mongo_db())
        except Exception:
            print("DB 마이그레이션 실패")
        yield   

    app = FastAPI(title="Mumul Mumul Api", version="0.1.0", lifespan=lifespan)

    return app

app = create_app()

# ------------------------------
# 라우터 등록
# ------------------------------
app.include_router(connection_router, prefix="/connection")
app.include_router(chatbot_router)
app.include_router(attendance_router, prefix="/attendance")
app.include_router(curriculum_router, prefix="/curriculum")
app.include_router(user_router, prefix="/user")
app.include_router(learning_chatbot_router, prefix="/learning_chatbot")
