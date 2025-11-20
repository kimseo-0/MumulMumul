# streamlit 앱 진입점
from __future__ import annotations
import streamlit as st

st.set_page_config(
    page_title="머물머물 관리자 대시보드",
    page_icon="🖥️",
    layout="centered"
)

pages = [
    st.Page(
        page="pages/example.py",
        title="example",
        icon="📃",
        default=True,
        url_path="example",
    ),
    st.Page(
        page="pages/report.py",
        title="Report",
        icon="📃",
        default=False,
        url_path="report",
    ),
]

nav = st.navigation(pages)
nav.run()
