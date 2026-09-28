import json
from datetime import datetime, timezone
from unittest.mock import patch

from attendance_terminal.config import Config
from attendance_terminal.store import PunchStore
from attendance_terminal.uploader import Uploader


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.body).encode()


def test_upload_acknowledges_rows(tmp_path):
    store = PunchStore(str(tmp_path / "db"), "pi-01")
    punch = store.add("AB", datetime.now(timezone.utc))
    config = Config("pi-01", str(tmp_path / "db"), "https://example.test", "secret")
    response = FakeResponse({"ok": True, "acknowledged_event_ids": [punch.event_id]})
    with patch("urllib.request.urlopen", return_value=response):
        assert Uploader(config, store).upload_once() == 1
    assert store.count_pending() == 0
