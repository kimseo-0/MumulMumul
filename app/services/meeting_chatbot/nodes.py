from langchain_core.prompts import ChatPromptTemplate
from app.core.logger import setup_logger
from app.core.db import SessionLocal
from app.core.schemas import Meeting


logger = setup_logger(__name__)


# -----------------------------------------------------------
# 1) 질문 분석
# -----------------------------------------------------------
async def analyze_query(state):
    query = state["query"]
    logger.info(f"[Node] analyze_query: {query}")

    state["search_performed"] = False
    state["needs_more_info"] = False
    return state


# -----------------------------------------------------------
# 2) Chroma 검색
# -----------------------------------------------------------
async def search_segments(state, vector_store):
    query = state["query"]
    meeting_id = state.get("meeting_id")
    group_id = state.get("group_id")

    logger.info(f"[Node] search_segments: query={query}, meeting_id={meeting_id}")

    try:
        # 우선순위 : meeting_id > group_id > 전체 검색
        if meeting_id:
            logger.info(f"특정 회의 검색: {meeting_id}")
            results = vector_store.search_segments(meeting_id, query, k=5)
        elif group_id:
            logger.info(f"그룹 회의 검색: {group_id}")
            results = vector_store.search_by_group_id(group_id, query, k=5)
        else:
            logger.info("전체 회의 검색")
            results = vector_store.search_summaries(query, k=3)

        relevant = []
        for doc in results:
            relevant.append({
                "content": doc.page_content,
                "metadata": doc.metadata
            })

        state["relevant_segments"] = relevant
        state["search_performed"] = True

        logger.info(f"검색 결과 {len(state['relevant_segments'])}개")

    except Exception as e:
        logger.error(f"검색 실패: {e}", exc_info=True)
        state["relevant_segments"] = []

    return state


# -----------------------------------------------------------
# 3) MongoDB 컨텍스트 조회
# -----------------------------------------------------------
async def retrieve_context(state, mongo_service, **kwargs):
    segments = state.get("relevant_segments", [])
    group_id = state.get("group_id")

    if not segments:
        state["meeting_context"] = {}
        return state
    
    # group_id가 있으면 여러 회의 컨텍스트 조회
    if group_id:
        logger.info("MongoDB 그룹 조회: {group_id}")
        try:
            db = SessionLocal()
            meetings = db.query(Meeting).filter(
                Meeting.chat_room_id == group_id
            ).all()
            db.close()

            if not meetings:
                state["meeting_context"] = {}
                return state
            
            context = {
                "group_id": group_id,
                "meeting_count": len(meetings),
                "meetings": []
            }

            for meeting in meetings:
                summary = mongo_service.get_summary(meeting.meeting_id)
                if summary:
                    context["meetings"].append({
                        "meeting_id": meeting.meeting_id,
                        "title": meeting.title,
                        "summary": summary.summary_text,
                        "key_points": summary.key_points,
                        "action_items": summary.action_items
                    })
            
            state["meeting_context"] = context
            logger.info(f"그룹 컨텍스트 조회 완료: {len(context['meetings'])}개 회의")

        except Exception as e:
            logger.error(f"그룹 컨텍스트 조회 실패: {e}")
            state["meeting_context"] = {}

        return state

    top = segments[0]
    meeting_id = top["metadata"].get("meeting_id")

    if not meeting_id:
        state["meeting_context"] = {}
        return state

    logger.info(f"MongoDB 조회: {meeting_id}")

    try:
        transcript = mongo_service.get_transcript(meeting_id)
        summary = mongo_service.get_summary(meeting_id)

        context = {}
        if transcript:
            context["title"] = transcript.title
            context["duration_ms"] = transcript.duration_ms
            context["speakers"] = transcript.speakers
            context["full_text"] = transcript.full_text[:2000]

        if summary:
            context["summary"] = summary.summary_text
            context["key_points"] = summary.key_points
            context["action_items"] = summary.action_items

        state["meeting_context"] = context
        logger.info("컨텍스트 조회 완료")

    except Exception as e:
        logger.error(f"MongoDB 조회 실패: {e}")
        state["meeting_context"] = {}

    return state


# -----------------------------------------------------------
# 4) 답변 생성
# -----------------------------------------------------------
async def generate_answer(state, llm, **kwargs):
    query = state["query"]
    segments = state.get("relevant_segments", [])
    context = state.get("meeting_context", {})
    group_id = state.get("group_id")

    logger.info("답변 생성 시작")

    # 검색 결과 없음
    if not segments:
        state["answer"] = "죄송합니다. 관련된 회의 정보를 찾지 못했습니다."
        state["confidence"] = 0.0
        state["sources"] = []
        return state

    segments_text = "\n\n".join([
        f"[{i+1}] {seg['content']}"
        for i, seg in enumerate(segments[:5])
    ])

    context_text = ""
    if group_id and "meetings" in context:
        context_text += f"\n\n이 그룹({group_id})의 {context['meeting_count']}개 회의에서 검색했습니다:\n"
        for i, meeting in enumerate(context["meetings"][:3], 1):
            context_text += f"\n{i}. {meeting['title']}\n"
            context_text += f"   요약: {meeting['summary'][:200]}...\n"

    elif "summary" in context:
        context_text += f"\n\n요약:\n{context['summary']}"
        if "key_points" in context:
            context_text += "\n\n핵심 포인트:\n" + "\n".join(
                f"- {k}" for k in context["key_points"][:3]
            )

    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 회의 요약 기반 어시스턴트입니다.
        제공된 회의 내용만을 근거로 답하세요.
        불확실하면 '확실하지 않습니다'라고 말하세요."""),
                
                ("human", """질문: {query}

        관련 회의 내용:
        {segments_text}

        {context_text}

        위 정보를 기반으로 답변해주세요.""")
    ])

    chain = prompt | llm

    try:
        response = await chain.ainvoke({
            "query": query,
            "segments_text": segments_text,
            "context_text": context_text
        })

        answer = response.content

        sources = []

        if group_id:
            sources.append(f"그룹 {group_id}의 {context.get('meeting_count', 0)}개 회의")

        for seg in segments[:5]:
            meta = seg["metadata"]
            if "meeting_id" in meta:
                sources.append(f"회의 {meta['meeting_id']}")

        state["answer"] = answer
        state["confidence"] = 0.8 if len(segments) >= 3 else 0.5
        state["sources"] = list(set(sources))

        logger.info("답변 생성 완료")

    except Exception as e:
        logger.error(f"답변 생성 실패: {e}", exc_info=True)
        state["answer"] = "답변 생성 중 오류가 발생했습니다."
        state["confidence"] = 0.0
        state["sources"] = []

    return state
