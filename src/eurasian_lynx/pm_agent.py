from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic

from .tools import TOOL_SCHEMAS, Executor

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TURNS = 6


def _system_blocks(prompt_md: str, roster_yaml: str) -> list[dict[str, Any]]:
    text = (
        f"{prompt_md}\n\n"
        f"## Team roster (YAML)\n\n```yaml\n{roster_yaml}\n```"
    )
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def run_tick(
    *,
    anthropic_client: Anthropic,
    prompt_md: str,
    roster_yaml: str,
    snapshot: dict[str, Any],
    executor: Executor,
) -> list[dict[str, Any]]:
    """Run one PM tick. Returns the list of executed tool calls for logging."""
    system = _system_blocks(prompt_md, roster_yaml)
    user_text = (
        "Here is the current snapshot. Decide which tool calls (if any) to make. "
        "Make them in this single turn; do not ask follow-up questions.\n\n"
        f"```json\n{json.dumps(snapshot, indent=2, default=str)}\n```"
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_text}]
    executed: list[dict[str, Any]] = []

    for _ in range(MAX_TURNS):
        resp = anthropic_client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=system,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses:
            break

        tool_results: list[dict[str, Any]] = []
        for tu in tool_uses:
            result = executor.execute(tu.name, dict(tu.input))
            executed.append({"name": tu.name, "input": dict(tu.input), "result": result})
            log.info("tool=%s input=%s result=%s", tu.name, dict(tu.input), result)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result),
                }
            )
        messages.append({"role": "user", "content": tool_results})

        if resp.stop_reason != "tool_use":
            break

    return executed
