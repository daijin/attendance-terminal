from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from pathlib import Path

from .config import Config, network_available
from .notifier import Notifier
from .reader import Reader
from .store import PunchStore
from .uploader import Uploader

LOG = logging.getLogger(__name__)


def run(config: Config) -> None:
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())

    store = PunchStore(config.database_path, config.device_id)
    notifier = Notifier(
        buzzer_pin=config.buzzer_pin,
        online_led_pin=config.online_led_pin,
        offline_led_pin=config.offline_led_pin,
        notification_wav=config.notification_wav,
        audio_device=config.audio_device,
        notification_sound=config.notification_sound,
        audio_volume_percent=config.audio_volume_percent,
        startup_sound=config.startup_sound,
    )
    online_mode = network_available()
    # /run is cleared at OS boot. Keep the marker over service restarts so the
    # mode sound is emitted once per OS boot, not whenever systemd restarts us.
    startup_marker = Path("/run/attendance-terminal/startup-notified")
    notifier.set_mode(online_mode, audible=not startup_marker.exists())
    try:
        startup_marker.touch(exist_ok=True)
    except OSError:
        # Running outside the systemd unit (for example during development)
        # must not prevent attendance recording.
        LOG.warning("could not create startup notification marker")
    LOG.info("started in %s mode", "upload" if online_mode else "punch-only")

    last_seen: dict[str, float] = {}

    def on_uid(uid: str) -> None:
        now_monotonic = time.monotonic()
        previous = last_seen.get(uid)
        if previous is not None and now_monotonic - previous < config.debounce_seconds:
            LOG.info("ignored duplicate UID %s", uid)
            return
        last_seen[uid] = now_monotonic
        punch = store.add(uid)
        LOG.info("recorded event=%s at=%s", punch.event_id, punch.punched_at)
        notifier.success()

    def upload_loop() -> None:
        uploader = Uploader(config, store)
        while not stopped.is_set():
            try:
                while uploader.upload_once():
                    pass
            except Exception:
                LOG.exception("upload failed; records remain queued")
            stopped.wait(config.upload_interval_seconds)

    if online_mode:
        threading.Thread(target=upload_loop, name="uploader", daemon=True).start()
    try:
        Reader(config.reader_name_contains, on_uid).run_forever(stopped.is_set)
    finally:
        stopped.set()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/attendance-terminal/config.json")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run(Config.load(args.config))


if __name__ == "__main__":
    main()
