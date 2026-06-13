"""Agent harness: a transparent Anthropic Messages API tool-use loop.

One small, controllable loop (not the Agent SDK) so every step can be streamed
into the team activity feed. Opus 4.8. The org API key is read from .env so usage
draws from the build-day $500 organization pool.

A digital employee = a scoped system prompt + a few domain tools + this loop.
Guardrails live in the system prompt (scope/refusal) and in the tool set (an
agent only holds the tools for its job).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

MODEL = "claude-opus-4-8"
MAX_TURNS = 10


# --- minimal .env loader (no extra dep) ------------------------------------- #
def load_env() -> None:
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


load_env()


def have_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def agents_enabled() -> bool:
    """Live agent calls (Haiku conversation + Opus reasoning) only run where this is
    explicitly turned on. The public deployment never sets BAXIE_LIVE_AGENTS, so it
    stays fully scripted: instant, free, and impossible to drain the org credits."""
    return have_key() and os.environ.get("BAXIE_LIVE_AGENTS") == "1"


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    impl: Callable[[dict], dict]   # takes tool input, returns JSON-able result


@dataclass
class AgentRun:
    final_text: str
    tool_calls: list[dict]         # [{name, input, result}]
    turns: int


def run_agent(
    system: str,
    user: str,
    tools: Optional[list[Tool]] = None,
    on_step: Optional[Callable[[str], None]] = None,
    max_turns: int = MAX_TURNS,
) -> AgentRun:
    """Run one agent to completion. Returns final text + the tool calls it made.

    Raises RuntimeError if no API key (callers should fall back to the scripted
    deterministic run for offline/no-key demos)."""
    if not have_key():
        raise RuntimeError("ANTHROPIC_API_KEY not set (org key for the $500 pool)")

    import anthropic

    client = anthropic.Anthropic()
    tools = tools or []
    tool_map = {t.name: t for t in tools}
    api_tools = [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]

    messages = [{"role": "user", "content": user}]
    tool_calls: list[dict] = []

    for turn in range(1, max_turns + 1):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=api_tools or anthropic.NOT_GIVEN,
            messages=messages,
        )

        text_parts = [b.text for b in resp.content if b.type == "text"]
        if text_parts and on_step:
            on_step(" ".join(text_parts))

        if resp.stop_reason != "tool_use":
            return AgentRun(final_text=" ".join(text_parts).strip(),
                            tool_calls=tool_calls, turns=turn)

        # execute tool calls, append results, loop
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            tool = tool_map.get(block.name)
            out = tool.impl(block.input) if tool else {"error": f"unknown tool {block.name}"}
            tool_calls.append({"name": block.name, "input": block.input, "result": out})
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(out),
            })
        messages.append({"role": "user", "content": results})

    return AgentRun(final_text="", tool_calls=tool_calls, turns=max_turns)
