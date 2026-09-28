from __future__ import annotations

import json
import logging
import ssl
import urllib.request

from .config import Config
from .store import PunchStore

LOG = logging.getLogger(__name__)


class Uploader:
    def __init__(self, config: Config, store: PunchStore) -> None:
        self.config = config
        self.store = store

    def upload_once(self) -> int:
        batch = self.store.pending(self.config.upload_batch_size)
        if not batch:
            return 0
        body = json.dumps(
            {
                "secret": self.config.upload_secret,
                "sheet_name": self.config.sheet_name,
                "events": [item.as_dict() for item in batch],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.config.upload_url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(
            request, timeout=15, context=ssl.create_default_context()
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "upload rejected"))
        acknowledged = result.get("acknowledged_event_ids", [])
        requested = {item.event_id for item in batch}
        if not set(acknowledged).issubset(requested):
            raise RuntimeError("server acknowledged unknown event ids")
        self.store.mark_uploaded(acknowledged)
        LOG.info("uploaded %d event(s)", len(acknowledged))
        return len(acknowledged)
