import sys
sys.path.append("../..")

from app.graphs.example_graph import agent

from fastapi import APIRouter, WebSocket

router = APIRouter()

from pydantic import BaseModel

# 사용자 요청 형식 (optional; we'll accept raw text or JSON {"question": ...})
class Request(BaseModel):
    question: str

@router.websocket("/ws/chatbot")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            payload = await websocket.receive_json()
            text = payload["question"]

            # 에이전트 호출
            from langchain.messages import HumanMessage

            user_messages = [HumanMessage(content=text)]
            result = agent.invoke({"messages": user_messages})

            # 서버 출력
            for m in result.get("messages", []):
                try:
                    m.pretty_print()
                except Exception:
                    pass

            # 클라이언트로 응답 전송
            final = ""
            if result.get("messages"):
                final = result["messages"][-1].content or ""

            await websocket.send_text(final)

    except Exception as e:
        print(f"WebSocket 에러 발생: {e}")
    # finally:
    #     await websocket.close()
    #     print("WebSocket 연결 종료")