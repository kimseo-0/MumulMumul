from __future__ import annotations
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.connection import router as connection_router
from app.api.chatbot import router as chatbot_router
from app.core.shcemas import init_db
from app.config import DB_URL

def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            print("DB 마이그레이션 적용")
            init_db(DB_URL)
        except Exception:
            print("DB 마이그레이션 실패")
        yield

    app = FastAPI(title="Moms Diary Chatbot API", version="0.1.0", lifespan=lifespan)

    return app

app = create_app()

# 라우터 추가
app.include_router(connection_router, prefix="/connection")
app.include_router(chatbot_router)