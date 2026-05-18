from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from . import state as state_mod
from .asana_client import AsanaClient
from .slack_client import SlackClient

log = logging.getLogger(__name__)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "assign_task",
        "description": "Assign an Asana task to a teammate by name. Use only when the right owner is clear; otherwise post a question to #summa instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_gid": {"type": "string", "description": "The Asana task gid."},
                "assignee_name": {"type": "string", "description": "Teammate name as it appears in the roster."},
            },
            "required": ["task_gid", "assignee_name"],
        },
    },
    {
        "name": "post_to_summa",
        "description": "Post a single concise message to the #summa Slack channel. Use sparingly — one message per actionable item per day.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Message body. Plain text. One sentence is ideal."},
                "related_task_gids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional task gids this message refers to. Used for idempotency tracking.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "snooze_task",
        "description": "Suppress reminders for a task until a date. Use when an assignee has explicitly indicated they'll get to it later.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_gid": {"type": "string"},
                "until_iso": {"type": "string", "description": "ISO-8601 UTC datetime when reminders resume."},
                "reason": {"type": "string"},
            },
            "required": ["task_gid", "until_iso", "reason"],
        },
    },
    {
        "name": "note",
        "description": "Write a debug note explaining why no external action was taken for a task this tick. No side effects.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]


@dataclass
class Roster:
    by_name: dict[str, dict[str, str]]

    @classmethod
    def from_yaml(cls, entries: list[dict[str, str]]) -> "Roster":
        return cls(by_name={e["name"]: e for e in entries})

    def asana_gid(self, name: str) -> str | None:
        e = self.by_name.get(name)
        return e.get("asana_gid") if e else None

    def slack_id(self, name: str) -> str | None:
        e = self.by_name.get(name)
        return e.get("slack_id") if e else None


@dataclass
class Executor:
    asana: AsanaClient
    slack: SlackClient
    roster: Roster
    state: dict[str, Any]

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is None:
            return {"ok": False, "error": f"unknown tool: {tool_name}"}
        return handler(**tool_input)

    def _tool_assign_task(self, task_gid: str, assignee_name: str) -> dict[str, Any]:
        user_gid = self.roster.asana_gid(assignee_name)
        if not user_gid or user_gid == "REPLACE_ME":
            return {"ok": False, "error": f"no asana gid in roster for {assignee_name!r}"}
        entry = self.state.get("tasks", {}).get(task_gid, {})
        if entry.get("last_known_assignee") == assignee_name:
            return {"ok": True, "skipped": "already assigned per state"}
        ok = self.asana.assign_task(task_gid, user_gid)
        if ok:
            state_mod.record_assignment(self.state, task_gid, assignee_name)
        return {"ok": ok}

    def _tool_post_to_summa(self, text: str, related_task_gids: list[str] | None = None) -> dict[str, Any]:
        related_task_gids = related_task_gids or []
        for gid in related_task_gids:
            if state_mod.already_pinged_today(self.state, gid):
                return {"ok": True, "skipped": f"already pinged {gid} today"}
        ts = self.slack.post_to_summa(text)
        if ts is None:
            return {"ok": False, "error": "slack post failed"}
        for gid in related_task_gids:
            state_mod.record_ping(self.state, gid, text)
        return {"ok": True, "ts": ts}

    def _tool_snooze_task(self, task_gid: str, until_iso: str, reason: str) -> dict[str, Any]:
        state_mod.set_snooze(self.state, task_gid, until_iso, reason)
        return {"ok": True}

    def _tool_note(self, text: str) -> dict[str, Any]:
        state_mod.add_note(self.state, text)
        return {"ok": True}
