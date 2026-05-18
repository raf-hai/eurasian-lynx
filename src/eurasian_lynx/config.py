from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
STATE_PATH = REPO_ROOT / "state" / "state.json"


@dataclass
class Config:
    asana_pat: str
    slack_bot_token: str
    anthropic_api_key: str
    summa_channel_id: str
    project_gids: list[str]
    project_names: dict[str, str]
    prompt_md: str
    roster_yaml_text: str
    roster_entries: list[dict[str, str]]


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"missing required env var: {name}")
    return val


def load_config() -> Config:
    load_dotenv(REPO_ROOT / ".env")

    projects_doc = yaml.safe_load((CONFIG_DIR / "projects.yaml").read_text())
    project_entries = projects_doc.get("projects", [])
    gids = [p["gid"] for p in project_entries if p.get("gid") and p["gid"] != "REPLACE_ME"]
    names = {p["gid"]: p.get("name", "") for p in project_entries}

    roster_text = (CONFIG_DIR / "roster.yaml").read_text()
    roster_doc = yaml.safe_load(roster_text)
    roster_entries = roster_doc.get("roster", [])

    prompt_md = (CONFIG_DIR / "prompt.md").read_text()

    return Config(
        asana_pat=_require_env("ASANA_PAT"),
        slack_bot_token=_require_env("SLACK_BOT_TOKEN"),
        anthropic_api_key=_require_env("ANTHROPIC_API_KEY"),
        summa_channel_id=_require_env("SLACK_SUMMA_CHANNEL_ID"),
        project_gids=gids,
        project_names=names,
        prompt_md=prompt_md,
        roster_yaml_text=roster_text,
        roster_entries=roster_entries,
    )
