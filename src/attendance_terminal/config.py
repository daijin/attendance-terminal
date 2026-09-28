from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    device_id: str
    database_path: str
    upload_url: str
    upload_secret: str
    sheet_name: str = "打刻ログ"
    debounce_seconds: float = 3.0
    upload_interval_seconds: float = 30.0
    upload_batch_size: int = 100
    reader_name_contains: str = "RC-S300"
    buzzer_pin: int | None = None
    online_led_pin: int | None = None
    offline_led_pin: int | None = None
    notification_wav: str | None = None
    notification_sound: str | None = None
    audio_device: str = "default"
    audio_volume_percent: int = 70

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        required = ("device_id", "database_path", "upload_url", "upload_secret")
        missing = [key for key in required if key not in raw]
        if missing:
            raise ValueError("config keys missing: " + ", ".join(missing))
        if not raw["device_id"].strip():
            raise ValueError("device_id must not be empty")
        return cls(**raw)


def network_available(timeout: float = 3.0) -> bool:
    """Check basic Internet reachability without depending on DNS or HTTP."""
    try:
        with socket.create_connection(("8.8.8.8", 443), timeout=timeout):
            return True
    except OSError:
        return False
