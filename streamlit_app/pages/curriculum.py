import streamlit as st
import pandas as pd
import altair as alt

from streamlit_app.api.curriculum import (
    fetch_camps,
    fetch_curriculum_report,
)

st.set_page_config(layout="wide")
st.title("📚 커리큘럼 난이도 & 추가 학습 요구 분석")

# --------------------------------
# 1) 캠프 목록 / 주차 목록 API로 가져오기
# --------------------------------
camps = fetch_camps()
camp_name_to_id = {c["name"]: c["camp_id"] for c in camps}

st.sidebar.header("필터 설정")

camp_name = st.sidebar.selectbox("반 선택", list(camp_name_to_id.keys()))
camp_id = camp_name_to_id[camp_name]

weeks = ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5", "Week 6"]
selected_week = st.sidebar.selectbox("주차 선택", weeks)

# --------------------------------
# 2) 리포트 API 호출
# --------------------------------
payload = fetch_curriculum_report(
    camp_id=camp_id,
    week_index=selected_week.split()[1],
)

summary = payload["summary_cards"]
tables = payload["tables"]
charts = payload["charts"]
ai_insights = payload["ai_insights"]

# Pandas 변환
df_questions = pd.DataFrame(tables["question_list"])
df_categories = pd.DataFrame(tables["question_counts"])
df_outer = pd.DataFrame(tables["outer_question_list"])

# --------------------------------
# 탭 구성
# --------------------------------
tab_summary, tab_ai = st.tabs(["요약", "AI 심층 분석"])

# =========================================================
# (1) 요약 탭
# =========================================================
with tab_summary:
    st.subheader(f"📌 {selected_week} 요약")

    col1, col2, col3 = st.columns(3)
    col1.metric("전체 질문 수", f"{summary['total_questions']}건")
    col2.metric("커리큘럼 외 비율", f"{summary['outer_ratio']}%")
    col3.metric("질문 분류 수", f"{summary['num_categories']}개")

    # ---------------------------
    # 상위 질문 분류
    # ---------------------------
    st.markdown("### 🔥 이번 주 상위 질문 분류")
    top3 = df_categories.head(3)

    colA, colB, colC = st.columns(3)
    for col, (_, row) in zip([colA, colB, colC], top3.iterrows()):
        col.info(
            f"""
### {row['category']}
**{int(row['count'])}건**
"""
        )

    # ---------------------------
    # 분류별 질문 수 그래프
    # ---------------------------
    st.markdown("---")
    st.markdown("### 📊 질문 분류별 질문 수")

    chart = (
        alt.Chart(df_categories)
        .mark_bar()
        .encode(
            x="count:Q",
            y=alt.Y("category:N", sort="-x"),
            color="category:N",
        )
        .properties(height=250)
    )
    st.altair_chart(chart, use_container_width=True)

    # ---------------------------
    # 분류별 질문 리스트
    # ---------------------------
    st.markdown("#### 📋 분류별 질문 리스트")
    selected_cat = st.selectbox("분류 선택", df_categories["category"].tolist())

    for q in df_questions[df_questions["category"] == selected_cat]["content"]:
        st.markdown(f"- {q}")

    # ---------------------------
    # 커리큘럼 외 질문
    # ---------------------------
    st.markdown("---")
    st.markdown("### 🥤 커리큘럼 외 질문 비율")

    df_ratio = pd.DataFrame(
        [
            {"type": "커리큘럼 내", "count": summary["inner_questions"]},
            {"type": "커리큘럼 외", "count": summary["outer_questions"]},
        ]
    )

    pie = (
        alt.Chart(df_ratio)
        .mark_arc(innerRadius=40)
        .encode(theta="count:Q", color="type:N")
        .properties(height=260)
    )
    st.altair_chart(pie, use_container_width=True)

    st.markdown("#### 커리큘럼 외 질문 리스트")
    for q in df_outer["content"]:
        st.markdown(f"- {q}")

# =========================================================
# (2) AI 심층 분석 탭
# =========================================================
with tab_ai:
    st.subheader(f"🤖 AI 심층 분석 — {selected_week}")

    colA, colB, colC = st.columns(3)

    colA.info(ai_insights["hardest_part_summary"])
    colB.warning(ai_insights["outer_summary"])
    colC.success(ai_insights["actions_summary"])

    st.markdown("---")

    # -------------------
    # 상세 보고서
    # -------------------
    st.markdown("## 📄 AI 인사이트 상세 보고서")

    # 1) 어려운 파트
    st.markdown("### 1. 이번 주 가장 어려워한 파트")
    for block in ai_insights["hardest_part_detail"]:
        st.markdown(f"#### • {block['category']}")
        for q in block["examples"]:
            st.markdown(f"- {q}")

    st.markdown("---")

    # 2) 커리큘럼 외 질문
    st.markdown("### 2. 커리큘럼 외 질문 분석")
    for block in ai_insights["outer_detail"]:
        st.markdown(f"#### • {block['category']}")
        for q in block["examples"]:
            st.markdown(f"- {q}")

    st.markdown("---")

    # 3) 운영진 액션
    st.markdown("### 3. 운영진 액션 정리")
    st.markdown(ai_insights["action_detail"])
