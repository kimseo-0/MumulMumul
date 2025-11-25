import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(layout="wide")
st.title("📚 커리큘럼 난이도 & 추가 학습 요구 분석")

# --------------------------------
# 커리큘럼 기반 더미 질문 데이터 생성
# --------------------------------
curriculum_map = {
    "Week 1": "Python 기본기",
    "Week 2": "NumPy / Pandas 기초",
    "Week 3": "데이터 처리 & EDA",
    "Week 4": "NLP & 통계 분석",
    "Week 5": "데이터 수집 (API/크롤링)",
    "Week 6": "종합 프로젝트",
}

questions = [
    # Week 1 - Python 기본기
    {"주차": "Week 1", "반": "1반", "유형": "커리큘럼 내", "분류": "기초 문법", "질문": "변수 스코프가 잘 이해되지 않음"},
    {"주차": "Week 1", "반": "2반", "유형": "커리큘럼 내", "분류": "제어문", "질문": "while과 for 사용 구분이 헷갈림"},
    {"주차": "Week 1", "반": "전체", "유형": "커리큘럼 외", "분류": "학습 방법", "질문": "문법을 빠르게 암기하는 방법이 궁금함"},

    # Week 2 - NumPy / Pandas
    {"주차": "Week 2", "반": "1반", "유형": "커리큘럼 내", "분류": "Numpy 배열", "질문": "shape 개념이 익숙하지 않음"},
    {"주차": "Week 2", "반": "2반", "유형": "커리큘럼 내", "분류": "Pandas 전처리", "질문": "groupby 사용법이 헷갈림"},
    {"주차": "Week 2", "반": "전체", "유형": "커리큘럼 외", "분류": "포트폴리오", "질문": "EDA 결과를 포트폴리오에 어떻게 적나요?"},

    # Week 3 - EDA & 시각화
    {"주차": "Week 3", "반": "1반", "유형": "커리큘럼 내", "분류": "시각화", "질문": "subplot 이용 방법이 어려움"},
    {"주차": "Week 3", "반": "2반", "유형": "커리큘럼 내", "분류": "EDA", "질문": "범주형 분석 기준을 잘 모르겠음"},
    {"주차": "Week 3", "반": "전체", "유형": "커리큘럼 외", "분류": "커리어", "질문": "데이터 분석 직무는 EDA를 얼마나 보나요?"},

    # Week 4 - NLP & 통계
    {"주차": "Week 4", "반": "1반", "유형": "커리큘럼 내", "분류": "감성 분석", "질문": "전처리 순서가 헷갈림"},
    {"주차": "Week 4", "반": "2반", "유형": "커리큘럼 내", "분류": "토픽 모델링", "질문": "LDA 파라미터 의미를 모르겠음"},
    {"주차": "Week 4", "반": "전체", "유형": "커리큘럼 외", "분류": "협업", "질문": "팀 분석 프로젝트에서 역할 분담은 어떻게 하나요?"},

    # Week 5 - 데이터 수집
    {"주차": "Week 5", "반": "1반", "유형": "커리큘럼 내", "분류": "API 요청", "질문": "API key 인증 오류 해결 방법이 궁금함"},
    {"주차": "Week 5", "반": "2반", "유형": "커리큘럼 내", "분류": "크롤링", "질문": "Selenium Xpath가 자꾸 바뀜"},
    {"주차": "Week 5", "반": "전체", "유형": "커리큘럼 외", "분류": "IDE 설정", "질문": "크롤링 시 디버깅 환경 설정이 어려움"},

    # Week 6 - 종합 프로젝트
    {"주차": "Week 6", "반": "1반", "유형": "커리큘럼 내", "분류": "모델링", "질문": "accuracy 외 어떤 지표를 봐야 하나요?"},
    {"주차": "Week 6", "반": "2반", "유형": "커리큘럼 내", "분류": "데이터 통합", "질문": "API와 CSV 데이터를 합치는 방법의 기준이 궁금함"},
    {"주차": "Week 6", "반": "전체", "유형": "커리큘럼 외", "분류": "면접", "질문": "프로젝트를 면접에서 어떻게 설명해야 하나요?"},
]

df = pd.DataFrame(questions)

# --------------------------------
# 사이드바
# --------------------------------
st.sidebar.header("필터 설정")

classes = ["전체", "1반", "2반", "3반", "4반"]
selected_class = st.sidebar.selectbox("반 선택", classes)

weeks = list(curriculum_map.keys())
selected_week = st.sidebar.selectbox("주차 선택", weeks)

week_title = curriculum_map[selected_week]

# 필터
df_filtered = df[df["주차"] == selected_week]
if selected_class != "전체":
    df_filtered = df_filtered[(df_filtered["반"] == selected_class) | (df_filtered["반"] == "전체")]

# --------------------------------
# 집계
# --------------------------------
total_q = len(df_filtered)
inner_q = len(df_filtered[df_filtered["유형"] == "커리큘럼 내"])
outer_q = len(df_filtered[df_filtered["유형"] == "커리큘럼 외"])
outer_ratio = round((outer_q / total_q * 100), 1) if total_q > 0 else 0

category_counts = (
    df_filtered.groupby("분류")
    .size()
    .reset_index(name="질문 수")
    .sort_values("질문 수", ascending=False)
)

outer_df = df_filtered[df_filtered["유형"] == "커리큘럼 외"]

# --------------------------------
# 탭 구성
# --------------------------------
tab_summary, tab_ai = st.tabs(["요약", "AI 심층 분석"])

# -----------------------------------
# (1) 요약 탭
# -----------------------------------
with tab_summary:
    st.subheader(f"📌 {selected_week} — {week_title} 요약")

    c1, c2, c3 = st.columns(3)
    c1.metric("전체 질문 수", f"{total_q}건")
    c2.metric("커리큘럼 외 비율", f"{outer_ratio}%")
    c3.metric("질문 분류 수", f"{len(category_counts)}개")

    st.markdown("### 🔥 이번 주 상위 질문 분류")

    # 상위 3개만 추출
    top3 = category_counts.head(3)

    colA, colB, colC = st.columns(3)

    columns = [colA, colB, colC]

    for col, (_, row) in zip(columns, top3.iterrows()):
        with col:
            st.info(
                f"""
    ### {row['분류']}
    **{int(row['질문 수'])}건**
    """
            )


    st.markdown("---")
    st.markdown("### 📊 질문 분류별 질문 수")

    chart = (
        alt.Chart(category_counts)
        .mark_bar()
        .encode(
            x="질문 수:Q",
            y=alt.Y("분류:N", sort="-x"),
            color="분류:N",
        )
        .properties(height=250)
    )
    st.altair_chart(chart, use_container_width=True)

    st.markdown("#### 📋 분류별 질문 리스트")
    selected_cat = st.selectbox("분류 선택", category_counts["분류"].tolist())
    for q in df_filtered[df_filtered["분류"] == selected_cat]["질문"]:
        st.markdown(f"- {q}")

    st.markdown("---")
    st.markdown("### 🥤 커리큘럼 외 질문 비율")

    pie = (
        alt.Chart(df_filtered.groupby("유형").size().reset_index(name="건수"))
        .mark_arc(innerRadius=40)
        .encode(theta="건수:Q", color="유형:N")
        .properties(height=260)
    )
    st.altair_chart(pie, use_container_width=True)

    st.markdown("#### 커리큘럼 외 질문 리스트")
    for q in outer_df["질문"]:
        st.markdown(f"- {q}")


# -----------------------------------
# (2) AI 심층 분석 탭
# -----------------------------------
with tab_ai:
    st.subheader(f"🤖 AI 심층 분석 — {selected_week}")

    # -------------------------
    # 상단 3개 요약 정보
    # -------------------------
    colA, colB, colC = st.columns(3)

    # 1. 가장 어려운 파트
    hardest_part = df_filtered["분류"].value_counts().idxmax()
    colA.info(
        f"### 가장 어려워한 파트\n"
        f"- **{hardest_part}** 관련 질문이 가장 많았음\n"
        f"- {week_title} 중 핵심 난이도 구간으로 추정됨"
    )

    # 2. 커리큘럼 외 질문
    if outer_q > 0:
        top_outer = outer_df["분류"].value_counts().idxmax()
        colB.warning(
            f"### 커리큘럼 외 질문\n"
            f"- 비중 **{outer_ratio}%**\n"
            f"- 가장 많은 주제: **{top_outer}**"
        )
    else:
        colB.warning("### 커리큘럼 외 질문\n- 이번 주는 거의 없음")

    # 3. 개선 방향
    colC.success(
        "### 개선 방향 제안\n"
        "- 난이도 높은 파트 별도 실습 제공\n"
        "- 커리큘럼 외 자주 등장하는 주제는 미니 세션 권장\n"
        "- 질문이 반복되는 항목은 FAQ로 정리"
    )

    st.markdown("---")

    # -------------------------
    # AI 상세 인사이트 보고서
    # -------------------------
    st.markdown("## 📄 AI 인사이트 상세 보고서")

    # 1) 어려운 파트
    st.markdown("### 1. 이번 주 가장 어려워한 파트")

    for _, row in category_counts.head().iterrows():
        part = row["분류"]
        st.markdown(f"#### • {part}")
        sample = df_filtered[df_filtered["분류"] == part]["질문"].tolist()
        for q in sample:
            st.markdown(f"- {q}")

    st.markdown("---")

    # 2) 커리큘럼 외 질문
    st.markdown("### 2. 커리큘럼 외 질문 분석")
    if outer_q > 0:
        for cat in outer_df["분류"].unique():
            st.markdown(f"#### • {cat}")
            for q in outer_df[outer_df["분류"] == cat]["질문"]:
                st.markdown(f"- {q}")
    else:
        st.write("이번 주에는 커리큘럼 외 질문이 거의 없음.")

    st.markdown("---")

    # 3) 운영진 액션
    st.markdown("### 3. 운영진 액션 정리")

    st.markdown("""
#### 3-1. 난이도 구간 개선
- 이번 주 학생들이 어려워한 부분을 집중적으로 보충
- 실습 기반 설명 강화 (예: 오류를 일부러 발생시켜보고 처리하는 방식)

#### 3-2. 추가 강의 자료 방향성
- 핵심 파트별 미니 요약/핵심 개념 PDF 제공
- ‘가장 많이 하는 실수 TOP5’ 유형 자료 제공

#### 3-3. 커리큘럼 외 세션 제안
- 포트폴리오/커리어: 1시간 Q&A
- IDE/환경 설정: 실습형 워크숍 진행 가능
""")
