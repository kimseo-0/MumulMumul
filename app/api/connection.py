import sys
sys.path.append("../..")

from fastapi import APIRouter

router = APIRouter()

# 예시 엔드포인트 : 접속시 Hello World 반환
@router.get("/")
async def hello_world():
    return {"message": "Hello World"}