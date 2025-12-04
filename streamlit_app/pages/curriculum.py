import streamlit as st
import pandas as pd
import altair as alt

from streamlit_app.api.curriculum import (
    analyze_curriculum_text,
    create_curriculum_report,
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
# 0) 세션 기반 데이터 캐시 설정  🔥
# --------------------------------
if "curriculum_session" not in st.session_state:  # 한 번만 초기화
    st.session_state["curriculum_session"] = {
        "camps": None,                       # fetch_camps() 결과
        "camp_name_to_id": None,            # {name: id}
        "curriculum_config_by_camp": {},    # {camp_id: config}
        "curriculum_reports": {},           # {f"{camp_id}_{week_index}": payload}
    }

session_cache = st.session_state["curriculum_session"]

# --- 캠프 목록은 세션에 한 번만 저장 ---
if session_cache["camps"] is None:
    camps = fetch_camps()  # [{camp_id, name, ...}, ...] 가정
    camp_name_to_id = {c["name"]: c["camp_id"] for c in camps}
    session_cache["camps"] = camps
    session_cache["camp_name_to_id"] = camp_name_to_id
else:
    camps = session_cache["camps"]
    camp_name_to_id = session_cache["camp_name_to_id"]

# --------------------------------
# 1) 캠프 목록 / 주차 선택
# --------------------------------
st.sidebar.header("필터 설정")

camp_name = st.sidebar.selectbox("반 선택", list(camp_name_to_id.keys()))
camp_id = camp_name_to_id[camp_name]

weeks = ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5", "Week 6"]
selected_week_label = st.sidebar.selectbox("주차 선택", weeks)
week_index = int(selected_week_label.split()[1])  # "Week 3" -> 3

# --------------------------------
# 1-1) 리포트 생성 버튼 + 세션 캐싱
# --------------------------------
report_key = f"{camp_id}_{week_index}"
reports_cache = session_cache["curriculum_reports"]

# 1) 세션에서 먼저 찾기
payload = reports_cache.get(report_key)

# 2) 세션에 없으면 → 백엔드(DB)에서 한 번 조회해서 있으면 캐시
if payload is None:
    db_report = fetch_curriculum_report(camp_id=camp_id, week_index=week_index)
    if db_report is not None:
        payload = db_report
        reports_cache[report_key] = payload

generate_clicked = st.sidebar.button("리포트 생성하기")
if generate_clicked:
    with st.spinner("리포트 생성 중입니다..."):
        payload = create_curriculum_report(
            camp_id=camp_id,
            week_index=week_index,
        )
        session_cache["curriculum_reports"][report_key] = payload

# 세션에서 현재 선택된 캠프/주차의 리포트 가져오기
payload = session_cache["curriculum_reports"].get(report_key)

# 아직 생성된 리포트가 없다면 안내만 띄우고 종료
if payload is None:
    week_label_fallback = f"{week_index}주차"
    st.info(
        f"현재 **{camp_name} / {week_label_fallback}** 리포트가 없습니다.\n\n"
        "좌측 사이드바에서 **'리포트 생성하기'** 버튼을 눌러 리포트를 생성해 주세요."
    )
    st.stop()

# --------------------------------
# 2) 리포트 payload 사용
# --------------------------------
summary = payload["summary_cards"]
charts = payload["charts"]
tables = payload["tables"]
ai_insights = payload["ai_insights"]

week_label = payload.get("week_label", f"{week_index}주차")

# ================================
# DataFrame 변환 유틸
# ================================
# 1) 카테고리별 질문 수 (차트용)
df_cat_raw = pd.DataFrame(charts.get("questions_by_category", []))  # [{category, scope, question_count}, ...]

if not df_cat_raw.empty:
    # scope 무시하고 카테고리별 총합으로 집계
    df_categories = (
        df_cat_raw.groupby("category", as_index=False)["question_count"]
        .sum()
        .rename(columns={"question_count": "question_count"})
        .sort_values("question_count", ascending=False)
    )
else:
    df_categories = pd.DataFrame(columns=["category", "question_count"])

# 2) 분류별 질문 리스트 (pattern_tags, intent는 지금은 없음 → TODO)
question_rows = []
for block in tables.get("questions_grouped_by_category", []):
    category = block.get("category")
    scope = block.get("scope")
    for q in block.get("questions", []):
        question_rows.append(
            {
                "category": category,
                "scope": scope,
                "question_text": q.get("question_text"),
                "created_at": q.get("created_at"),
                "pattern_tags": q.get("pattern_tags") or [],
                "intent": q.get("intent"),
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

# 4) 패턴 전체 분포
raw_stats = payload.get("raw_stats", {})
pattern_stats = raw_stats.get("pattern_stats", [])

df_pattern_overall = pd.DataFrame(pattern_stats)

# 5) 카테고리별 주요 패턴
cat_pattern_raw = raw_stats.get("category_pattern_summary", [])
category_pattern_summary = []
for row in cat_pattern_raw:
    if row.get("patterns"):
        pattern_str = ", ".join(
            f"{p['tag']}({p['count']})" for p in row["patterns"]
        )
    else:
        pattern_str = ""
    category_pattern_summary.append(
        {
            "category": row["category"],
            "patterns": pattern_str,
            "summary": "",  # 나중에 LLM이 한 줄 요약 채워주게 해도 됨
        }
    )

# 6) 커리큘럼 강화 우선순위
raw_stats = payload.get("raw_stats", {})
priority_rows = raw_stats.get("priority", [])

df_priority = pd.DataFrame(priority_rows)

# ================================
# 탭 구성
# ================================
tab_curriculum, tab_summary, tab_ai = st.tabs(
    ["📚 커리큘럼 설정·분석", "요약", "AI 심층 분석"]
)

# =========================================================
# (탭 1) 📚 커리큘럼 설정·분석 탭
# =========================================================
with tab_curriculum:
    st.subheader(f"📚 커리큘럼 설정·분석 — {camp_name}")

    config_cache = session_cache["curriculum_config_by_camp"]

    preview_container = st.container()

    # 1) 현재 저장된 커리큘럼 불러오기 (캠프별 1회)
    config = config_cache.get(camp_id)
    if config is None:
        config = fetch_curriculum_config(camp_id=camp_id) or {}
        config_cache[camp_id] = config

    existing_weeks = config.get("weeks", [])

    st.markdown("####  커리큘럼 텍스트 자동 분석")

    raw_text = st.text_area(
        "커리큘럼 전체 설명을 붙여넣어 주세요. (1주차 ~ N주차)",
        height=180,
        key="curriculum_raw_text",
        placeholder=(
            "예시)\n"
            "1주차: 파이썬 기초, 자료형, 조건문, 반복문\n"
            "2주차: Numpy / Pandas 데이터 처리\n"
            "3주차: 시각화, Matplotlib, EDA 프로젝트\n"
            "4주차: NLP 네트워크, 연관어 분석 ..."
        ),
    )

    col_auto_1, col_auto_2 = st.columns([2, 3])
    with col_auto_1:
        if st.button("🧠 텍스트로 자동 세팅", use_container_width=True):
            config_cache[camp_id] = {}
            if raw_text.strip():
                with st.spinner("LLM으로 커리큘럼 구조 분석 중..."):
                    auto_config = analyze_curriculum_text(
                        camp_id=camp_id,
                        raw_text=raw_text,
                    )
                    
                    config_cache[camp_id] = auto_config
                    existing_weeks = auto_config.get("weeks", [])
                    st.success("커리큘럼 텍스트를 기반으로 주차별 구조를 자동 완성했어요.")
            else:
                st.warning("커리큘럼 텍스트를 먼저 입력해 주세요.")

    st.markdown("---")

    st.markdown("#### 주차별 커리큘럼 직접 수정")

    # 최신 existing_weeks 기준으로 폼 구성
    existing_weeks = config_cache.get(camp_id, {}).get("weeks", [])

    # 기본 주차 수는 기존 설정 or 6주
    if existing_weeks:
        default_week_count = max([w.get("week_index", 0) for w in existing_weeks] + [1])
    else:
        default_week_count = 6

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
        existing = next((w for w in existing_weeks if w.get("week_index") == i), None)
        default_label = existing.get("week_label") if existing else f"{i}주차"
        default_topics = ",".join(existing.get("topics", [])) if existing else ""

        with st.expander(f"{i}주차 설정", expanded=(i == 1)):
            week_label_input = st.text_input(
                f"{i}주차 라벨",
                value=default_label,
                key=f"week_label_{camp_id}_{i}",
            )
            topic_raw = st.text_input(
                f"{i}주차 토픽 키 (쉼표 구분, 예: python_basics,pandas)",
                value=default_topics,
                key=f"week_topics_{camp_id}_{i}",
            )
            topics = [t.strip() for t in topic_raw.split(",") if t.strip()]

            new_weeks.append(
                {
                    "week_index": i,
                    "week_label": week_label_input,
                    "topics": topics,
                }
            )

    if st.button("💾 커리큘럼 저장", use_container_width=True, key="save_curriculum_btn"):
        config_cache[camp_id] = {}
        save_curriculum_config(
            camp_id=camp_id,
            weeks=new_weeks,
        )
        config_cache[camp_id] = {
            "weeks": new_weeks,
        }
        st.success("커리큘럼 구조를 저장했어요.")

    with preview_container:
        st.markdown("#### 현재 커리큘럼 구조 미리보기")

        latest_config = config_cache.get(camp_id, {})
        existing_weeks = latest_config.get("weeks", [])

        if existing_weeks:
            df_weeks = pd.DataFrame(existing_weeks)
            st.dataframe(df_weeks, hide_index=True, use_container_width=True)
        else:
            st.info("아직 저장된 커리큘럼 구조가 없습니다. 자동 세팅이나 직접 입력 후 저장해 주세요.")

# =========================================================
# (1) 요약 탭
# =========================================================
with tab_summary:
    st.subheader(f"📌 {week_label} 요약 ({camp_name})")

    total_questions = summary.get("total_questions", 0)
    out_ratio = summary.get("curriculum_out_ratio", 0.0) * 100  # 0~1 → %
    in_q = summary.get("curriculum_in_questions", 0)
    out_q = summary.get("curriculum_out_questions", 0)
    num_categories = df_categories["category"].nunique() if not df_categories.empty else 0

    # 1. 상단 Summary Cards
    st.markdown("### 🔢 핵심 지표")

    col1, col2, col3 = st.columns(3)
    col1.metric("전체 질문 수", f"{total_questions}건")
    col2.metric("커리큘럼 외 비율", f"{out_ratio:.1f}%")
    col3.metric("질문 분류 수", f"{num_categories}개")

    # 2. 상위 질문 분류 Top 3
    st.markdown("### 🔥 상위 질문 분류 Top 3")

    top_cats = summary.get("top_question_categories", [])[:3]

    colA, colB, colC = st.columns(3)
    cols = [colA, colB, colC]

    for col, cat in zip(cols, top_cats):
        scope_label = "커리큘럼 내" if cat["scope"] == "in" else "커리큘럼 외"
        col.info(
            f"**{cat['category']}**  \n"
            f"{int(cat['question_count'])}건  \n"
            f"*{scope_label}*"
        )
    
    st.markdown("---")

    # 3. 질문 패턴 분포 (전체)
    st.markdown("### 🧩 이번 주 질문 패턴 분포")

    if not df_pattern_overall.empty:
        chart_pattern = (
            alt.Chart(df_pattern_overall)
            .mark_bar()
            .encode(
                x=alt.X("count:Q", title="질문 수"),
                y=alt.Y("tag:N", sort="-x", title="패턴 태그"),
                tooltip=[
                    "tag",
                    "count",
                    alt.Tooltip("ratio:Q", format=".0%"),
                ],
            )
            .properties(height=220)
        )
        st.altair_chart(chart_pattern, use_container_width=True)

        top_tag_row = df_pattern_overall.sort_values("count", ascending=False).iloc[0]
        st.caption(
            f"→ 이번 주에는 **{top_tag_row['tag']}** 패턴의 질문이 가장 많이 관찰되었음."
        )
    else:
        st.write("패턴 통계 데이터가 없습니다.")

    st.markdown("---")

    # 4. 커리큘럼 강화 우선순위 Top 3
    st.markdown("### 🧱 커리큘럼 강화 우선순위 Top 3")

    if not df_priority.empty:
        st.dataframe(
            df_priority[
                ["rank", "category", "difficulty_level", "main_patterns", "action_hint"]
            ],
            hide_index=True,
        )
    else:
        st.write("강화 우선순위 데이터가 없습니다.")
    
    st.markdown("---")

    # 5. 커리큘럼 외 주요 토픽 Top 3
    st.markdown("### 🧭 커리큘럼 외 주요 토픽 Top 3")

    extra_topics = ai_insights.get("extra_topics_detail", [])
    if extra_topics:
        top_extra = extra_topics[:3]
        for t in top_extra:
            with st.container(border=True):
                st.markdown(f"#### {t['topic_label']} ({t['question_count']}건)")
                if t.get("example_questions"):
                    st.markdown(f"- 대표 질문: {t['example_questions'][0]}")
                if t.get("suggested_session_idea"):
                    st.markdown(f"- 제안: {t['suggested_session_idea']}")
                st.markdown("")
    else:
        st.write("커리큘럼 외 주요 토픽 데이터가 없습니다.")

    st.markdown("---")

    # 6. 카테고리별 주요 어려움 패턴
    st.markdown("### 🧠 카테고리별 주요 어려움 패턴")

    if category_pattern_summary:
        for row in category_pattern_summary:
            with st.container(border=True):
                st.markdown(f"#### {row['category']}")
                st.markdown(f"- 주요 패턴: {row['patterns']}")
                # st.markdown(f"- 요약: {row['summary']}")
                st.markdown("")
    else:
        st.write("카테고리별 패턴 요약 데이터가 없습니다.")

    st.markdown("---")

    # 7. 상세 데이터 (expander)
    with st.expander("📎 상세 데이터 더 보기"):
        # 7-1. 카테고리별 질문 수 차트
        st.markdown("#### 📊 카테고리별 질문 수")

        if not df_categories.empty:
            chart_cat = (
                alt.Chart(df_categories)
                .mark_bar()
                .encode(
                    x=alt.X("question_count:Q", title="질문 수"),
                    y=alt.Y("category:N", sort="-x", title="질문 분류"),
                    tooltip=["category", "question_count"],
                )
                .properties(height=260)
            )
            st.altair_chart(chart_cat, use_container_width=True)
        else:
            st.write("질문 데이터가 없습니다.")

        st.markdown("---")

        # 7-2. 분류별 질문 리스트 (pattern + intent 포함)
        st.markdown("#### 📋 분류별 질문 리스트")

        if not df_categories.empty and not df_questions.empty:
            selected_cat = st.selectbox(
                "분류 선택",
                df_categories["category"].tolist(),
                key="category_select_detail",
            )

            df_q_cat = df_questions[df_questions["category"] == selected_cat]

            for _, row in df_q_cat.iterrows():
                st.markdown(f"**{row['question_text']}**")
                st.markdown(
                    f"  - intent: {row['intent']}  \n"
                    f"  - tags: {', '.join(row['pattern_tags'])}"
                )
        else:
            st.write("표시할 질문이 없습니다.")

        st.markdown("---")

        # 7-3. 커리큘럼 내/외 비율 파이
        st.markdown("#### 📉 커리큘럼 내/외 질문 비율")

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
                .encode(
                    theta="count:Q",
                    color="type:N",
                    tooltip=["type", "count"],
                )
                .properties(height=260)
            )
            st.altair_chart(pie, use_container_width=True)
        else:
            st.write("커리큘럼 내/외 데이터가 없습니다.")

        st.markdown("#### 커리큘럼 외 질문 전체 리스트")

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

    with st.container():
        with st.expander("🔎 AI 분석 기준 보기", expanded=False):
            render_curriculum_analysis_rules()

    st.markdown("---")

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

    st.markdown("---")

    st.markdown("## 📄 AI 인사이트 상세 보고서")

    # 1) 이번 주 가장 어려워한 파트
    st.markdown("### 1. 이번 주 가장 어려워한 파트")

    hardest_parts = ai_insights.get("hardest_parts_detail", [])
    if hardest_parts:
        for block in hardest_parts:
            st.markdown(f"#### • {block['part_label']}")
            if block.get("main_categories"):
                st.markdown("- 주요 분류: " + ", ".join(block["main_categories"]))
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
