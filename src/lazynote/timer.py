"""Pure timer command parsing and wall-clock countdown state."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
import time
from typing import Literal


DEFAULT_DURATION_MS = 25 * 60_000


@dataclass(frozen=True)
class TimerCommand:
    """A recognized line command."""

    kind: Literal["start", "pause", "resume", "dismiss"]
    duration_ms: int | None = None


@dataclass(frozen=True)
class TimerState:
    """The single persisted countdown state."""

    status: Literal["running", "paused", "done"]
    ends_at_ms: int | None
    remaining_ms: int
    total_duration_ms: int


def now_ms() -> int:
    """Return the current wall-clock time in milliseconds."""
    return int(time.time() * 1_000)


def parse_command(line: str) -> TimerCommand | None:
    """Parse an exact timer command line, or return ``None`` for normal text."""
    if line == "timer":
        return TimerCommand("start", DEFAULT_DURATION_MS)
    if line == "timer p":
        return TimerCommand("pause")
    if line == "timer r":
        return TimerCommand("resume")
    if line == "timer x":
        return TimerCommand("dismiss")

    match = re.fullmatch(r"timer ([1-9]\d*)([smh])", line)
    if match is None:
        return None
    amount, unit = match.groups()
    multiplier = {"s": 1_000, "m": 60_000, "h": 3_600_000}[unit]
    return TimerCommand("start", int(amount) * multiplier)


def remaining_ms(state: TimerState, now_ms: int) -> int:
    """Return remaining duration, deriving a running timer from its deadline."""
    if state.status == "running":
        return max(0, (state.ends_at_ms or now_ms) - now_ms)
    return state.remaining_ms


def total_duration_ms(state: TimerState) -> int:
    """Return the timer's original duration."""
    return state.total_duration_ms


def elapsed_ms(state: TimerState, now_ms: int) -> int:
    """Return elapsed time without exceeding the original duration."""
    return max(0, state.total_duration_ms - remaining_ms(state, now_ms))


def start(duration_ms: int, now_ms: int) -> TimerState:
    """Start a positive-duration countdown at ``now_ms``."""
    return TimerState("running", now_ms + duration_ms, duration_ms, duration_ms)


def refresh(state: TimerState, now_ms: int) -> TimerState:
    """Update a running state for wall-clock elapsed time and completion."""
    if state.status != "running":
        return state
    left = remaining_ms(state, now_ms)
    if left == 0:
        return TimerState("done", None, 0, state.total_duration_ms)
    return TimerState("running", state.ends_at_ms, left, state.total_duration_ms)


def pause(state: TimerState, now_ms: int) -> TimerState:
    """Pause a running timer; other states remain unchanged."""
    current = refresh(state, now_ms)
    if current.status != "running":
        return current
    return TimerState("paused", None, current.remaining_ms, current.total_duration_ms)


def resume(state: TimerState, now_ms: int) -> TimerState:
    """Resume a paused timer; other states remain unchanged."""
    if state.status != "paused":
        return state
    return TimerState(
        "running", now_ms + state.remaining_ms, state.remaining_ms, state.total_duration_ms
    )


def format_remaining(milliseconds: int) -> str:
    """Render positive duration as ``MM:SS``, rounding visible seconds upward."""
    seconds = max(0, math.ceil(milliseconds / 1_000))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def encode_state(state: TimerState | None) -> str:
    """Serialize state for the string-only settings repository."""
    if state is None:
        return ""
    return json.dumps(
        {
            "status": state.status,
            "ends_at_ms": state.ends_at_ms,
            "remaining_ms": state.remaining_ms,
            "total_duration_ms": state.total_duration_ms,
        },
        separators=(",", ":"),
    )


def decode_state(value: str | None) -> TimerState | None:
    """Decode valid persisted state; corrupt or absent settings become inactive."""
    if not value:
        return None
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    status = data.get("status")
    ends_at_ms = data.get("ends_at_ms")
    remaining = data.get("remaining_ms")
    total = data.get("total_duration_ms", remaining)
    if status not in ("running", "paused", "done"):
        return None
    if not isinstance(remaining, int) or isinstance(remaining, bool) or remaining < 0:
        return None
    if not isinstance(total, int) or isinstance(total, bool) or total < remaining:
        return None
    if status == "running":
        if not isinstance(ends_at_ms, int) or isinstance(ends_at_ms, bool):
            return None
    elif ends_at_ms is not None:
        return None
    return TimerState(status, ends_at_ms, remaining, total)
