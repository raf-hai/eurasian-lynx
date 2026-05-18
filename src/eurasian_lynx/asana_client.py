from __future__ import annotations

import logging
from typing import Any, Iterable

import asana
from asana.rest import ApiException

log = logging.getLogger(__name__)

TASK_FIELDS = "gid,name,notes,assignee.name,assignee.gid,completed,due_on,due_at,modified_at,created_at,tags.name,permalink_url"


class AsanaClient:
    def __init__(self, pat: str, dry_run: bool = False):
        self.dry_run = dry_run
        cfg = asana.Configuration()
        cfg.access_token = pat
        self._client = asana.ApiClient(cfg)
        self._tasks = asana.TasksApi(self._client)

    def list_open_tasks(self, project_gid: str, modified_since: str | None = None) -> list[dict[str, Any]]:
        opts: dict[str, Any] = {"opt_fields": TASK_FIELDS, "completed_since": "now"}
        if modified_since:
            opts["modified_since"] = modified_since
        try:
            return list(self._tasks.get_tasks_for_project(project_gid, opts))
        except ApiException as e:
            log.error("asana list_open_tasks failed for %s: %s", project_gid, e)
            return []

    def assign_task(self, task_gid: str, user_gid: str) -> bool:
        if self.dry_run:
            log.info("[dry-run] would assign task %s to user %s", task_gid, user_gid)
            return True
        try:
            self._tasks.update_task({"data": {"assignee": user_gid}}, task_gid, {})
            return True
        except ApiException as e:
            log.error("asana assign_task failed: %s", e)
            return False


def collect_tasks(client: AsanaClient, project_gids: Iterable[str], modified_since: str | None) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for gid in project_gids:
        for t in client.list_open_tasks(gid, modified_since=modified_since):
            seen[t["gid"]] = t
    return list(seen.values())
