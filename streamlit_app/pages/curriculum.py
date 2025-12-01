import streamlit as st
import pandas as pd
import altair as alt

from streamlit_app.api.curriculum import (
    fetch_camps,
    fetch_curriculum_report,
    fetch_curriculum_config,
    save_curriculum_config,
)

st.set_page_config(layout="wide")
st.title("📚 커리큘럼 난이도 & 추가 학습 요구 분석")

# 리포트 가이드
def render_curriculum_analysis_rules():
    """커리큘럼 난이도 & 추가 학습 요구 분석 기준 안내 블록."""
    st.markdown("""
    ### 📐 커리큘럼 분석 기준 (AI 인사이트가 따르는 룰)

    **1️⃣ '어려운 파트'(커리큘럼 내) 선정 기준**

    - 질문 비율 기준  
    - 해당 카테고리가 **커리큘럼 내(in) 질문의 20% 이상**이면 High-Friction Topic으로 간주함.
    - 질문 수 기준  
    - 질문 수 **상위 Top 3 카테고리**는 모두 어려운 파트 후보로 포함함.
    - 질문 패턴 기준  
    - "왜 이런 결과가 나오나요?", "A와 B 차이가 뭐죠?"처럼  
        **개념 혼란/이해도 부족**을 드러내는 질문이 많은 카테고리는 난이도가 높은 파트로 판단함.

    ---

    **2️⃣ '커리큘럼 외 추가 요구' 선정 기준**

    - 최소 언급 수  
    - 동일 주제에 대한 질문이 **2건 이상**이면 우연이 아닌 반복 요구로 판단함.
    - 비율 기준  
    - 커리큘럼 외(out) 질문의 **15% 이상**을 차지하면 주요 요구 토픽으로 간주함.
    - 주제 성격  
    - 포트폴리오, 커리어/면접, IDE·환경 설정, 협업(Git)처럼  
        **학습 성과와 직접 연결되는 주제**는 중요도 높게 다룸.

    ---

    **3️⃣ '즉시 보완 vs 다음 기수 개선' 기준**

    - **즉시 보완**
    - Week 1–2의 기초 파트이고, in 질문 비율이 **25% 이상**이거나 Top 3에 해당함.
    - 해당 파트에서 개념 혼란성 질문이 많이 발생함.
    - **다음 기수 개선**
    - Week 3–5의 심화 개념으로, 난이도는 높지만 상대적으로 질문 비율이 낮음.
    - 커리어/포트폴리오/환경 설정 등 **구조적 개선**이 필요한 영역임.

    ---

    **4️⃣ 참고한 교육·학습 분석 자료**

    - Learning Analytics Handbook (2022)  
    - Carnegie Mellon Eberly Center – Learning Engineering Framework  
    - Coursera Engagement Analytics Report (2020)  
    - Stanford HCI Learner Pattern Study (2019)  
    - Bloom’s Taxonomy & Cognitive Load Theory

    위 기준을 바탕으로 AI 인사이트가 생성되며,  
    운영진은 이 규칙을 참고하여 리포트의 해석 및 후속 액션을 결정할 수 있음.
    """)


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

# ----------------------------
# 커리큘럼 
# ----------------------------
with st.sidebar.expander("📚 커리큘럼", expanded=False):
    # 1) 서버에서 기존 설정 불러오기
    config = fetch_curriculum_config(camp_id=camp_id)  # 없으면 None 또는 {}
    existing_weeks = (config or {}).get("weeks", [])

    # 기본 주차 수는 기존 설정 or 6주
    default_week_count = max([w["week_index"] for w in existing_weeks], default=6) if existing_weeks else 6

    week_count = st.number_input(
        "주차 수",
        min_value=1,
        max_value=30,
        value=default_week_count,
        step=1,
        key="curriculum_week_count",
    )

    new_weeks = []

    for i in range(1, week_count + 1):
        # 기존 값 있으면 가져오기
        existing = next((w for w in existing_weeks if w["week_index"] == i), None)
        default_label = existing["week_label"] if existing else f"{i}주차"
        default_topics = ",".join(existing.get("topics", [])) if existing else ""

        with st.expander(f"{i}주차 설정", expanded=(i == 1)):
            week_label = st.text_input(
                f"{i}주차 라벨",
                value=default_label,
                key=f"week_label_{i}",
            )
            topic_raw = st.text_input(
                f"{i}주차 토픽 키 (쉼표 구분, 예: python_basics,pandas)",
                value=default_topics,
                key=f"week_topics_{i}",
            )
            topics = [t.strip() for t in topic_raw.split(",") if t.strip()]

            new_weeks.append(
                {
                    "week_index": i,
                    "week_label": week_label,
                    "topics": topics,
                }
            )

    if st.button("💾 커리큘럼 저장", use_container_width=True):
        save_curriculum_config(
            camp_id=camp_id,
            weeks=new_weeks,
        )
        st.success("커리큘럼 구조를 저장했어요.")

# --------------------------------
# 1-1) 리포트 생성 버튼 + 세션 캐싱
# --------------------------------
if "curriculum_reports" not in st.session_state:
    st.session_state["curriculum_reports"] = {} 

report_key = f"{camp_id}_{week_index}"

generate_clicked = st.sidebar.button("리포트 생성하기") 

if generate_clicked:
    with st.spinner("리포트 생성 중입니다..."): 
        payload = fetch_curriculum_report(
            camp_id=camp_id,
            week_index=week_index,
        )
        st.session_state["curriculum_reports"][report_key] = payload

# 세션에서 현재 선택된 캠프/주차의 리포트 가져오기
payload = st.session_state["curriculum_reports"].get(report_key)

# 아직 생성된 리포트가 없다면 안내만 띄우고 종료
if payload is None:
    week_label = f"{week_index}주차"
    st.info(
        f"현재 **{camp_name} / {week_label}** 리포트가 없습니다.\n\n"
        "좌측 사이드바에서 **'해당 Week 리포트 생성하기'** 버튼을 눌러 리포트를 생성해 주세요."
    )
    st.stop()

# --------------------------------
# 2) (기존) 리포트 payload 사용
#    - 여기부터는 기존 코드 그대로 사용 가능
# --------------------------------
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

    # ---------------------------
    # 분석 기준 토글 / 팝업 블록
    # ---------------------------
    with st.container():
        with st.expander("🔎 AI 분석 기준 보기", expanded=False):
            render_curriculum_analysis_rules()

    st.markdown("---")

    # ---------------------------
    # 상단 요약 블록
    # ---------------------------
    colA, colB, colC = st.columns(3)

    with colA:
        st.markdown("#### 🔥 가장 어려운 파트 요약")
        st.info(ai_insights.get("hardest_part_summary", "가장 어려운 파트 요약 없음"))

    with colB:
        st.markdown("#### 🧩 커리큘럼 외 질문 요약")
        st.warning(ai_insights.get("curriculum_out_summary", "커리큘럼 외 질문 요약 없음"))

    with colC:
        st.markdown("#### 🛠 개선 방향 요약")
        st.success(ai_insights.get("improvement_summary", "개선 방향 요약 없음"))
    # colA.info(ai_insights.get("hardest_part_summary", "가장 어려운 파트 요약 없음"))
    # colB.warning(ai_insights.get("curriculum_out_summary", "커리큘럼 외 질문 요약 없음"))
    # colC.success(ai_insights.get("improvement_summary", "개선 방향 요약 없음"))

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
