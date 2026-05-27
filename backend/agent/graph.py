"""DeepAgent setup. PRD Section 7.

We load the system prompt template + the two skill files at import time, and
substitute {today} / {staff_name} per request. Skills are inlined into the
system prompt (PRD line 406: not loaded on-demand in v1).

The agent is constructed per request so we get today's date baked in; the
SQLite checkpointer is a long-lived singleton so memory persists across the
agent objects within the same thread_id.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import AsyncIterator, Optional

import aiosqlite
from deepagents import SubAgent, create_deep_agent
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent.tools import make_tools

load_dotenv()

_AGENT_DIR = Path(__file__).parent
_PROMPTS_DIR = _AGENT_DIR / "prompts"
_SKILLS_DIR = _AGENT_DIR / "skills"

_PROMPT_TEMPLATE = (_PROMPTS_DIR / "main_system.md").read_text(encoding="utf-8")
_INCIDENT_LOGGING = (_SKILLS_DIR / "incident_logging.md").read_text(encoding="utf-8")

_CHECKPOINT_DB_PATH = str(_AGENT_DIR.parent / "agent_memory.db")

# Async checkpointer initialised on startup. astream_events is async, so the
# sync SqliteSaver raises "does not support async methods".
_checkpoint_conn: Optional[aiosqlite.Connection] = None
_checkpointer: Optional[AsyncSqliteSaver] = None


async def init_checkpointer() -> None:
    """Open the aiosqlite connection and ensure tables exist. Idempotent."""
    global _checkpoint_conn, _checkpointer
    if _checkpointer is not None:
        return
    _checkpoint_conn = await aiosqlite.connect(_CHECKPOINT_DB_PATH)
    _checkpointer = AsyncSqliteSaver(_checkpoint_conn)
    await _checkpointer.setup()


async def close_checkpointer() -> None:
    global _checkpoint_conn, _checkpointer
    if _checkpoint_conn is not None:
        await _checkpoint_conn.close()
    _checkpoint_conn = None
    _checkpointer = None


def build_system_prompt(staff_name: str, role: str = "staff") -> str:
    return _PROMPT_TEMPLATE.format(
        today=date.today().isoformat(),
        staff_name=staff_name,
        role=role,
        incident_logging_skill=_INCIDENT_LOGGING,
    )


def build_health_advisor_prompt() -> str:
    template = (_PROMPTS_DIR / "health_advisor.md").read_text(encoding="utf-8")
    return template.format(today=date.today().isoformat())


async def _build_agent(staff_name: str, staff_id: int, role: str = "staff"):
    await init_checkpointer()
    model = init_chat_model(
        "openai:gpt-4o-mini",
        temperature=0.3,
        use_responses_api=False,  # PRD doesn't need Responses API features.
    )

    # Specialist sub-agent for canine health questions. Has only read-only
    # tools (query_db + web_search), its own strict safety guardrail, and
    # is invoked by the main agent via the auto-injected `task` tool when
    # the main agent decides to delegate.
    all_tools = make_tools(staff_id)
    health_tools = [t for t in all_tools if t.name in ("query_db", "web_search")]

    health_advisor = SubAgent(
        name="health_advisor",
        description=(
            "Canine health research specialist. Delegate any question about "
            "a dog's symptoms, medication safety, dose/toxicity questions, "
            "breed-specific risks, emergency signs, or general veterinary "
            "topics to this agent. It has strict safety guardrails and "
            "always defers dose/diagnosis/treatment to a vet."
        ),
        system_prompt=build_health_advisor_prompt(),
        tools=health_tools,
    )

    return create_deep_agent(
        model=model,
        tools=all_tools,
        subagents=[health_advisor],
        system_prompt=build_system_prompt(staff_name, role),
        checkpointer=_checkpointer,
    )


async def astream_chat(
    *,
    message: str,
    thread_id: str,
    staff_name: str,
    staff_id: int,
    role: str = "staff",
) -> AsyncIterator[dict]:
    """Yield normalized event dicts the /chat endpoint translates into SSE.

    Event shapes (all dicts):
      {"type": "token", "content": "..."}
      {"type": "tool_call", "name": "...", "args": {...}}
      {"type": "tool_result", "name": "...", "result_summary": "..."}
      {"type": "done"}
      {"type": "error", "detail": "..."}
    """
    agent = await _build_agent(staff_name, staff_id, role)
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {"messages": [HumanMessage(content=message)]}

    try:
        async for event in agent.astream_events(inputs, config=config, version="v2"):
            kind = event.get("event")
            data = event.get("data", {}) or {}

            if kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                # AIMessageChunk has .content which can be str or list of blocks.
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    yield {"type": "token", "content": content}
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text") or ""
                            if text:
                                yield {"type": "token", "content": text}

            elif kind == "on_tool_start":
                yield {
                    "type": "tool_call",
                    "name": event.get("name", "unknown"),
                    "args": data.get("input", {}),
                }

            elif kind == "on_tool_end":
                output = data.get("output")
                summary = str(output) if output is not None else ""
                # Keep tool_result short for SSE — full output is in the trace.
                if len(summary) > 240:
                    summary = summary[:237] + "..."
                yield {
                    "type": "tool_result",
                    "name": event.get("name", "unknown"),
                    "result_summary": summary,
                }
    except Exception as e:
        yield {"type": "error", "detail": str(e)}
    finally:
        yield {"type": "done"}
