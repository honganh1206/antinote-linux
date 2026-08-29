# Timer Commands and Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start, pause, resume, and persist one countdown timer through commands typed on any note line, with a compact non-modal QML overlay and desktop completion notification.

**Architecture:** Keep command parsing and wall-clock state transitions in a PySide-free `lazynote.timer` module. `Backend` owns the live Qt refresh timer, persists one serialized timer state in `app_settings`, exposes timer properties and a command slot to QML, and delegates notifications to a small DBus adapter. `Editor.qml` consumes a recognized command line on Enter; `TimerOverlay.qml` renders the state exposed by the backend.

**Tech Stack:** Python 3.12+, PySide6/Qt 6 (QtCore, QtDBus, Qt Quick), QML, stdlib JSON, sqlite3 settings, pytest, ruff.

**Spec:** `docs/plans/2026-08-29-timer-design.md`

## Global Constraints

- Keep pure modules free of PySide6 imports.
- Add no Python dependencies; use the installed PySide6 QtDBus module for `org.freedesktop.Notifications`.
- Support Linux X11 and Wayland; desktop notification failure must leave timer state intact.
- Support exactly one active timer and persist it in `app_settings`.
- `timer` defaults to 25 minutes; accept only positive integer `s`, `m`, and `h` durations.
- Commands run from any exact line and disappear after Enter; invalid duration/syntax remains normal text.
- Use real wall-clock milliseconds, never accumulated QTimer ticks, to calculate elapsed time.
- Run `QT_QPA_PLATFORM=offscreen pytest -q` and `ruff check .` before each commit.

---

## File structure

| File | Responsibility |
| --- | --- |
| `src/lazynote/timer.py` | Pure command parser, immutable timer state, serialization, wall-clock transitions, and `MM:SS` formatting. |
| `tests/test_timer.py` | Unit tests for every accepted/rejected command and all state/time boundaries. |
| `src/lazynote/notifications.py` | Best-effort DBus notification with the `sound-name` hint; returns success/failure without leaking DBus errors. |
| `tests/test_notifications.py` | Unit tests for valid and unavailable DBus notification paths using fakes. |
| `src/lazynote/bridge.py` | Owns persistent live state, Qt refresh timer, QML properties, and `run_timer_command`. |
| `tests/test_bridge.py` | Backend persistence and property tests with a deterministic injected clock/notification callback. |
| `src/lazynote/qml/TimerOverlay.qml` | Compact overlay that binds to backend timer properties and does not consume editor clicks outside its own rectangle. |
| `src/lazynote/qml/Editor.qml` | Detects recognized timer lines on Enter, removes them, and preserves normal line splitting otherwise. |
| `src/lazynote/qml/Main.qml` | Hosts the overlay above `Editor`. |
| `tests/test_sanity.py` | Extends the offscreen engine smoke test to ensure `TimerOverlay.qml` loads. |

### Task 1: Pure command and state model

**Files:**
- Create: `src/lazynote/timer.py`
- Create: `tests/test_timer.py`

**Interfaces:**
- Produces `TimerCommand(kind: Literal["start", "pause", "resume"], duration_ms: int | None)`.
- Produces `TimerState(status: Literal["running", "paused", "done"], ends_at_ms: int | None, remaining_ms: int)`.
- Produces `parse_command(line: str) -> TimerCommand | None`, `start(duration_ms: int, now_ms: int) -> TimerState`, `pause(state: TimerState, now_ms: int) -> TimerState`, `resume(state: TimerState, now_ms: int) -> TimerState`, `refresh(state: TimerState, now_ms: int) -> TimerState`, `remaining_ms(state: TimerState, now_ms: int) -> int`, `format_remaining(milliseconds: int) -> str`, `encode_state(state: TimerState | None) -> str`, and `decode_state(value: str | None) -> TimerState | None`.

- [ ] **Step 1: Write failing parser and formatting tests**

```python
from lazynote import timer


def test_parse_start_commands():
    assert timer.parse_command("timer") == timer.TimerCommand("start", 25 * 60_000)
    assert timer.parse_command("timer 90s") == timer.TimerCommand("start", 90_000)
    assert timer.parse_command("timer 10m") == timer.TimerCommand("start", 600_000)
    assert timer.parse_command("timer 1h") == timer.TimerCommand("start", 3_600_000)


def test_parse_control_commands_and_rejects_non_commands():
    assert timer.parse_command("timer p") == timer.TimerCommand("pause", None)
    assert timer.parse_command("timer r") == timer.TimerCommand("resume", None)
    assert timer.parse_command(" timer") is None
    assert timer.parse_command("timer 0m") is None
    assert timer.parse_command("timer -1m") is None
    assert timer.parse_command("timer 1.5m") is None
    assert timer.parse_command("timer 2d") is None
    assert timer.parse_command("timer hello") is None


def test_format_remaining_rounds_up_to_the_next_visible_second():
    assert timer.format_remaining(0) == "00:00"
    assert timer.format_remaining(1) == "00:01"
    assert timer.format_remaining(60_000) == "01:00"
    assert timer.format_remaining(61_001) == "01:02"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_timer.py -v`

Expected: FAIL because `lazynote.timer` does not exist.

- [ ] **Step 3: Implement parser and formatting**

```python
@dataclass(frozen=True)
class TimerCommand:
    kind: Literal["start", "pause", "resume"]
    duration_ms: int | None = None


def parse_command(line: str) -> TimerCommand | None:
    if line == "timer":
        return TimerCommand("start", 25 * 60_000)
    if line == "timer p":
        return TimerCommand("pause")
    if line == "timer r":
        return TimerCommand("resume")
    match = re.fullmatch(r"timer ([1-9]\d*)([smh])", line)
    if match is None:
        return None
    amount, unit = match.groups()
    multiplier = {"s": 1_000, "m": 60_000, "h": 3_600_000}[unit]
    return TimerCommand("start", int(amount) * multiplier)


def format_remaining(milliseconds: int) -> str:
    seconds = max(0, math.ceil(milliseconds / 1_000))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
```

- [ ] **Step 4: Run parser tests**

Run: `pytest tests/test_timer.py -v`

Expected: PASS.

- [ ] **Step 5: Add failing state-transition and persistence tests**

```python
def test_pause_resume_and_refresh_use_wall_clock_time():
    running = timer.start(10_000, now_ms=1_000)
    assert timer.remaining_ms(running, now_ms=4_250) == 6_750
    paused = timer.pause(running, now_ms=4_250)
    assert paused == timer.TimerState("paused", None, 6_750)
    assert timer.remaining_ms(paused, now_ms=99_000) == 6_750
    resumed = timer.resume(paused, now_ms=99_000)
    assert resumed == timer.TimerState("running", 105_750, 6_750)
    assert timer.refresh(resumed, now_ms=105_750).status == "done"


def test_state_round_trip_and_invalid_saved_values():
    original = timer.TimerState("paused", None, 123_456)
    assert timer.decode_state(timer.encode_state(original)) == original
    assert timer.decode_state(None) is None
    assert timer.decode_state("not json") is None
    assert timer.decode_state('{"status":"running","ends_at_ms":null,"remaining_ms":1}') is None
```

- [ ] **Step 6: Implement transitions and JSON validation**

```python
@dataclass(frozen=True)
class TimerState:
    status: Literal["running", "paused", "done"]
    ends_at_ms: int | None
    remaining_ms: int


def start(duration_ms: int, now_ms: int) -> TimerState:
    return TimerState("running", now_ms + duration_ms, duration_ms)


def refresh(state: TimerState, now_ms: int) -> TimerState:
    if state.status != "running":
        return state
    left = max(0, (state.ends_at_ms or now_ms) - now_ms)
    if left == 0:
        return TimerState("done", None, 0)
    return TimerState("running", state.ends_at_ms, left)
```

Implement `pause` by calling `refresh`; retain `remaining_ms` in a paused state. Implement `resume` only for paused states; it returns other states unchanged. Encode exactly `status`, `ends_at_ms`, and `remaining_ms` with `json.dumps(..., separators=(",", ":"))`. Decode only dictionaries with a supported status, a non-negative integer `remaining_ms`, and an integer deadline for running states.

- [ ] **Step 7: Run pure-module tests and lint**

Run: `pytest tests/test_timer.py -v && ruff check src/lazynote/timer.py tests/test_timer.py`

Expected: PASS with no lint findings.

- [ ] **Step 8: Commit Task 1**

```bash
git add src/lazynote/timer.py tests/test_timer.py
git commit -m "feat: add pure timer command model"
```

### Task 2: Best-effort desktop notification adapter

**Files:**
- Create: `src/lazynote/notifications.py`
- Create: `tests/test_notifications.py`
- Modify: `packaging/lazynote.spec: Qt module imports collected by Analysis`

**Interfaces:**
- Consumes `PySide6.QtDBus.QDBusConnection` and `QDBusInterface`.
- Produces `notify_timer_finished() -> bool`; it returns `False` for unavailable/failed DBus and never raises.
- Later consumed by `Backend` as its default completion notifier.

- [ ] **Step 1: Write failing notification tests with a fake interface factory**

```python
from lazynote import notifications


class Reply:
    def __init__(self, valid: bool):
        self._valid = valid

    def isValid(self):
        return self._valid


class Interface:
    def __init__(self, valid=True, reply_valid=True):
        self.valid = valid
        self.reply_valid = reply_valid
        self.calls = []

    def isValid(self):
        return self.valid

    def call(self, method, *args):
        self.calls.append((method, args))
        return Reply(self.reply_valid)


def test_sends_freedesktop_notification_with_sound_hint():
    interface = Interface()
    assert notifications.notify_timer_finished(lambda: interface) is True
    method, args = interface.calls[0]
    assert method == "Notify"
    assert args[0] == "Lazynote"
    assert args[3] == "Timer finished"
    assert args[6]["sound-name"] == "complete"


def test_returns_false_when_notification_service_is_unavailable():
    assert notifications.notify_timer_finished(lambda: Interface(valid=False)) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_notifications.py -v`

Expected: FAIL because `lazynote.notifications` does not exist.

- [ ] **Step 3: Implement the DBus adapter**

```python
def _notification_interface() -> QDBusInterface:
    return QDBusInterface(
        "org.freedesktop.Notifications",
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications",
        QDBusConnection.sessionBus(),
    )


def notify_timer_finished(factory: Callable[[], QDBusInterface] = _notification_interface) -> bool:
    try:
        interface = factory()
        if not interface.isValid():
            return False
        reply = interface.call(
            "Notify",
            "Lazynote", 0, "", "Timer finished", "", [], {"sound-name": "complete"}, 10_000,
        )
        return reply.isValid()
    except Exception:
        return False
```

Import QtDBus directly in this module. In `packaging/lazynote.spec`, add `"PySide6.QtDBus"` to `hiddenimports` in the existing `Analysis(...)` call so the direct runtime import and its already-allowlisted `libQt6DBus.so.6` are retained in the bundled application.

- [ ] **Step 4: Run adapter tests and a packaging syntax check**

Run: `pytest tests/test_notifications.py -v && python -m py_compile src/lazynote/notifications.py packaging/lazynote.spec`

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/lazynote/notifications.py tests/test_notifications.py packaging/lazynote.spec
git commit -m "feat: notify when timer completes"
```

### Task 3: Backend controller, persistence, and QML API

**Files:**
- Modify: `src/lazynote/bridge.py: imports, Backend signals/properties, __init__, timer slots`
- Modify: `tests/test_bridge.py: backend timer tests`

**Interfaces:**
- Consumes `timer.TimerState`, `timer.parse_command`, state helpers, `notifications.notify_timer_finished`, and `store.get_settings()`.
- Produces QML properties `timerState: str`, `timerRemaining: int`, `timerDisplay: str`, and `timerVisible: bool`, all notified by `timerChanged`.
- Produces `@Slot(str, result=bool) run_timer_command(line: str)`, returning `True` only for recognized command syntax so QML knows to remove the line.

- [ ] **Step 1: Add failing backend tests using injected dependencies**

```python
def test_timer_command_persists_running_timer_and_exposes_properties(tmp_path, monkeypatch):
    now = [1_000]
    b = _make_backend(tmp_path, monkeypatch, clock_ms=lambda: now[0])
    assert b.run_timer_command("timer 10m") is True
    assert b.property("timerState") == "running"
    assert b.property("timerRemaining") == 600_000
    assert b.property("timerDisplay") == "10:00"
    assert b.property("timerVisible") is True
    assert store.get_settings().get("timer_state")


def test_timer_pause_resume_and_restart_restore(tmp_path, monkeypatch):
    now = [1_000]
    b = _make_backend(tmp_path, monkeypatch, clock_ms=lambda: now[0])
    b.run_timer_command("timer 10s")
    now[0] = 4_250
    b.refresh_timer()
    assert b.run_timer_command("timer p") is True
    assert b.property("timerState") == "paused"
    assert b.property("timerRemaining") == 6_750
    now[0] = 99_000
    restored = Backend(clock_ms=lambda: now[0])
    assert restored.property("timerState") == "paused"
    assert restored.property("timerRemaining") == 6_750
    assert restored.run_timer_command("timer r") is True
    assert restored.property("timerState") == "running"


def test_timer_completion_notifies_once_and_keeps_done_overlay(tmp_path, monkeypatch):
    now = [1_000]
    completed = []
    b = _make_backend(tmp_path, monkeypatch, clock_ms=lambda: now[0], notify=lambda: completed.append(True))
    b.run_timer_command("timer 1s")
    now[0] = 2_000
    b.refresh_timer()
    b.refresh_timer()
    assert completed == [True]
    assert b.property("timerState") == "done"
    assert b.property("timerDisplay") == "00:00"
```

Update `_make_backend` to accept `**kwargs` and pass them into `Backend(**kwargs)`. Import `store` and `Backend` at test-module scope only if that does not break its existing Qt setup; otherwise retain the helper’s imports and return both needed references through the existing module imports.

- [ ] **Step 2: Run backend timer tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_bridge.py -k timer -v`

Expected: FAIL because `Backend` has no timer constructor arguments, properties, or slots.

- [ ] **Step 3: Add backend controller state and properties**

Add these constructor dependencies while preserving the existing QML-compatible default call:

```python
def __init__(
    self,
    parent: QObject | None = None,
    *,
    clock_ms: Callable[[], int] = timer.now_ms,
    notify: Callable[[], bool] = notifications.notify_timer_finished,
) -> None:
```

Add `timerChanged = Signal()`. Create `self._timer_tick = QTimer(self)` with a 250 ms interval connected to `self.refresh_timer`; set `self._clock_ms`, `self._notify`, and `self._timer_state = timer.decode_state(store.get_settings().get("timer_state"))`. Immediately call `refresh_timer()` after loading saved state so an expired deadline becomes `done`.

Implement the properties exactly as:

```python
def _timer_state_name(self) -> str:
    return self._timer_state.status if self._timer_state is not None else "inactive"

timerState = Property(str, _timer_state_name, notify=timerChanged)

def _timer_remaining(self) -> int:
    return timer.remaining_ms(self._timer_state, self._clock_ms()) if self._timer_state else 0

timerRemaining = Property(int, _timer_remaining, notify=timerChanged)

timerDisplay = Property(str, lambda self: timer.format_remaining(self._timer_remaining()), notify=timerChanged)
timerVisible = Property(bool, lambda self: self._timer_state is not None, notify=timerChanged)
```

- [ ] **Step 4: Implement command, refresh, and persistence methods**

```python
@Slot(str, result=bool)
def run_timer_command(self, line: str) -> bool:
    command = timer.parse_command(line)
    if command is None:
        return False
    now = self._clock_ms()
    if command.kind == "start":
        self._timer_state = timer.start(command.duration_ms or 0, now)
    elif command.kind == "pause" and self._timer_state is not None:
        self._timer_state = timer.pause(self._timer_state, now)
    elif command.kind == "resume" and self._timer_state is not None:
        self._timer_state = timer.resume(self._timer_state, now)
    self._persist_timer()
    self._sync_timer_tick()
    self.timerChanged.emit()
    return True

@Slot()
def refresh_timer(self) -> None:
    if self._timer_state is None:
        return
    old_status = self._timer_state.status
    self._timer_state = timer.refresh(self._timer_state, self._clock_ms())
    if old_status != "done" and self._timer_state.status == "done":
        self._notify()
        self._persist_timer()
    self._sync_timer_tick()
    self.timerChanged.emit()
```

`_persist_timer` writes `timer.encode_state(self._timer_state)` under `timer_state`. `_sync_timer_tick` starts the 250 ms timer only while state is `running`, otherwise stops it. Add `@Slot() dismiss_timer` to set `_timer_state` to `None`, persist the encoded null state, stop ticking, and emit `timerChanged`. Ensure notification exceptions are swallowed by the adapter and do not affect state.

- [ ] **Step 5: Run backend timer tests, then all bridge tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_bridge.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/lazynote/bridge.py tests/test_bridge.py
git commit -m "feat: add persistent timer backend"
```

### Task 4: Overlay component and command-line consumption in the editor

**Files:**
- Create: `src/lazynote/qml/TimerOverlay.qml`
- Modify: `src/lazynote/qml/Main.qml: panel children after Editor`
- Modify: `src/lazynote/qml/Editor.qml: add timer-aware return handler`
- Modify: `tests/test_sanity.py: offscreen QML smoke test`

**Interfaces:**
- Consumes backend properties `timerVisible`, `timerState`, `timerDisplay` and `dismiss_timer()`.
- Consumes `backend.run_timer_command(line) -> bool`.
- Produces a compact overlay that only accepts pointer events inside its own dismiss button.

- [ ] **Step 1: Write a failing engine smoke test**

```python
def test_qml_engine_loads_timer_overlay(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from PySide6.QtWidgets import QApplication
    from lazynote import store
    from lazynote.app import create_engine

    monkeypatch.setattr(store, "_LEGACY_DB_PATHS", [])
    app = QApplication.instance() or QApplication([])
    engine = create_engine(app)
    assert engine.rootObjects()
```

Do not enter the Qt event loop. This verifies `Main.qml` can resolve the new local component and all backend bindings.

- [ ] **Step 2: Run smoke test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_sanity.py::test_qml_engine_loads_timer_overlay -v`

Expected: FAIL because `Main.qml` references a missing `TimerOverlay` component.

- [ ] **Step 3: Create `TimerOverlay.qml`**

Implement a local `Item` with `visible: backend && backend.timerVisible`, an implicit width around 136 px, and a height around 42 px. Anchor it to the editor’s top-right area from `Main.qml`, not full-screen. Use a rounded `Rectangle` with `backend.colors.bg` and a subtle border, then a monospaced `Text` bound to `backend.timerDisplay`. Add a smaller state label bound to `backend.timerState === "paused" ? "paused" : backend.timerState === "done" ? "done" : "running"`. Add only a 24×24 close `MouseArea` whose click calls `backend.dismiss_timer()`; do not add an overlay-wide `MouseArea`.

```qml
Item {
    id: root
    visible: backend && backend.timerVisible
    width: 136
    height: 42
    z: 20

    Rectangle { anchors.fill: parent; radius: 8; color: backend.colors.bg }
    Text { text: backend.timerDisplay; anchors.left: parent.left; anchors.leftMargin: 12 }
    MouseArea {
        anchors.right: parent.right
        width: 24; height: parent.height
        onClicked: backend.dismiss_timer()
    }
}
```

Use the project’s `backend.colors`, `backend.font.family`, and `backend.font.size` bindings rather than hard-coded theme colors.

- [ ] **Step 4: Host the overlay in `Main.qml`**

Immediately after the `Editor { id: editor ... }` block inside `panel`, add:

```qml
TimerOverlay {
    anchors.right: parent.right
    anchors.top: dragStrip.bottom
    anchors.rightMargin: 12
    anchors.topMargin: 8
}
```

This places it above the editor with `z: 20` from the component while leaving all non-button space click-through.

- [ ] **Step 5: Add an editor helper that consumes recognized timer commands**

Before `splitLine` in `Editor.qml`, add:

```javascript
function submitLineOrSplit(idx, col) {
    if (!backend.run_timer_command(lines[idx])) {
        splitLine(idx, col)
        return
    }
    var arr = lines.slice()
    arr.splice(idx, 1)
    if (arr.length === 0)
        arr = [""]
    lines = arr
    cursorLine = Math.min(idx, lines.length - 1)
    cursorCol = 0
    list.model = lines.length
    pushEdit()
    Qt.callLater(ensureEditor)
}
```

Replace both `root.splitLine(row.index, cursorPosition)` calls in `Keys.onReturnPressed` and `Keys.onEnterPressed` with `root.submitLineOrSplit(row.index, cursorPosition)`. The helper calls the backend before modifying `lines`, removes only recognized command lines, and preserves normal Enter behavior for invalid timer syntax and ordinary prose.

- [ ] **Step 6: Run QML smoke test and all tests**

Run: `QT_QPA_PLATFORM=offscreen pytest -q && ruff check .`

Expected: PASS. Manually run `lazynote`, type `timer` on a non-first line, press Enter, and confirm the line vanishes, the compact `25:00` overlay appears, and text outside the overlay remains editable.

- [ ] **Step 7: Commit Task 4**

```bash
git add src/lazynote/qml/TimerOverlay.qml src/lazynote/qml/Main.qml src/lazynote/qml/Editor.qml tests/test_sanity.py
git commit -m "feat: add in-note timer overlay"
```

### Task 5: End-to-end verification and documentation alignment

**Files:**
- Modify: `README.md: feature list and usage section`
- Modify: `docs/plans/2026-08-29-timer-design.md: only if implementation exposed a factual API correction`

**Interfaces:**
- Consumes completed timer command, backend, QML, and notification behavior.
- Produces user-facing command documentation matching the implemented syntax.

- [ ] **Step 1: Add the concise timer usage documentation**

Add this exact usage block near existing user-facing feature documentation:

```markdown
### Timer

Type a timer command on any line, then press Enter. Lazynote removes the command
line and shows one compact countdown over the note:

- `timer` starts 25 minutes.
- `timer 10m`, `timer 90s`, and `timer 1h` start custom countdowns.
- `timer p` pauses the active timer.
- `timer r` resumes the paused timer.

Only one timer runs at a time. It continues while the app is hidden or restarted
and sends a desktop notification when it finishes.
```

- [ ] **Step 2: Run the full automated verification suite**

Run: `QT_QPA_PLATFORM=offscreen pytest -q && ruff check .`

Expected: PASS.

- [ ] **Step 3: Run the application smoke test**

Run: `QT_QPA_PLATFORM=offscreen timeout 5 python -m lazynote`

Expected: process stays running until `timeout` stops it; no QML component, binding, or Python traceback appears.

- [ ] **Step 4: Perform manual desktop acceptance checks**

Run: `lazynote`

Verify each case:

1. Type ordinary text `timer 0m`, press Enter, and confirm it remains text and splits the line normally.
2. Type `timer` in the middle of a note, press Enter, and confirm its line is removed and `25:00` appears.
3. Type `timer p`, press Enter, wait five seconds, and confirm the shown value does not change.
4. Type `timer r`, press Enter, wait two seconds, and confirm the value decreases.
5. Hide Lazynote, reopen it, and confirm the same countdown reflects elapsed wall time.
6. Quit and reopen Lazynote during a running timer, and confirm it restores at the elapsed value.
7. Start `timer 1s` and confirm the overlay changes to `Done` and the desktop receives a notification with sound where the notification daemon supports the `sound-name` hint.
8. Start a second timer while one is paused or running and confirm the second replaces the first.

- [ ] **Step 5: Commit Task 5**

```bash
git add README.md docs/plans/2026-08-29-timer-design.md
git commit -m "docs: document timer commands"
```

## Self-review

- **Spec coverage:** Task 1 covers all command forms, custom durations, invalid syntax, and wall-clock calculations. Task 3 persists a single timer through pause, resume, hide/restart, and completion. Task 2 provides desktop notification with a sound hint and a safe failure path. Task 4 removes recognized lines from any position and renders a compact click-through overlay. Task 5 validates and documents all user-visible behavior.
- **Placeholder scan:** No deferred implementation markers or generic testing instructions remain; each task names exact files, interfaces, tests, commands, and state behavior.
- **Type consistency:** `TimerCommand`, `TimerState`, `run_timer_command`, `refresh_timer`, `timerState`, `timerRemaining`, `timerDisplay`, `timerVisible`, and `dismiss_timer` retain the same names and signatures across tasks.
