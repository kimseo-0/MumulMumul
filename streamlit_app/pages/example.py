import streamlit as st

import sys
sys.path.append("..")
from api.chatbot import sendchat
#---------------------------------------------------------------------
# session state 정의 : 히스토리 저장소 만들기
if not "messages" in st.session_state:
    st.session_state["messages"] = []
#---------------------------------------------------------------------
# 챗봇 제목 
st.title("챗봇 테스트")

# st.write(st.session_state["messages"])

# 과거 메시지 출력 
for chat in st.session_state["messages"]:
    st.chat_message(name=chat["role"]).markdown(chat["content"])

# 사용자 입력
import asyncio

user_input = st.chat_input("메세지를 입력하세요...")

# 사용자 입력 이후
if user_input:
    st.session_state["messages"].append(
        {"role": "user", "content": user_input}
    )

    with st.chat_message("user"):
        st.write(user_input)

    # 요청 보내고 전체 응답을 한 번에 표시
    with st.chat_message("assistant"):
        with st.spinner("생각하는 중이에요..."):
            try:
                answer = asyncio.run(sendchat(user_input))
            except RuntimeError:
                loop = asyncio.get_event_loop()
                answer = loop.run_until_complete(sendchat(user_input))

        st.write(answer)

    st.session_state["messages"].append(
        {"role": "assistant", "content": answer}
    )
