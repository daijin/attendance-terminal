from __future__ import annotations

import logging
import queue
import time
from collections.abc import Callable
from typing import Any

LOG = logging.getLogger(__name__)
GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]


def _read_uid(card: Any) -> str:
    """Read one UID from a card reported by PC/SC."""
    connection = card.createConnection()
    connection.connect()
    try:
        data, sw1, sw2 = connection.transmit(GET_UID)
        if (sw1, sw2) != (0x90, 0x00) or not data:
            raise RuntimeError(f"GET UID failed: {sw1:02X}{sw2:02X}")
        return "".join(f"{byte:02X}" for byte in data)
    finally:
        try:
            connection.disconnect()
        except Exception:
            # Removal may make disconnect fail; the connection is no longer used.
            pass
        try:
            connection.release()
        except Exception:
            pass


class Reader:
    """Read UID/IDm through RC-S300's PC/SC interface."""

    def __init__(self, reader_name_contains: str, on_uid: Callable[[str], None]) -> None:
        self.reader_name_contains = reader_name_contains.casefold()
        self.on_uid = on_uid

    def run_forever(self, stop_requested: Callable[[], bool]) -> None:
        from smartcard.CardMonitoring import CardMonitor, CardObserver

        events: queue.Queue[Any] = queue.Queue()

        class Observer(CardObserver):
            def update(self, observable: Any, actions: Any) -> None:
                added_cards, _removed_cards = actions
                for card in added_cards:
                    events.put(card)

        observer = Observer()

        while not stop_requested():
            monitor = None
            try:
                monitor = CardMonitor()
                monitor.addObserver(observer)
                while not stop_requested():
                    try:
                        card = events.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    reader_name = str(getattr(card, "reader", ""))
                    if self.reader_name_contains not in reader_name.casefold():
                        continue

                    try:
                        self.on_uid(_read_uid(card))
                    except Exception:
                        LOG.exception("card read failed")
            except Exception:
                LOG.exception("PC/SC monitor is unavailable; waiting")
                time.sleep(2)
            finally:
                if monitor is not None:
                    try:
                        monitor.deleteObserver(observer)
                    except Exception:
                        pass
