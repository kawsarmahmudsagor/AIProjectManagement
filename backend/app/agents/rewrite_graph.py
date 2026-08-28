"""LangGraph orchestration for the `/ai/rewrite` flow.

This is deliberately a one-node graph today — `call_provider` just awaits the same
`LLMProvider.rewrite()` the service called directly before. It exists so the rewrite path
already runs through LangGraph's StateGraph/compiled-graph machinery, which is the seam a
future chatbot feature (multi-turn state, tool-calling nodes, routing) will extend rather
than replace. `ai_service.rewrite_field()` calls `run_rewrite()` instead of
`provider.rewrite()` directly; nothing else about the retry loop or provider layer changes.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.models.user import AgentPersona
from app.providers.base import LLMProvider


class RewriteState(TypedDict):
    provider: LLMProvider
    persona: AgentPersona
    op: str
    target_text: str
    source_text: str | None
    char_limit: int | None
    context: dict | None
    instruction: str | None
    result: str


async def _call_provider(state: RewriteState) -> dict:
    result = await state["provider"].rewrite(
        op=state["op"],
        target_text=state["target_text"],
        source_text=state["source_text"],
        char_limit=state["char_limit"],
        context=state["context"],
        instruction=state["instruction"],
        persona=state["persona"],
    )
    return {"result": result}


_graph = StateGraph(RewriteState)
_graph.add_node("call_provider", _call_provider)
_graph.add_edge(START, "call_provider")
_graph.add_edge("call_provider", END)
rewrite_graph = _graph.compile()


async def run_rewrite(
    provider: LLMProvider,
    persona: AgentPersona,
    *,
    op: str,
    target_text: str,
    source_text: str | None,
    char_limit: int | None,
    context: dict | None = None,
    instruction: str | None = None,
) -> str:
    initial_state: RewriteState = {
        "provider": provider,
        "persona": persona,
        "op": op,
        "target_text": target_text,
        "source_text": source_text,
        "char_limit": char_limit,
        "context": context,
        "instruction": instruction,
        "result": "",
    }
    state = await rewrite_graph.ainvoke(initial_state)
    return state["result"]
