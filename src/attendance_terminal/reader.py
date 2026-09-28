from __future__ import annotations

import logging
import time
from collections.abc import Callable

LOG = logging.getLogger(__name__)
GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]


class Reader:
    """Read UID/IDm through RC-S300's PC/SC interface."""

    def __init__(self, reader_name_contains: str, on_uid: Callable[[str], None]) -> None:
        self.reader_name_contains = reader_name_contains.casefold()
        self.on_uid = on_uid

    def run_forever(self, stop_requested: Callable[[], bool]) -> None:
        from smartcard.Exceptions import CardConnectionException, NoCardException
        from smartcard.System import readers

        logged_missing = False
        while not stop_requested():
            try:
                devices = [
                    device for device in readers()
                    if self.reader_name_contains in str(device).casefold()
                ]
            except Exception:
                if not logged_missing:
                    LOG.exception("PC/SC service is unavailable; waiting")
                    logged_missing = True
                time.sleep(2)
                continue
            if not devices:
                if not logged_missing:
                    LOG.error("RC-S300 not found; waiting for reader")
                    logged_missing = True
                time.sleep(2)
                continue
            logged_missing = False
            device = devices[0]
            try:
                connection = device.createConnection()
                connection.connect()
                data, sw1, sw2 = connection.transmit(GET_UID)
                if (sw1, sw2) != (0x90, 0x00) or not data:
                    raise RuntimeError(f"GET UID failed: {sw1:02X}{sw2:02X}")
                self.on_uid("".join(f"{byte:02X}" for byte in data))
                # Wait for removal. This prevents a held card from creating punches.
                while not stop_requested():
                    try:
                        connection.transmit(GET_UID)
                        time.sleep(0.15)
                    except (CardConnectionException, NoCardException):
                        break
                    except Exception:
                        break
            except (CardConnectionException, NoCardException):
                time.sleep(0.15)
            except Exception:
                LOG.exception("card read failed")
                time.sleep(1)
