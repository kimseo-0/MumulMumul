from langgraph.graph import StateGraph, END
from .state import ChatbotState
from .nodes import (
    analyze_query,
    search_segments,
    retrieve_context,
    generate_answer
)

def build_graph(llm, vector_store, mongo_service):
    graph = StateGraph(ChatbotState)

    graph.add_node("analyze_query", analyze_query)

    async def search_wrapper(st):
        return await search_segments(st, vector_store)

    async def context_wrapper(st):
        return await retrieve_context(st, mongo_service)

    async def answer_wrapper(st):
        return await generate_answer(st, llm)
    
    graph.add_node("search_segments", search_wrapper)
    graph.add_node("retrieve_context", context_wrapper)
    graph.add_node("generate_answer", answer_wrapper)

    graph.set_entry_point("analyze_query")

    graph.add_edge("analyze_query", "search_segments")
    graph.add_edge("search_segments", "retrieve_context")
    graph.add_edge("retrieve_context", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()
