from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic

from . import state as state_mod
from .asana_client import AsanaClient, collect_tasks
from .config import STATE_PATH, load_config
from .pm_agent import run_tick
from .slack_client import SlackClient
from .tools import Executor, Roster


def _build_snapshot(
    *,
    tasks: list[dict[str, Any]],
    state: dict[str, Any],
    project_names: dict[str, str],
) -> dict[str, Any]:
    last_run = state.get("last_run_at")
    deltas: list[dict[str, Any]] = []
    for t in tasks:
        prior = state.get("tasks", {}).get(t["gid"], {})
        modified = t.get("modified_at")
        if modified and prior.get("last_seen_modified") != modified:
            deltas.append(
                {
                    "gid": t["gid"],
                    "name": t.get("name"),
                    "was": prior.get("last_seen_modified"),
                    "now": modified,
                    "assignee": (t.get("assignee") or {}).get("name"),
                }
            )
    return {
        "now_utc": datetime.now(timezone.utc).isoformat(),
        "last_run_at": last_run,
        "project_names": project_names,
        "open_tasks": tasks,
        "deltas_since_last_run": deltas,
        "recent_state": {
            gid: {
                "last_known_assignee": e.get("last_known_assignee"),
                "snoozed_until": e.get("snoozed_until"),
                "reminders_today": [r for r in e.get("reminders_sent", []) if r.get("date") == datetime.now(timezone.utc).date().isoformat()],
            }
            for gid, e in state.get("tasks", {}).items()
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eurasian-lynx", description="LLM-driven Asana to Slack PM agent.")
    parser.add_argument("--once", action="store_true", help="Run a single tick and exit. (Currently the only mode.)")
    parser.add_argument("--dry-run", action="store_true", help="Do not call Asana writes or Slack posts; log intent only.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("eurasian_lynx")

    cfg = load_config()
    if not cfg.project_gids:
        log.error("no Asana project gids configured; edit config/projects.yaml")
        return 2

    state = state_mod.load(STATE_PATH)

    asana = AsanaClient(cfg.asana_pat, dry_run=args.dry_run)
    slack = SlackClient(cfg.slack_bot_token, cfg.summa_channel_id, dry_run=args.dry_run)
    roster = Roster.from_yaml(cfg.roster_entries)
    executor = Executor(asana=asana, slack=slack, roster=roster, state=state)

    tasks = collect_tasks(asana, cfg.project_gids, modified_since=state.get("last_run_at"))
    log.info("fetched %d open tasks across %d project(s)", len(tasks), len(cfg.project_gids))

    snapshot = _build_snapshot(tasks=tasks, state=state, project_names=cfg.project_names)

    anthropic_client = Anthropic(api_key=cfg.anthropic_api_key)
    executed = run_tick(
        anthropic_client=anthropic_client,
        prompt_md=cfg.prompt_md,
        roster_yaml=cfg.roster_yaml_text,
        snapshot=snapshot,
        executor=executor,
    )

    for t in tasks:
        entry = state_mod.task_entry(state, t["gid"])
        entry["last_seen_modified"] = t.get("modified_at")
        if t.get("assignee"):
            entry["last_known_assignee"] = (t["assignee"] or {}).get("name")

    state_mod.mark_run(state)
    state_mod.save(STATE_PATH, state)

    print(json.dumps({"tick": "ok", "tool_calls": executed, "tasks_seen": len(tasks)}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
