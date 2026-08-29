# Timer Commands and Overlay — Design

Date: 2026-08-29

## Goal

Let a user start and control one persistent countdown from any line in a note.
The command disappears after execution and a compact overlay displays the active
timer without preventing note editing.

## Commands

A completed line is a timer command when it exactly matches one of these forms:

- `timer` — start a 25-minute countdown.
- `timer 10m` — start a custom duration. Accept positive integer seconds (`s`),
  minutes (`m`), or hours (`h`), for example `timer 90s` and `timer 1h`.
- `timer p` — pause the active timer.
- `timer r` — resume the active timer.

Commands work on every line, not only the first line. On Enter, the editor asks
the backend whether the just-completed line is a timer command. If it is, the
editor removes that whole line and shows the command result. A non-command or
invalid duration remains ordinary note text.

There is one active timer. Starting a new countdown replaces the previous
active or paused timer.

## UI and completion

`TimerOverlay.qml` is a compact, non-modal overlay above the editor. It shows
remaining time as `MM:SS`, state (running or paused), and a dismiss control.
It must not block editing outside its own bounds. The command interface is the
only required control mechanism in v1; `timer p` pauses and `timer r` resumes.

At zero, the overlay displays `Done`. Lazynote sends a desktop notification
that requests sound. If native desktop notifications are unavailable, the
completed overlay remains as the safe fallback.

## State and persistence

A running timer stores a wall-clock end timestamp. A paused timer stores its
remaining milliseconds. State is saved immediately in `app_settings` whenever
a timer starts, pauses, resumes, is dismissed, or completes. Restoring the app
recomputes remaining time from the wall clock, so countdowns continue accurately
while Lazynote is hidden or not running.

## Architecture

- `src/lazynote/timer.py`: pure command parsing, validation, state transitions,
  remaining-time calculation, and display formatting. It imports no PySide6.
- `src/lazynote/bridge.py`: owns a Qt timer/controller, exposes timer properties
  and command slots to QML, persists state, and sends completion notifications.
- `src/lazynote/notifications.py`: invokes the standard `notify-send` client
  with a desktop sound hint; failures are non-fatal.
- `src/lazynote/qml/Editor.qml`: detects Enter after a completed line, calls the
  backend, and removes a recognized command line.
- `src/lazynote/qml/TimerOverlay.qml`: renders the compact timer state.
- `src/lazynote/qml/Main.qml`: hosts the overlay above the editor.

The Qt controller may refresh UI roughly four times per second, but never uses
tick count as the time source. It calculates remaining time from persisted
state and the current wall clock.

## Error handling

Invalid timer syntax or zero/negative durations are left in the editor as
normal text. A syntactically valid pause or resume command is removed even when
there is no applicable active timer; it is otherwise harmless. Notification
failures cannot stop or corrupt timer state.

## Verification

- Unit-test every accepted and rejected command form, duration conversion,
  formatting, pause/resume, replacement, completion, and restart calculations.
- Backend tests cover persistence and command effects.
- An offscreen QML smoke test confirms the main scene loads with the overlay.
- Manually verify desktop notification plus sound on a supported Linux desktop.
