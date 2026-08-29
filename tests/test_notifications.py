from types import SimpleNamespace

from lazynote import notifications


def test_sends_notification_with_sound_hint():
    calls = []

    def runner(args):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    assert notifications.notify_timer_finished(runner) is True
    assert calls == [[
        "notify-send",
        "--app-name=Lazynote",
        "--expire-time=10000",
        "--hint=string:sound-name:complete",
        "Timer finished",
    ]]


def test_returns_false_when_notify_send_is_unavailable(monkeypatch):
    monkeypatch.setattr(notifications.shutil, "which", lambda _: None)
    assert notifications.notify_timer_finished() is False


def test_returns_false_when_notification_command_fails():
    assert notifications.notify_timer_finished(lambda _: SimpleNamespace(returncode=1)) is False
