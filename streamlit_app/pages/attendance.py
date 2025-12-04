# streamlit_app/attendance_report.py

import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, datetime, timedelta

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
# 헬퍼: 캠프 + 주차 → 날짜 범위 계산
# -----------------------------
def get_week_date_range(camp: dict, week_label: str) -> tuple[date, date]:
    """
    캠프 시작일 기준으로 주차별 날짜 범위를 계산.
    - week_label: 'Week 1' 형태
    - camp["start_date"], camp.get("end_date")는 ISO 문자열이라고 가정.
    """
    # week_label에서 숫자 부분만 추출 (예: 'Week 3' -> 3)
    try:
        week_idx = int(week_label.split()[-1])
    except Exception:
        week_idx = 1

    # 캠프 시작일 파싱
    today = date.today()
    camp_start_str = camp.get("start_date")
    if camp_start_str:
        try:
            # '2025-11-01' 같은 ISO 포맷 가정
            camp_start = datetime.fromisoformat(camp_start_str).date()
        except Exception:
            camp_start = today - timedelta(days=7)  # fallback
    else:
        camp_start = today - timedelta(days=7)

    # 주차 시작일 = 캠프 시작일 + 7 * (week_idx - 1)
    start_date = camp_start + timedelta(days=7 * (week_idx - 1))
    end_date = start_date + timedelta(days=6)

    # 캠프 종료일이 있으면 클램핑
    camp_end_str = camp.get("end_date")
    if camp_end_str:
        try:
            camp_end = datetime.fromisoformat(camp_end_str).date()
            if end_date > camp_end:
                end_date = camp_end
        except Exception:
            pass

    # 오늘 이후로는 잘라주기
    if end_date > today:
        end_date = today

    return start_date, end_date


# -----------------------------
# 캠프 리스트
# -----------------------------
camps = get_camps()
camp_name_to_obj = {camp["name"]: camp for camp in camps}
camp_names = list(camp_name_to_obj.keys())

# -----------------------------
# 사이드바 UI
# -----------------------------
st.sidebar.header("캠프 / 주차 설정")

selected_camp_name = st.sidebar.selectbox("반 선택", camp_names)

# 커리큘럼 리포트처럼 Week 단위 선택 (필요 시 범위 조정 가능)
weeks = ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5", "Week 6"]
selected_week = st.sidebar.selectbox("주차 선택", weeks)

generate_btn = st.sidebar.button("출결 리포트 생성")

selected_camp = camp_name_to_obj[selected_camp_name]

payload = None
start_date = None
end_date = None

if generate_btn:
    # 선택한 주차 → 날짜 범위 변환
    start_date, end_date = get_week_date_range(selected_camp, selected_week)

    # -----------------------------
    # API에서 리포트 가져오기
    # -----------------------------
    camp_id = selected_camp["camp_id"]
    payload = get_attendance_report(camp_id, start_date, end_date)

# -----------------------------
# 화면
# -----------------------------
st.title(f"🧍 출결 & 이탈 위험 리포트 - {selected_camp_name}")

if payload is None:
    st.info("좌측에서 **반과 주차를 선택**한 뒤, `📊 이 주차 출결 리포트 생성` 버튼을 눌러 리포트를 확인하세요.")
else:
    summary = payload["summary_cards"]
    charts = payload["charts"]
    tables = payload["tables"]
    insights = payload["ai_insights"]

    df_att = pd.DataFrame(charts["attendance_timeseries"])
    df_students = pd.DataFrame(tables["student_list"])
    df_risk = pd.DataFrame(tables["top_risk_students"])

    # 선택된 주차 / 날짜 범위 표시
    if start_date and end_date:
        st.caption(f"선택 주차: **{selected_week}**  |  분석 기간: **{start_date} ~ {end_date}**")

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
        st.altair_chart(chart, width="stretch")

        st.markdown("### 위험 학습자 상위")
        if not df_risk.empty:
            st.table(df_risk)
        else:
            st.write("위험 학습자가 없습니다.")

        st.markdown("### 전체 학습자 리스트")
        st.dataframe(df_students, width="stretch")

    # -----------------------------
    # (2) AI 분석 탭
    # -----------------------------
    with tab2:
        # --- 기본 수치 / 텍스트 준비 (payload 기반) ---
        avg_attendance = summary["avg_attendance_rate"]
        low_access_count = summary["num_low_access_3days"]
        risky_count = summary["num_risky"]
        warning_count = summary["num_warning"]

        df_att_ai = pd.DataFrame(charts["attendance_timeseries"])
        if not df_att_ai.empty:
            df_att_ai = df_att_ai.rename(
                columns={"week_label": "주차", "attendance_rate": "출석률"}
            )

        df_students_ai = pd.DataFrame(tables["student_list"])
        df_risk_ai = pd.DataFrame(tables["top_risk_students"])
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
            if not df_att_ai.empty:
                chart_att_ai = (
                    alt.Chart(df_att_ai)
                    .mark_line(point=True)
                    .encode(
                        x="주차:N",
                        y="출석률:Q",
                        tooltip=["주차", "출석률"],
                    )
                    .properties(height=260)
                )
                st.altair_chart(chart_att_ai, width="stretch")
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
            if not df_risk_ai.empty:
                show_cols = [
                    c
                    for c in df_risk_ai.columns
                    if c in ("user_id", "student_id", "name", "class_id", "days_active_7d", "risk_level")
                ]
                df_show = df_risk_ai[show_cols]
                if "name" in df_show.columns:
                    df_show = df_show.set_index("name")
                st.table(df_show)
            else:
                st.write("현재 위험 학습자가 없음.")

        st.markdown("---")

        # --- 3. 위험 학습자 개별 액션 제안 ---
        st.markdown("### 3. 위험 학습자 개별 액션 제안")

        st.markdown(
            """
            AI는 출결 패턴과 (있다면) 설문 기반 성향,  
            최근 접속/참여 데이터를 함께 고려하여  
            **주의·고위험 학습자별 개별 대응 방향**을 제안함.
            """
        )

        if not df_actions.empty:
            show_cols = [
                c
                for c in df_actions.columns
                if c in ("name", "risk_level", "pattern_type", "recommended_action", "priority", "suggested_channel")
            ]
            df_actions_show = df_actions[show_cols]
            if "name" in df_actions_show.columns:
                df_actions_show = df_actions_show.set_index("name")
            st.table(df_actions_show)
        else:
            st.info("현재 선택된 반에는 개별 액션 제안이 필요한 위험 학습자가 없음.")

        st.markdown("---")

        # --- 4. 중기 운영 액션 정리 ---
        st.markdown("### 4. 중기(3주 이상) 운영 액션 제안")

        st.write(insights["mid_term_actions"])

        st.caption(
            "※ 위 인사이트는 출결 로그·회의 참여·질문 데이터 및 (있을 경우) 설문 성향을 기반으로 "
            "LLM이 생성한 제안 결과임."
        )
