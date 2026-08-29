"""Best-effort desktop notifications for Lazynote."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import shutil
import subprocess


NotifyRunner = Callable[[Sequence[str]], object]


def _run_notify_send(args: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=False, timeout=5)


def notify_timer_finished(
    runner: NotifyRunner | None = None,
) -> bool:
    """Request a desktop completion notification with a sound hint.

    ``notify-send`` is used instead of PySide6 QtDBus because PySide6 marshals
    Python integers as signed D-Bus values while the notification API requires
    an unsigned replacement ID.
    """
    if runner is None:
        if shutil.which("notify-send") is None:
            return False
        runner = _run_notify_send
    try:
        result = runner(
            [
                "notify-send",
                "--app-name=Lazynote",
                "--expire-time=10000",
                "--hint=string:sound-name:complete",
                "Timer finished",
            ]
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return getattr(result, "returncode", 1) == 0
