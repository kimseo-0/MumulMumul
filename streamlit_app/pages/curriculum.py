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
# 1) 캠프 목록 / 주차 선택
# --------------------------------
camps = fetch_camps()  # [{camp_id, name, ...}, ...] 형태라고 가정
camp_name_to_id = {c["name"]: c["camp_id"] for c in camps}

st.sidebar.header("필터 설정")

camp_name = st.sidebar.selectbox("반 선택", list(camp_name_to_id.keys()))
camp_id = camp_name_to_id[camp_name]

weeks = ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5", "Week 6"]
selected_week_label = st.sidebar.selectbox("주차 선택", weeks)
week_index = int(selected_week_label.split()[1])  # "Week 3" -> 3

# --------------------------------
# 2) 리포트 API 호출
# --------------------------------
payload = fetch_curriculum_report(
    camp_id=camp_id,
    week_index=week_index,
)

summary = payload["summary_cards"]
charts = payload["charts"]
tables = payload["tables"]
ai_insights = payload["ai_insights"]

# ================================
# DataFrame 변환 유틸
# ================================
# 1) 카테고리별 질문 수 (차트용) : charts["questions_by_category"]
df_cat_raw = pd.DataFrame(charts.get("questions_by_category", []))  # [{category, scope, question_count}, ...]

if not df_cat_raw.empty:
    # scope 무시하고 카테고리별 총합으로 집계
    df_categories = (
        df_cat_raw.groupby("category", as_index=False)["question_count"]
        .sum()
        .rename(columns={"question_count": "질문 수"})
        .sort_values("질문 수", ascending=False)
    )
else:
    df_categories = pd.DataFrame(columns=["category", "질문 수"])

# 2) 분류별 질문 리스트 (tables["questions_grouped_by_category"])
question_rows = []
for block in tables.get("questions_grouped_by_category", []):
    # block: {category, scope, questions: [QuestionRow...]}
    for q in block.get("questions", []):
        question_rows.append(
            {
                "category": q.get("category"),
                "scope": q.get("scope"),
                "question_text": q.get("question_text"),
                "created_at": q.get("created_at"),
            }
        )

df_questions = pd.DataFrame(question_rows)

# 3) 커리큘럼 외 질문 리스트
df_outer = pd.DataFrame(
    [
        {
            "category": q.get("category"),
            "question_text": q.get("question_text"),
            "created_at": q.get("created_at"),
        }
        for q in tables.get("curriculum_out_questions", [])
    ]
)

# ================================
# 탭 구성
# ================================
tab_summary, tab_ai = st.tabs(["요약", "AI 심층 분석"])

# =========================================================
# (1) 요약 탭
# =========================================================
with tab_summary:
    # 주차 라벨은 payload 기준으로 표시
    week_label = payload.get("week_label", f"{week_index}주차")
    st.subheader(f"📌 {week_label} 요약 ({camp_name})")

    total_questions = summary.get("total_questions", 0)
    out_ratio = summary.get("curriculum_out_ratio", 0.0) * 100  # 0~1 → %
    in_q = summary.get("curriculum_in_questions", 0)
    out_q = summary.get("curriculum_out_questions", 0)
    num_categories = df_categories["category"].nunique() if not df_categories.empty else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("전체 질문 수", f"{total_questions}건")
    col2.metric("커리큘럼 외 비율", f"{out_ratio:.1f}%")
    col3.metric("질문 분류 수", f"{num_categories}개")

    # ---------------------------
    # 상위 질문 분류 Top 3
    # ---------------------------
    st.markdown("### 🔥 이번 주 상위 질문 분류")

    top_cats = summary.get("top_question_categories", [])  # [TopQuestionCategory... dict]
    # 최대 3개만 사용
    top_cats = top_cats[:3]

    colA, colB, colC = st.columns(3)
    cols = [colA, colB, colC]

    for col, cat in zip(cols, top_cats):
        col.info(
            f"""
### {cat['category']}
**{int(cat['question_count'])}건**  
*(scope: { '커리큘럼 내' if cat['scope']=='in' else '커리큘럼 외' })*
"""
        )

    st.markdown("---")
    st.markdown("### 📊 질문 분류별 질문 수")

    if not df_categories.empty:
        chart = (
            alt.Chart(df_categories)
            .mark_bar()
            .encode(
                x="질문 수:Q",
                y=alt.Y("category:N", sort="-x", title="질문 분류"),
                color="category:N",
            )
            .properties(height=250)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.write("질문 데이터가 없습니다.")

    # ---------------------------
    # 분류별 질문 리스트
    # ---------------------------
    st.markdown("#### 📋 분류별 질문 리스트")

    if not df_categories.empty and not df_questions.empty:
        selected_cat = st.selectbox(
            "분류 선택",
            df_categories["category"].tolist(),
        )
        for q in df_questions[df_questions["category"] == selected_cat]["question_text"]:
            st.markdown(f"- {q}")
    else:
        st.write("표시할 질문이 없습니다.")

    # ---------------------------
    # 커리큘럼 내/외 비율 (파이)
    # ---------------------------
    st.markdown("---")
    st.markdown("### 🥤 커리큘럼 내/외 질문 비율")

    scope_ratio = charts.get("curriculum_scope_ratio", [])
    if scope_ratio:
        df_ratio = pd.DataFrame(
            [
                {
                    "type": "커리큘럼 내" if r["scope"] == "in" else "커리큘럼 외",
                    "count": r["question_count"],
                }
                for r in scope_ratio
            ]
        )

        pie = (
            alt.Chart(df_ratio)
            .mark_arc(innerRadius=40)
            .encode(theta="count:Q", color="type:N")
            .properties(height=260)
        )
        st.altair_chart(pie, use_container_width=True)
    else:
        st.write("커리큘럼 내/외 데이터가 없습니다.")

    st.markdown("#### 커리큘럼 외 질문 리스트")

    if not df_outer.empty:
        for q in df_outer["question_text"]:
            st.markdown(f"- {q}")
    else:
        st.write("커리큘럼 외 질문이 없습니다.")

# =========================================================
# (2) AI 심층 분석 탭
# =========================================================
with tab_ai:
    st.subheader(f"🤖 AI 심층 분석 — {week_label} ({camp_name})")

    colA, colB, colC = st.columns(3)

    colA.info(ai_insights.get("hardest_part_summary", "가장 어려운 파트 요약 없음"))
    colB.warning(ai_insights.get("curriculum_out_summary", "커리큘럼 외 질문 요약 없음"))
    colC.success(ai_insights.get("improvement_summary", "개선 방향 요약 없음"))

    st.markdown("---")

    # -------------------
    # 상세 보고서
    # -------------------
    st.markdown("## 📄 AI 인사이트 상세 보고서")

    # 1) 이번 주 가장 어려워한 파트
    st.markdown("### 1. 이번 주 가장 어려워한 파트")

    hardest_parts = ai_insights.get("hardest_parts_detail", [])
    if hardest_parts:
        for block in hardest_parts:
            st.markdown(f"#### • {block['part_label']}")
            if block.get("main_categories"):
                st.markdown(
                    "- 주요 분류: " + ", ".join(block["main_categories"])
                )
            if block.get("example_questions"):
                st.markdown("**예시 질문**")
                for q in block["example_questions"]:
                    st.markdown(f"- {q}")
            if block.get("root_cause_analysis"):
                st.markdown("**원인 분석**")
                st.markdown(block["root_cause_analysis"])
            if block.get("improvement_direction"):
                st.markdown("**개선 방향**")
                st.markdown(block["improvement_direction"])
            st.markdown("---")
    else:
        st.write("어려운 파트에 대한 상세 분석이 없습니다.")

    # 2) 커리큘럼 외 질문 분석
    st.markdown("### 2. 커리큘럼 외 질문 분석")

    extra_topics = ai_insights.get("extra_topics_detail", [])
    if extra_topics:
        for topic in extra_topics:
            st.markdown(f"#### • {topic['topic_label']} ({topic['question_count']}건)")
            if topic.get("example_questions"):
                st.markdown("**예시 질문**")
                for q in topic["example_questions"]:
                    st.markdown(f"- {q}")
            if topic.get("suggested_session_idea"):
                st.markdown("**추가 세션/자료 제안**")
                st.markdown(topic["suggested_session_idea"])
            st.markdown("---")
    else:
        st.write("커리큘럼 외 질문에 대한 상세 분석이 없습니다.")

    # 3) 운영진 액션 정리
    st.markdown("### 3. 운영진 액션 정리")

    st.markdown("#### 3-1. 커리큘럼/난이도 개선 액션")
    st.markdown(ai_insights.get("curriculum_improvement_actions", "내용 없음"))

    st.markdown("#### 3-2. 커리큘럼 외 세션/자료 제안")
    st.markdown(ai_insights.get("extra_session_suggestions", "내용 없음"))
