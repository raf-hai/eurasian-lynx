from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"last_run_at": None, "tasks": {}, "notes": []}
    with path.open("r") as f:
        return json.load(f)


def save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".state-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def task_entry(state: dict[str, Any], task_gid: str) -> dict[str, Any]:
    return state.setdefault("tasks", {}).setdefault(
        task_gid,
        {"reminders_sent": [], "snoozed_until": None, "last_seen_modified": None, "last_known_assignee": None},
    )


def already_pinged_today(state: dict[str, Any], task_gid: str) -> bool:
    entry = state.get("tasks", {}).get(task_gid)
    if not entry:
        return False
    today = _utc_today_iso()
    return any(r.get("date") == today for r in entry.get("reminders_sent", []))


def record_ping(state: dict[str, Any], task_gid: str, text: str) -> None:
    entry = task_entry(state, task_gid)
    entry["reminders_sent"].append({"date": _utc_today_iso(), "at": _utc_now_iso(), "text": text})


def is_snoozed(state: dict[str, Any], task_gid: str) -> bool:
    entry = state.get("tasks", {}).get(task_gid)
    if not entry or not entry.get("snoozed_until"):
        return False
    return _utc_now_iso() < entry["snoozed_until"]


def set_snooze(state: dict[str, Any], task_gid: str, until_iso: str, reason: str) -> None:
    entry = task_entry(state, task_gid)
    entry["snoozed_until"] = until_iso
    entry["snooze_reason"] = reason


def record_assignment(state: dict[str, Any], task_gid: str, assignee_name: str) -> None:
    entry = task_entry(state, task_gid)
    entry["last_known_assignee"] = assignee_name
    entry["last_assigned_at"] = _utc_now_iso()


def add_note(state: dict[str, Any], text: str) -> None:
    state.setdefault("notes", []).append({"at": _utc_now_iso(), "text": text})


def mark_run(state: dict[str, Any]) -> None:
    state["last_run_at"] = _utc_now_iso()
