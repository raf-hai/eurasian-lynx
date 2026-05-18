from __future__ import annotations

import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

log = logging.getLogger(__name__)


class SlackClient:
    def __init__(self, bot_token: str, summa_channel_id: str, dry_run: bool = False):
        self.dry_run = dry_run
        self.summa_channel_id = summa_channel_id
        self._client = WebClient(token=bot_token)

    def post_to_summa(self, text: str) -> str | None:
        if self.dry_run:
            log.info("[dry-run] would post to #summa (%s): %s", self.summa_channel_id, text)
            return "dry-run"
        try:
            resp = self._client.chat_postMessage(channel=self.summa_channel_id, text=text)
            return resp.get("ts")
        except SlackApiError as e:
            log.error("slack post failed: %s", e.response.get("error"))
            return None
