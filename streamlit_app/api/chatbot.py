import sys
sys.path.append("../..")
import asyncio
import websockets
import json

WEBSOCKET_URL = "ws://localhost:8020/ws/chatbot"

async def sendchat(question):
    # TODO : 서버로 요청 보내는 로직 구현
    async with websockets.connect(WEBSOCKET_URL) as websocket:
        json_data = json.dumps({"question": question}, ensure_ascii=False)
        await websocket.send(json_data)
        
        resp = await websocket.recv()
        return resp