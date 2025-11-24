# streamlit_app/attendance_report.py

import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta

from api.attendance import (
    get_camps,
    get_attendance_report,
)

st.set_page_config(
    page_title="출결 관리",
    page_icon="👥",
    layout="wide"
    )

# -----------------------------
# 캠프 리스트
# -----------------------------
camps = get_camps()
camp_name_to_id = {camp["name"]: camp["camp_id"] for camp in camps}
camp_names = list(camp_name_to_id.keys())

# -----------------------------
# 사이드바 UI
# -----------------------------
st.sidebar.header("캠프 설정")

today = date.today()
selected_camp = st.sidebar.selectbox("반 선택", camp_names)

start_date = st.sidebar.date_input("시작일", today - timedelta(days=7))
end_date = st.sidebar.date_input("종료일", today)

# -----------------------------
# API에서 리포트 가져오기
# -----------------------------
camp_id = camp_name_to_id[selected_camp]
payload = get_attendance_report(camp_id, start_date, end_date)

summary = payload["summary_cards"]
charts = payload["charts"]
tables = payload["tables"]
insights = payload["ai_insights"]

df_att = pd.DataFrame(charts["attendance_timeseries"])
df_students = pd.DataFrame(tables["student_list"])
df_risk = pd.DataFrame(tables["top_risk_students"])

# -----------------------------
# 화면
# -----------------------------
st.title(f"🧍 출결 & 이탈 위험 리포트 - {selected_camp}")

tab1, tab2 = st.tabs(["요약", "AI 분석"])

# -----------------------------
# (1) 요약 탭
# -----------------------------
with tab1:
    st.subheader("핵심 요약")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("평균 출석률", f"{summary['avg_attendance_rate']}%")
    col2.metric("3일 이하 접속자", summary["num_low_access_3days"])
    col3.metric("고위험", summary["num_risky"])
    col4.metric("주의", summary["num_warning"])

    st.markdown("### 출석률 추이")
    df_att_chart = df_att.rename(
        columns={"week_label": "주차", "attendance_rate": "출석률"}
    )
    chart = (
        alt.Chart(df_att_chart)
        .mark_line(point=True)
        .encode(x="주차:N", y="출석률:Q")
        .properties(height=300)
    )
    st.altair_chart(chart, width='stretch')

    st.markdown("### 위험 학습자 상위")
    if not df_risk.empty:
        st.table(df_risk)
    else:
        st.write("위험 학습자가 없습니다.")

    st.markdown("### 전체 학습자 리스트")
    st.dataframe(df_students, width='stretch')


# -----------------------------
# (2) AI 분석 탭
# -----------------------------
with tab2:
    # --- 기본 수치 / 텍스트 준비 (payload 기반) ---
    avg_attendance = summary["avg_attendance_rate"]
    low_access_count = summary["num_low_access_3days"]
    risky_count = summary["num_risky"]
    warning_count = summary["num_warning"]

    # charts["attendance_timeseries"]를 DataFrame으로
    df_att = pd.DataFrame(charts["attendance_timeseries"])
    if not df_att.empty:
        df_att = df_att.rename(
            columns={"week_label": "주차", "attendance_rate": "출석률"}
        )

    # 표 데이터들
    df_students = pd.DataFrame(tables["student_list"])
    df_risk = pd.DataFrame(tables["top_risk_students"])
    df_actions = pd.DataFrame(tables.get("per_student_actions", []))

    # --- 0. 상단 한 줄 요약 & 카드 형태 인사이트 ---
    colA, colB, colC = st.columns(3)
    colA.info(
        f"**출석·참여 패턴 요약**\n\n"
        f"{insights['summary_one_line']}"
    )
    colB.warning(
        "**주의 신호 요약**\n\n"
        f"{insights['risk_signals_summary']}\n\n"
        f"- 3일 이하 접속 학습자: {low_access_count}명\n"
        f"- 고위험: {risky_count}명 / 주의: {warning_count}명"
    )
    colC.success(
        "**운영 우선 과제(단기)**\n\n"
        f"{insights['short_term_actions']}"
    )

    st.markdown("---")

    # --- 1. 출석률 및 참여 경향 분석 ---
    st.markdown("### 1. 출석률 및 참여 경향 분석")

    left, right = st.columns([1.3, 1.2])

    with left:
        st.markdown("#### 1-1. 출석률 분석 요약")
        st.write(insights["attendance_summary"])

    with right:
        st.markdown("#### 1-2. 출석률 추이 그래프")
        if not df_att.empty:
            chart_att_ai = (
                alt.Chart(df_att)
                .mark_line(point=True)
                .encode(
                    x="주차:N",
                    y="출석률:Q",
                    tooltip=["주차", "출석률"],
                )
                .properties(height=260)
            )
            st.altair_chart(chart_att_ai, width='stretch')
            st.caption("주차별 출석률 변동을 통해 특정 구간 이후 이탈 신호를 확인할 수 있음.")
        else:
            st.write("출석률 시계열 데이터가 없음.")

    st.markdown("---")

    # --- 2. 위험 학습자 패턴 분석 ---
    st.markdown("### 2. 위험 학습자 패턴 분석")

    colX, colY = st.columns([1.4, 1.0])

    with colX:
        st.markdown("#### 2-1. 위험 신호/패턴 요약")
        st.write(insights["risk_signals_summary"])

    with colY:
        st.markdown("#### 2-2. 위험 학습자 상위 리스트")
        if not df_risk.empty:
            # student_id / name / class_id / days_active_7d / risk_level 등의 컬럼 가정
            show_cols = [
                c for c in df_risk.columns
                if c in ("student_id", "name", "class_id", "days_active_7d", "risk_level")
            ]
            st.table(df_risk[show_cols].set_index("name") if "name" in df_risk.columns else df_risk[show_cols])
        else:
            st.write("현재 위험 학습자가 없음.")

    st.markdown("---")

    # --- 3. 위험 학습자 개별 액션 제안 ---
    st.markdown("### 3. 위험 학습자 개별 액션 제안")

    st.markdown(
        """
        AI는 출결 패턴과 설문 기반 성향(있다면),  
        최근 접속/참여 데이터를 함께 고려하여  
        **주의·고위험 학습자별 개별 대응 방향**을 제안함.
        """
    )

    if not df_actions.empty:
        # per_student_actions: student_id, name, risk_level, pattern_type, recommended_action, priority, suggested_channel 등 가정
        show_cols = [
            c for c in df_actions.columns
            if c in ("name", "risk_level", "pattern_type", "recommended_action", "priority", "suggested_channel")
        ]
        st.table(df_actions[show_cols].set_index("name") if "name" in df_actions.columns else df_actions[show_cols])
    else:
        st.info("현재 선택된 반에는 개별 액션 제안이 필요한 위험 학습자가 없음.")

    st.markdown("---")

    # --- 4. 중기 운영 액션 정리 ---
    st.markdown("### 4. 중기(3주 이상) 운영 액션 제안")

    st.write(insights["mid_term_actions"])

    st.caption(
        "※ 위 인사이트는 출결 로그·회의 참여·질문 데이터 및 설문 성향(있을 경우)을 기반으로 "
        "LLM이 생성한 제안 결과임."
    )