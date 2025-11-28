# streamlit 앱 진입점
from __future__ import annotations
import streamlit as st

st.set_page_config(
    page_title="머물머물 관리자 대시보드",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🔥 머물머물 운영 리포트 대시보드")
st.markdown(
    """
왼쪽 사이드바에서 아래 3가지 리포트 페이지를 이동하며 구조를 확인할 수 있어요.

1. **익명 게시판 분석** – 건의/문제 파악, 분위기 흐름  
2. **학습 난이도·커리큘럼 병목 분석** – 어디서 막히는지  
3. **출결 및 이탈 위험 분석** – 누구를 케어해야 하는지  

실제 데이터/LLM 연동은 이후 단계에서 추가합니다.
"""
)

st.info("좌측 사이드바의 `pages` 메뉴에서 각 리포트 페이지를 선택해 레이아웃을 확인해보세요.")