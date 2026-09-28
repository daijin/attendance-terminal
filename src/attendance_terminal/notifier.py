from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

LOG = logging.getLogger(__name__)


class Notifier:
    """Optional GPIO indicators. Pins use BCM numbering and may be omitted."""

    def __init__(
        self,
        buzzer_pin: int | None,
        online_led_pin: int | None,
        offline_led_pin: int | None,
        notification_wav: str | None = None,
        audio_device: str = "default",
        notification_sound: str | None = None,
        audio_volume_percent: int = 70,
        startup_sound: str | None = None,
    ) -> None:
        self.buzzer = self.online_led = self.offline_led = None
        # notification_wav is retained for compatibility with existing configs.
        selected_sound = notification_sound or notification_wav
        self.notification_sound = self._validate_sound(selected_sound, "notification")
        self.startup_sound = self._validate_sound(startup_sound, "startup")
        self.audio_device = audio_device
        if not 0 <= audio_volume_percent <= 100:
            raise ValueError("audio_volume_percent must be between 0 and 100")
        self.audio_volume_percent = audio_volume_percent
        if any(pin is not None for pin in (buzzer_pin, online_led_pin, offline_led_pin)):
            try:
                from gpiozero import Buzzer, LED

                self.buzzer = Buzzer(buzzer_pin) if buzzer_pin is not None else None
                self.online_led = LED(online_led_pin) if online_led_pin is not None else None
                self.offline_led = LED(offline_led_pin) if offline_led_pin is not None else None
            except Exception:
                LOG.exception("GPIO notifier initialization failed; continuing without GPIO")

    @staticmethod
    def _validate_sound(value: str | None, label: str) -> Path | None:
        if not value:
            return None
        sound = Path(value)
        if not sound.is_file():
            LOG.error("%s sound does not exist: %s", label, sound)
            return None
        if sound.suffix.casefold() not in (".mp3", ".wav"):
            raise ValueError(f"{label} sound must be an MP3 or WAV file")
        return sound

    def set_mode(self, online: bool, audible: bool = True) -> None:
        if self.online_led:
            self.online_led.value = bool(online)
        if self.offline_led:
            self.offline_led.value = not online
        if audible:
            self._beep(
                count=2 if online else 1,
                duration=0.12,
                sound=self.startup_sound or self.notification_sound,
            )

    def success(self) -> None:
        self._beep(count=1, duration=0.08)

    def error(self) -> None:
        self._beep(count=3, duration=0.15)

    def _beep(
        self,
        count: int,
        duration: float,
        sound: Path | None = None,
    ) -> None:
        if self.buzzer:
            for index in range(count):
                self.buzzer.on()
                time.sleep(duration)
                self.buzzer.off()
                if index + 1 < count:
                    time.sleep(0.08)
            return
        selected_sound = sound or self.notification_sound
        if selected_sound:
            for index in range(count):
                try:
                    if selected_sound.suffix.casefold() == ".mp3":
                        # mpg123 uses 32768 as 100% software volume.
                        scale = round(32768 * self.audio_volume_percent / 100)
                        command = [
                            "mpg123", "-q", "-a", self.audio_device,
                            "-f", str(scale), str(selected_sound),
                        ]
                    else:
                        command = [
                            "aplay", "-q", "-D", self.audio_device,
                            str(selected_sound),
                        ]
                    subprocess.run(
                        command,
                        check=True,
                        timeout=5,
                    )
                except (OSError, subprocess.SubprocessError):
                    LOG.exception("sound notification failed")
                    return
                if index + 1 < count:
                    time.sleep(0.08)
