import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta

st.set_page_config(
    layout="wide",
)

# -----------------------------
# 공통: 사이드바 (반 선택 / 기간 / 현재 주차)
# -----------------------------
st.sidebar.header("캠프 설정")

today = date.today()

class_options = ["전체", "1반", "2반", "3반", "4반"]
selected_class = st.sidebar.selectbox("반 선택", class_options, index=0)

start_date = st.sidebar.date_input("반 시작일", value=today - timedelta(weeks=3))
end_date = st.sidebar.date_input("반 종료일", value=today + timedelta(weeks=4))

if start_date > end_date:
    st.sidebar.error("반 시작일이 종료일 이후입니다. 날짜를 다시 선택해주세요.")

# 현재 주차 계산
if today < start_date:
    week_label = "개강 전"
elif today > end_date:
    week_label = "수료 이후"
else:
    delta_days = (today - start_date).days
    week_num = delta_days // 7 + 1
    week_label = f"{week_num}주차"

st.sidebar.markdown(f"**현재 주차:** {week_label}")

# 반별 스케일 팩터 (더미용)
class_factor_map = {
    "전체": 1.0,
    "1반": 1.05,   # 1반: 조금 더 활발
    "2반": 0.9,    # 2반: 조금 조용
    "3반": 1.0,
    "4반": 0.95,
}
factor = class_factor_map.get(selected_class, 1.0)

# -----------------------------
# 페이지 타이틀
# -----------------------------
if selected_class == "전체":
    title_suffix = "전체 반 기준"
else:
    title_suffix = f"{selected_class} 기준"

st.title(f"💬 속마음 모닥불 리포트 ({title_suffix})")

# -----------------------------
# [베이스] 가짜 데이터 생성 (전체 기준)
# -----------------------------

# 키워드/빈도 (워드클라우드용)
keyword_data_base = pd.DataFrame(
    {
        "키워드": ["git_conflict", "일정압박", "반 분위기", "리더상담", "번아웃", "불안"],
        "빈도": [19, 14, 11, 7, 5, 4],
    }
)

# 카테고리별 고민/건의 수
worry_categories_base = pd.DataFrame(
    {
        "분류": ["학습 난이도", "팀 관계", "시간 압박", "진로/미래"],
        "게시글 수": [18, 12, 9, 5],
    }
)

suggest_categories_base = pd.DataFrame(
    {
        "분류": ["수업 방식", "과제 난이도", "커뮤니티 운영", "진로/취업 지원"],
        "게시글 수": [7, 6, 4, 3],
    }
)

# 분류별 중요 글 예시 (최대 3개씩) - 텍스트는 반에 상관없이 공통 사용
worry_examples = {
    "학습 난이도": [
        "이번 주 내용이 너무 빠르게 지나가서 복습할 시간이 부족해요.",
        "기본 개념을 더 천천히 다뤄주면 좋겠습니다.",
        "당장 따라가기는 하는데, 완전히 이해하지 못한 느낌이에요.",
    ],
    "팀 관계": [
        "팀원들에게 질문하기가 눈치 보일 때가 있어요.",
        "의견을 내도 묵살되는 느낌이라 위축됩니다.",
    ],
    "시간 압박": [
        "과제, 복습, 기록까지 하다 보니 하루가 너무 부족합니다.",
        "주중에 일을 병행하는 사람들에게는 일정이 빡빡한 것 같아요.",
    ],
    "진로/미래": [
        "이 과정을 수료한 뒤에 실제로 어떤 일을 할 수 있을지 걱정됩니다.",
    ],
}

suggest_examples = {
    "수업 방식": [
        "실습 위주 수업 시간이 조금 더 길었으면 좋겠습니다.",
        "실제 코드 리뷰 과정을 한 번 보여주시면 도움이 될 것 같아요.",
    ],
    "과제 난이도": [
        "이번 주 과제가 지난 주보다 난이도가 급격히 올라간 것 같습니다.",
        "필수/선택 과제로 나누어 주시면 부담이 줄 것 같아요.",
    ],
    "커뮤니티 운영": [
        "반별로 잡담/소통 채널이 있으면 좋겠습니다.",
        "익명 게시판에 너무 무거운 글이 많아 가볍게 쓸 공간도 필요해요.",
    ],
    "진로/취업 지원": [
        "포트폴리오를 어떻게 준비해야 할지 안내 세션이 있으면 좋겠습니다.",
    ],
}

# 일별 글 수 추이 (이번 주, 전체 기준)
days = [today - timedelta(days=i) for i in range(6, -1, -1)]
posts_per_day_base = [8, 9, 10, 11, 12, 10, 14]
df_daily_posts_base = pd.DataFrame({"날짜": days, "게시글 수": posts_per_day_base})

# -----------------------------
# [반 기준] 뷰용 데이터 생성 (factor 적용)
# -----------------------------
# 숫자형 값들을 factor로 살짝 조정해서 반별 차이가 있는 것처럼 보이게

# 요약 지표용 숫자
base_total_posts = 86
base_worry_posts = 54
base_negative_posts = 27

total_posts = int(round(base_total_posts * factor))
worry_posts = int(round(base_worry_posts * factor))
negative_posts = int(round(base_negative_posts * factor))

# 데이터프레임들 복사 후 스케일 적용
keyword_data = keyword_data_base.copy()
keyword_data["빈도"] = (keyword_data["빈도"] * factor).round().astype(int).clip(lower=1)

worry_categories = worry_categories_base.copy()
worry_categories["게시글 수"] = (
    worry_categories["게시글 수"] * factor
).round().astype(int).clip(lower=1)

suggest_categories = suggest_categories_base.copy()
suggest_categories["게시글 수"] = (
    suggest_categories["게시글 수"] * factor
).round().astype(int).clip(lower=1)

df_daily_posts = df_daily_posts_base.copy()
df_daily_posts["게시글 수"] = (
    df_daily_posts["게시글 수"] * factor
).round().astype(int).clip(lower=1)

# -----------------------------
# 탭 구성
# -----------------------------
tab_summary, tab_ai = st.tabs(["요약", "AI 심층 분석"])

# -----------------------------
# (1) 요약 탭
# -----------------------------
with tab_summary:
    if selected_class == "전체":
        st.subheader(f"{week_label} 요약 - 전체 기준")
    else:
        st.subheader(f"{week_label} 요약 - {selected_class} 기준")

    st.markdown("#### 이번 주 통계")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("익명 게시글 수", f"{total_posts}건", "▲ 12건")
    with col2:
        st.metric("고민 글 수", f"{worry_posts}건", "▲ 9건")
    with col3:
        st.metric("부정 감정 글 수", f"{negative_posts}건", "▲ 6건")

    st.markdown("#### 키워드 하이라이트")
    if selected_class == "전체":
        st.caption("이번 주 전체 익명 게시판에서 자주 등장한 키워드입니다.")
    else:
        st.caption(f"이번 주 {selected_class} 익명 게시판에서 자주 등장한 키워드입니다.")

    keyword_chart = (
        alt.Chart(keyword_data)
        .mark_bar()
        .encode(
            x=alt.X("빈도:Q", title="언급 빈도"),
            y=alt.Y("키워드:N", sort="-x", title="키워드"),
            color=alt.Color("키워드:N", legend=None),
            tooltip=["키워드", "빈도"],
        )
        .properties(height=260)
    )
    st.altair_chart(keyword_chart, width='stretch')

    st.markdown("---")
    st.markdown("### 지표 한눈에 보기")

    st.markdown("#### 글 수 추이")

    st.markdown(
        """
- 이번 주 동안 익명 게시글이 얼마나 꾸준히 올라왔는지 확인할 수 있습니다.  
- 특정 날짜에 글이 급증했다면, 그날 진행된 수업/공지/이벤트와 함께 보는 것이 좋습니다.
"""
    )

    trend_chart = (
        alt.Chart(df_daily_posts)
        .mark_line(point=True)
        .encode(
            x=alt.X("날짜:T", title="날짜"),
            y=alt.Y("게시글 수:Q", title="게시글 수"),
            tooltip=["날짜", "게시글 수"],
        )
        .properties(height=260)
    )
    st.altair_chart(trend_chart, width='stretch')

    top_left, top_right = st.columns(2)

    with top_left:
        st.markdown("#### 고민글 분류별 통계")

        worry_chart = (
            alt.Chart(worry_categories)
            .mark_bar()
            .encode(
                x=alt.X("게시글 수:Q", title="게시글 수"),
                y=alt.Y("분류:N", sort="-x", title="분류"),
                color=alt.Color("분류:N", legend=None),
                tooltip=["분류", "게시글 수"],
            )
            .properties(height=260)
        )
        st.altair_chart(worry_chart, width='stretch')

        selected_worry = st.selectbox(
            "자세히 보고 싶은 고민글 분류 선택",
            worry_categories["분류"].tolist(),
        )

        examples = worry_examples.get(selected_worry, [])
        if examples:
            st.markdown(f"**[{selected_worry}] 관련 주요 고민글 (최대 3개)**")
            for i, txt in enumerate(examples[:3], start=1):
                st.markdown(f"- {txt}")
        else:
            st.markdown("표시할 고민글이 없습니다.")

    with top_right:
        st.markdown("#### 건의글 분류별 통계")

        suggest_chart = (
            alt.Chart(suggest_categories)
            .mark_bar()
            .encode(
                x=alt.X("게시글 수:Q", title="게시글 수"),
                y=alt.Y("분류:N", sort="-x", title="분류"),
                color=alt.Color("분류:N", legend=None),
                tooltip=["분류", "게시글 수"],
            )
            .properties(height=260)
        )
        st.altair_chart(suggest_chart, width='stretch')

        selected_suggest = st.selectbox(
            "자세히 보고 싶은 건의글 분류 선택",
            suggest_categories["분류"].tolist(),
        )

        examples_s = suggest_examples.get(selected_suggest, [])
        if examples_s:
            st.markdown(f"**[{selected_suggest}] 관련 주요 건의글 (최대 3개)**")
            for i, txt in enumerate(examples_s[:3], start=1):
                st.markdown(f"- {txt}")
        else:
            st.markdown("표시할 건의글이 없습니다.")

# -----------------------------
# (2) AI 심층 분석 탭
# -----------------------------
# -----------------------------
# (2) AI 심층 분석 탭
# -----------------------------
with tab_ai:
    if selected_class == "전체":
        st.subheader("AI 인사이트 리포트 - 전체 기준")
        대상_문구 = "전체 익명 게시판에서는"
    else:
        st.subheader(f"AI 인사이트 리포트 - {selected_class} 기준")
        대상_문구 = f"{selected_class} 익명 게시판에서는"

    # 상단 요약 카드 (핵심 키워드 / 분위기 / 우선 액션)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(
            "**핵심 키워드 요약**\n\n"
            "- Git 협업 이슈 다수 발생함\n"
            "- 일정·시간 관련 언급 증가함\n"
            "- 반 분위기·소통 어려움 드러남"
        )
    with col2:
        st.warning(
            "**분위기 진단 요약**\n\n"
            "- 고민 글 비중이 높아지는 추세임\n"
            "- 부정 감정 비율도 함께 상승 중임\n"
            "- 일부 반에서 심리적 안전감 낮을 가능성 있음"
        )
    with col3:
        st.success(
            "**운영 우선 과제 요약**\n\n"
            "- Git 문제 해결 지원 강화 필요함\n"
            "- 일정 압박 완화 메시지 전달이 필요함\n"
            "- 반 단위 체크인 미팅이 권장됨"
        )

    st.markdown("---")

    # 1. 주요 이슈 현황
    st.markdown("### 1. 주요 이슈 현황")

    col_a, col_b = st.columns([1.2, 1.5])

    with col_a:
        # 상위 3개 키워드 텍스트 요약
        top_keywords = (
            keyword_data.sort_values("빈도", ascending=False)
            .head(3)
            .reset_index(drop=True)
        )

        st.markdown("#### 1-1. 상위 키워드 요약")
        st.markdown(
            f"""
- {대상_문구} 아래 이슈가 가장 많이 언급됨  
- 상위 키워드 Top3 기준 요약임
"""
        )

        for idx, row in top_keywords.iterrows():
            rank = idx + 1
            st.markdown(f"- **{rank}위:** `{row['키워드']}` · {row['빈도']}회 언급됨")

        st.caption("※ 실제 서비스에서는 기간/반 선택에 따라 상위 키워드가 자동으로 갱신됨.")

    with col_b:
        st.markdown("#### 1-2. 키워드 빈도 분포")

        keyword_chart_ai = (
            alt.Chart(keyword_data)
            .mark_bar()
            .encode(
                x=alt.X("빈도:Q", title="언급 빈도"),
                y=alt.Y("키워드:N", sort="-x", title="키워드"),
                color=alt.Color("키워드:N", legend=None),
                tooltip=["키워드", "빈도"],
            )
            .properties(height=260)
        )
        st.altair_chart(keyword_chart_ai, width='stretch')
        st.caption("이번 주 기준 키워드별 언급 빈도 분포임.")

    st.markdown("---")

    # 2. 고민 글 분석
    st.markdown("### 2. 고민 글 분석")

    col_c, col_d = st.columns([1.4, 1.3])

    with col_c:
        st.markdown("#### 2-1. 고민 글 패턴 요약")

        top_worry = (
            worry_categories.sort_values("게시글 수", ascending=False)
            .reset_index(drop=True)
        )
        top_cat = top_worry.loc[0, "분류"]
        top_val = top_worry.loc[0, "게시글 수"]

        st.markdown(
            f"""
- 고민 글은 **`{top_cat}`** 관련 비중이 가장 높음  
- 해당 분류 게시글 수는 **{top_val}건** 수준임  
- 전체적으로는 **학습 난이도·진도, 팀 관계, 시간 압박** 순으로 이슈가 분포하는 양상임
"""
        )

        st.markdown("##### 운영 관점 주요 해석")
        st.markdown(
            """
- 학습 난이도와 속도를 동시에 부담으로 느끼는 학습자가 적지 않은 것으로 보임  
- 팀 내 소통 어려움이 함께 언급되어, 단순 학습 문제가 아닌 **관계·분위기 문제**도 일부 결합되어 있음  
- 과제·복습·기록을 병행하는 과정에서, **체력·시간 부족감**이 누적되고 있음
"""
        )

    with col_d:
        st.markdown("#### 2-2. 고민 글 분류별 분포")

        worry_chart_ai = (
            alt.Chart(worry_categories)
            .mark_bar()
            .encode(
                x=alt.X("게시글 수:Q", title="게시글 수"),
                y=alt.Y("분류:N", sort="-x", title="분류"),
                color=alt.Color("분류:N", legend=None),
                tooltip=["분류", "게시글 수"],
            )
            .properties(height=260)
        )
        st.altair_chart(worry_chart_ai, width='stretch')
        st.caption("분류별 고민 글 분포를 통해 어떤 영역에서 부담이 큰지 확인 가능함.")

    with st.expander("2-3. 고민 글 예시 문장"):
        st.markdown(
            """
- “이번 주 내용이 너무 빠르게 지나가서 복습할 시간이 부족함.”
- “팀원들에게 질문하기가 눈치 보일 때가 있음.”
- “과제, 복습, 기록까지 하다 보니 하루가 너무 부족하다고 느껴짐.”
"""
        )

    st.markdown("---")

    # 3. 건의 글 분석
    st.markdown("### 3. 건의 글 분석")

    col_e, col_f = st.columns([1.4, 1.3])

    with col_e:
        st.markdown("#### 3-1. 건의 글 패턴 요약")

        top_suggest = (
            suggest_categories.sort_values("게시글 수", ascending=False)
            .reset_index(drop=True)
        )
        s_cat = top_suggest.loc[0, "분류"]
        s_val = top_suggest.loc[0, "게시글 수"]

        st.markdown(
            f"""
- 건의 글은 **`{s_cat}`** 관련 요구가 가장 높게 나타남  
- 해당 분류 게시글 수는 **{s_val}건** 수준임  
- 수업 방식·과제 설계·커뮤니티 운영·진로 지원 등 **운영 전반에 대한 구체적 제안**이 다수 존재함
"""
        )

        st.markdown("##### 운영 관점 주요 해석")
        st.markdown(
            """
- 수업 방식 측면에서는 실습 비중 확대, 코드 리뷰 데모 등 **실전 중심 개선 요구**가 확인됨  
- 과제 난이도 측면에서는 필수/선택 구분 등 **부담 조절 장치**에 대한 요구가 나타남  
- 커뮤니티·진로 측면에서는 **잡담 채널, 포트폴리오/진로 세션** 등 정서·미래 관련 지원이 필요함
"""
        )

    with col_f:
        st.markdown("#### 3-2. 건의 글 분류별 분포")

        suggest_chart_ai = (
            alt.Chart(suggest_categories)
            .mark_bar()
            .encode(
                x=alt.X("게시글 수:Q", title="게시글 수"),
                y=alt.Y("분류:N", sort="-x", title="분류"),
                color=alt.Color("분류:N", legend=None),
                tooltip=["분류", "게시글 수"],
            )
            .properties(height=260)
        )
        st.altair_chart(suggest_chart_ai, width='stretch')
        st.caption("어떤 영역에서 ‘구체적인 개선 제안’이 많이 나오는지 확인 가능함.")

    with st.expander("3-3. 건의 글 예시 문장"):
        st.markdown(
            """
- “실습 위주 수업 시간이 조금 더 길었으면 좋겠음.”
- “이번 주 과제가 지난 주보다 난이도가 급격히 올라간 것으로 느껴짐.”
- “반별로 잡담/소통 채널이 있으면 좋겠음.”
- “포트폴리오 준비 방법을 다루는 안내 세션이 있으면 좋겠음.”
"""
        )

    st.markdown("---")

    # 4. 운영 액션 제안 정리
    st.markdown("### 4. 운영 액션 제안 요약")

    col_g, col_h = st.columns(2)

    with col_g:
        st.markdown("#### 4-1. 단기(1~2주) 액션 제안")
        st.markdown(
            """
- Git 협업 실습 세션 1회 추가 및 **자주 발생하는 에러·충돌 시나리오 가이드** 배포 필요함  
- 이번/다음 주 과제 난이도를 조정하거나, **필수/선택 과제 구분**을 도입하는 방안 검토가 필요함  
- 잡담/소통 채널 신설 등으로, **가벼운 대화와 정서적 환기**가 가능한 공간을 마련하는 것이 좋음
"""
        )

    with col_h:
        st.markdown("#### 4-2. 중기(3주 이상) 액션 제안")
        st.markdown(
            """
- 포트폴리오/진로 Q&A 세션을 정기적으로 운영하여, **미래에 대한 불안**을 완화할 필요가 있음  
- Git·환경 설정·협업 툴 활용법 등을 **별도 모듈/워크숍**으로 구성하여 반복적으로 활용 가능하게 하는 것이 바람직함  
- 반별 리더/멘토와 함께, **심리적 안전감·소통 구조**를 정기적으로 점검하는 체계를 갖추는 것이 필요함
"""
        )

    st.caption("※ 위 제안은 더미 데이터 기반 예시이며, 실제 서비스에서는 실시간 로그·질문·게시글을 기반으로 자동 생성되는 리포트임.")
