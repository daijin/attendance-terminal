from unittest.mock import call, patch

from attendance_terminal.notifier import Notifier


def test_startup_and_success_use_separate_sounds(tmp_path):
    notification = tmp_path / "notification.mp3"
    startup = tmp_path / "startup.mp3"
    notification.touch()
    startup.touch()
    notifier = Notifier(
        None,
        None,
        None,
        notification_sound=str(notification),
        startup_sound=str(startup),
    )

    with patch("attendance_terminal.notifier.subprocess.run") as run:
        notifier.set_mode(online=True)
        notifier.success()

    startup_command = [
        "mpg123", "-q", "-a", "default", "-f", "22938", str(startup)
    ]
    notification_command = [
        "mpg123", "-q", "-a", "default", "-f", "22938", str(notification)
    ]
    assert run.call_args_list == [
        call(startup_command, check=True, timeout=5),
        call(startup_command, check=True, timeout=5),
        call(notification_command, check=True, timeout=5),
    ]


def test_startup_falls_back_to_notification_sound(tmp_path):
    notification = tmp_path / "notification.mp3"
    notification.touch()
    notifier = Notifier(None, None, None, notification_sound=str(notification))

    with patch("attendance_terminal.notifier.subprocess.run") as run:
        notifier.set_mode(online=False)

    assert run.call_args.args[0][-1] == str(notification)
