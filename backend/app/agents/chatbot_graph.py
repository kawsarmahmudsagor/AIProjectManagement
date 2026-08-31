"""LangGraph orchestration for Jarvis, the chatbot. Follows `rewrite_graph.py`'s
conventions (TypedDict state, an `async def run_*()`/`stream_*()` entrypoint services call
instead of touching the graph object directly) with one deliberate deviation: the compiled
graph is built **per chat turn** via `_build_graph(tools)` rather than once at module load,
because two of Jarvis's three tools (`project_search`, `portfolio_analysis`) close over a
request-scoped `db`/`user_id` — see `chat_tools.build_tools`. Compiling a 3-node graph per
call is microseconds; this is not an oversight.

The agent loop is a standard ReAct-style tool-calling loop built from LangGraph's prebuilt
pieces (`ToolNode`, `tools_condition`) rather than a hand-rolled dispatch — "persona
switching" between grounded project Q&A, portfolio analysis, and ungrounded technology
advice is entirely the LLM's own per-turn decision about which tool(s) to call, guided by
the grounding rules in the system prompt (see providers/prompts.build_chatbot_system_prompt).
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated, TypedDict
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from app.models.user import ChatProvider
from app.providers.base import LLMProvider

_ContentType = str | list


def stringify_content(content: _ContentType) -> str:
    """A chat model's (streamed or final) content is str | list[str | dict] — some
    providers emit a list of content blocks (text/thinking/redacted_thinking/tool_use/
    signature_delta/...) instead of a plain string, particularly under extended thinking.
    Only text blocks are ever meant for the user; thinking/tool-delta blocks must be
    dropped here rather than passed through, or they show up as literal "[object
    Object]" garbage once JSON round-trips them to the frontend (dict/list -> JSON array
    -> JS String() on an array of objects)."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)

# Caps agent-node invocations per turn so a model stuck calling tools repeatedly can't
# loop forever. When hit, the agent node returns a plain (tool-call-free) fallback
# message instead of forcing a mid-tool-call stop — that would otherwise leave an
# AIMessage with unresolved tool_calls in history, which most providers reject on replay.
_MAX_AGENT_STEPS = 6


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: UUID
    chat_provider: ChatProvider
    system_prompt: str
    provider: LLMProvider
    agent_steps: int


class ChatGraphEvent(TypedDict, total=False):
    """Internal event shape yielded by `stream_chat` — NOT the wire SSE contract (see
    schemas/chat.ChatSSEEvent for that). services/chat_service.stream_turn translates
    these into SSE frames and, for the final "final" event, persists `messages`."""

    type: str  # "token" | "tool_start" | "tool_end" | "final"
    delta: str
    tool_call_id: str
    name: str
    result: dict
    messages: list[BaseMessage]


def _build_graph(tools: list[BaseTool]):
    async def _call_agent(state: ChatState) -> dict:
        agent_steps = state.get("agent_steps", 0)
        if agent_steps >= _MAX_AGENT_STEPS:
            fallback = AIMessage(
                content="I wasn't able to finish that within a reasonable number of steps — "
                "could you rephrase or narrow the question?"
            )
            return {"messages": [fallback], "agent_steps": agent_steps + 1}

        chat_model = state["provider"].get_chat_model().bind_tools(tools)
        response = await chat_model.ainvoke(
            [SystemMessage(content=state["system_prompt"]), *state["messages"]]
        )
        return {"messages": [response], "agent_steps": agent_steps + 1}

    graph = StateGraph(ChatState)
    graph.add_node("agent", _call_agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


async def run_chat(
    provider: LLMProvider,
    *,
    chat_provider: ChatProvider,
    system_prompt: str,
    user_id: UUID,
    messages: list[BaseMessage],
    tools: list[BaseTool],
) -> list[BaseMessage]:
    """Non-streaming entrypoint — used by tests; `stream_chat` below is what
    chat_service.stream_turn actually calls in the real request path."""
    compiled = _build_graph(tools)
    initial_state: ChatState = {
        "messages": messages,
        "user_id": user_id,
        "chat_provider": chat_provider,
        "system_prompt": system_prompt,
        "provider": provider,
        "agent_steps": 0,
    }
    final_state = await compiled.ainvoke(initial_state)
    return final_state["messages"][len(messages) :]


async def stream_chat(
    provider: LLMProvider,
    *,
    chat_provider: ChatProvider,
    system_prompt: str,
    user_id: UUID,
    messages: list[BaseMessage],
    tools: list[BaseTool],
) -> AsyncIterator[ChatGraphEvent]:
    """Streams token deltas and tool start/end notifications, and always ends with a
    single `{"type": "final", "messages": [...]}` event carrying every new message
    produced this turn (in order) for the caller to persist.

    Deliberately reconstructs the new-message sequence from per-model/per-tool callback
    events (`on_chat_model_end`, `on_tool_end`) rather than from the graph's own aggregate
    output — those two event names are part of LangChain's stable core callback
    taxonomy, whereas `astream_events`'s graph-level output shape has changed across
    LangGraph versions. Spot-check this against the installed `langgraph`/`langchain-core`
    versions (see docs/RESEARCH.md §E) before trusting it blindly, same discipline as
    providers/gemini.py and providers/ollama.py already apply to their own response shapes.
    """
    compiled = _build_graph(tools)
    initial_state: ChatState = {
        "messages": messages,
        "user_id": user_id,
        "chat_provider": chat_provider,
        "system_prompt": system_prompt,
        "provider": provider,
        "agent_steps": 0,
    }

    collected: list[BaseMessage] = []

    async for event in compiled.astream_events(initial_state, version="v2"):
        kind = event.get("event")

        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            delta = stringify_content(getattr(chunk, "content", None) or "")
            if delta:
                yield {"type": "token", "delta": delta}

        elif kind == "on_chat_model_end":
            output = event.get("data", {}).get("output")
            if isinstance(output, AIMessage):
                collected.append(output)

        elif kind == "on_tool_start":
            run_id = str(event.get("run_id", ""))
            name = event.get("name", "")
            yield {"type": "tool_start", "tool_call_id": run_id, "name": name}

        elif kind == "on_tool_end":
            run_id = str(event.get("run_id", ""))
            name = event.get("name", "")
            output = event.get("data", {}).get("output")

            if isinstance(output, ToolMessage):
                tool_message = output
            else:
                content = output if isinstance(output, str) else json.dumps(output or {})
                tool_message = ToolMessage(content=content, tool_call_id=run_id, name=name)
            collected.append(tool_message)

            artifact = getattr(tool_message, "artifact", None)
            if artifact is not None:
                result = artifact
            else:
                try:
                    result = json.loads(tool_message.content)
                except (TypeError, ValueError):
                    result = {}
            yield {"type": "tool_end", "tool_call_id": run_id, "name": name, "result": result}

    yield {"type": "final", "messages": collected}
