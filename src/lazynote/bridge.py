"""Backend QObject exposed to QML.

Wraps NoteState + a debounced autosave QTimer, and exposes settings / open-url.
QML reads `content`/`index`/`count`/`mode` properties and calls the slots.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable

from PySide6.QtCore import (
    Property, Qt, QObject, QTimer, QUrl, Signal, Slot,
    QBuffer, QIODevice,
)
from PySide6.QtGui import QDesktopServices, QFontDatabase, QFontInfo, QGuiApplication, QImage

from lazynote import fonts, notifications, obsidian, ocr, store, theme, timer
from lazynote.editormodel import line_render_spans
from lazynote.geometry import Geometry, is_on_screen, parse_geometry
from lazynote.notestate import NoteState
from lazynote.parse.links import link_occurrence_by_offset
from lazynote.parse.mode import REGISTERED_KEYWORDS, detect_mode

SAVE_DEBOUNCE_MS = 500


class Backend(QObject):
    contentChanged = Signal()
    statusChanged = Signal()
    autoHideChanged = Signal(bool)
    toggleWindowRequested = Signal()
    themeChanged = Signal()
    fontChanged = Signal()
    linkSettingsChanged = Signal()
    ocrComplete = Signal(str)        # recognized text
    ocrStatus = Signal(str, bool)    # (message, isError)
    timerChanged = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        clock_ms: Callable[[], int] = timer.now_ms,
        notify: Callable[[], object] = notifications.notify_timer_finished,
    ) -> None:
        super().__init__(parent)
        self._mono_cache: list[str] | None = None
        self._state = NoteState(store.get_notes(), store.get_settings())
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._state.save_current)

        self._clock_ms = clock_ms
        self._notify = notify
        self._timer_state = timer.decode_state(store.get_settings().get("timer_state"))
        self._timer_tick = QTimer(self)
        self._timer_tick.setInterval(250)
        self._timer_tick.timeout.connect(self.refresh_timer)
        self.refresh_timer()

        # Per-note expanded-link state (session-only). URLs in this set render
        # full-length even when auto-shortening is on. Keyed by URL value.
        self._expanded_urls: set[str] = set()

        hints = QGuiApplication.styleHints()
        if hints is not None:
            hints.colorSchemeChanged.connect(self._on_os_scheme_changed)

    # ---- theme ----
    def _os_scheme(self) -> str:
        hints = QGuiApplication.styleHints()
        if hints is None:
            return "dark"
        return "light" if hints.colorScheme() == Qt.ColorScheme.Light else "dark"

    def _theme_mode(self) -> str:
        m = store.get_settings().get("theme")
        return m if m in ("system", "light", "dark") else "system"

    def _on_os_scheme_changed(self, _scheme) -> None:
        # Only the system-following mode cares about live OS changes.
        if self._theme_mode() == "system":
            self.themeChanged.emit()
            self.contentChanged.emit()

    def _theme(self) -> str:
        return self._theme_mode()

    theme = Property(str, _theme, notify=themeChanged)

    def _effective_scheme(self) -> str:
        return theme.resolve_scheme(self._theme_mode(), self._os_scheme())

    effectiveScheme = Property(str, _effective_scheme, notify=themeChanged)

    def _colors(self) -> dict:
        return theme.palette_for(self._theme_mode(), self._os_scheme())

    colors = Property("QVariantMap", _colors, notify=themeChanged)

    @Slot(str)
    def set_theme(self, mode: str) -> None:
        if mode not in ("system", "light", "dark"):
            return
        store.get_settings().set("theme", mode)
        self.themeChanged.emit()
        self.contentChanged.emit()

    @Slot()
    def toggle_theme(self) -> None:
        """Flip light ↔ dark based on the currently effective scheme.

        Switches to the opposite of whatever the user is effectively seeing, so
        the toggle works from "system" mode too (it picks an explicit override).
        """
        new = "light" if self._effective_scheme() == "dark" else "dark"
        store.get_settings().set("theme", new)
        self.themeChanged.emit()
        self.contentChanged.emit()

    # ---- font ----
    def _default_family(self) -> str:
        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        resolved = QFontInfo(fixed).family()
        mono = self.mono_families()
        if resolved in mono:
            return resolved
        return mono[0] if mono else resolved

    @Slot(result="QStringList")
    def mono_families(self) -> list[str]:
        if self._mono_cache is None:
            mono = sorted(
                f for f in QFontDatabase.families() if QFontDatabase.isFixedPitch(f)
            )
            self._mono_cache = mono if mono else sorted(QFontDatabase.families())
        return self._mono_cache

    def _font(self) -> dict:
        s = store.get_settings()
        return fonts.resolve_font(
            s.get("font_family") or "",
            s.get("font_size"),
            self.mono_families(),
            self._default_family(),
        )

    font = Property("QVariantMap", _font, notify=fontChanged)

    @Slot(str, int)
    def set_font(self, family: str, size: int) -> None:
        s = store.get_settings()
        if family:
            s.set("font_family", family)
        s.set("font_size", str(fonts.clamp_size(size)))
        self.fontChanged.emit()

    # ---- properties ----
    def _content(self) -> str:
        return self._state.content

    content = Property(str, _content, notify=contentChanged)

    def _index(self) -> int:
        return self._state.index

    index = Property(int, _index, notify=statusChanged)

    def _count(self) -> int:
        return self._state.count()

    count = Property(int, _count, notify=statusChanged)

    def _mode(self) -> str:
        m = detect_mode(self._state.content)
        return m["keyword"] if m else ""

    mode = Property(str, _mode, notify=contentChanged)

    def _keywords(self) -> list:
        return list(REGISTERED_KEYWORDS)

    keywords = Property("QStringList", _keywords, constant=True)

    # ---- timer ----
    def _timer_state_name(self) -> str:
        return self._timer_state.status if self._timer_state is not None else "inactive"

    timerState = Property(str, _timer_state_name, notify=timerChanged)

    def _timer_remaining(self) -> int:
        if self._timer_state is None:
            return 0
        return timer.remaining_ms(self._timer_state, self._clock_ms())

    timerRemaining = Property(int, _timer_remaining, notify=timerChanged)

    def _timer_elapsed(self) -> int:
        if self._timer_state is None:
            return 0
        return timer.elapsed_ms(self._timer_state, self._clock_ms())

    timerElapsed = Property(int, _timer_elapsed, notify=timerChanged)

    def _timer_total(self) -> int:
        if self._timer_state is None:
            return 0
        return timer.total_duration_ms(self._timer_state)

    timerTotal = Property(int, _timer_total, notify=timerChanged)

    def _timer_display(self) -> str:
        return timer.format_remaining(self._timer_remaining())

    timerDisplay = Property(str, _timer_display, notify=timerChanged)

    def _timer_visible(self) -> bool:
        return self._timer_state is not None

    timerVisible = Property(bool, _timer_visible, notify=timerChanged)

    def _persist_timer(self) -> None:
        store.get_settings().set("timer_state", timer.encode_state(self._timer_state))

    def _sync_timer_tick(self) -> None:
        if self._timer_state is not None and self._timer_state.status == "running":
            self._timer_tick.start()
        else:
            self._timer_tick.stop()

    @Slot(str, result=bool)
    def run_timer_command(self, line: str) -> bool:
        """Run a recognized timer command and report whether QML should remove it."""
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
        """Refresh the visible countdown from wall-clock time."""
        if self._timer_state is None:
            return
        old_status = self._timer_state.status
        self._timer_state = timer.refresh(self._timer_state, self._clock_ms())
        if old_status != "done" and self._timer_state.status == "done":
            self._notify()
            self._persist_timer()
        self._sync_timer_tick()
        self.timerChanged.emit()

    @Slot()
    def dismiss_timer(self) -> None:
        self._timer_state = None
        self._persist_timer()
        self._sync_timer_tick()
        self.timerChanged.emit()

    # ---- slots ----
    @Slot()
    def load(self) -> None:
        self._state.load()
        self.contentChanged.emit()
        self.statusChanged.emit()

    @Slot(str)
    def edit(self, text: str) -> None:
        self._state.set_content(text)
        self.contentChanged.emit()
        self._save_timer.start()

    @Slot()
    def flush(self) -> None:
        self._save_timer.stop()
        self._state.save_current()

    @Slot(int)
    def navigate(self, delta: int) -> None:
        if self._state.navigate(delta):
            self.contentChanged.emit()
            self.statusChanged.emit()

    @Slot()
    def new_note(self) -> None:
        self._state.add()
        self.contentChanged.emit()
        self.statusChanged.emit()

    @Slot()
    def delete_current(self) -> None:
        self._state.remove_current()
        self.contentChanged.emit()
        self.statusChanged.emit()

    @Slot(str)
    def slash_select(self, keyword: str) -> None:
        c = self._state.content
        nl = c.find("\n")
        rest = c[nl:] if nl != -1 else ""
        self._state.set_content(keyword + rest)
        self.contentChanged.emit()
        self._save_timer.start()

    @Slot(str, result=str)
    def setting_get(self, key: str) -> str:
        v = store.get_settings().get(key)
        return v if v is not None else ""

    @Slot(str, str)
    def setting_set(self, key: str, value: str) -> None:
        store.get_settings().set(key, value)
        if key in ("link_shortening", "hyperlink_features"):
            self.linkSettingsChanged.emit()

    @Slot(int, int, int, int)
    def save_geometry(self, x: int, y: int, w: int, h: int) -> None:
        store.get_settings().set(
            "window_geometry", json.dumps({"x": x, "y": y, "width": w, "height": h})
        )

    @Slot(result="QVariantList")
    def restore_geometry(self) -> list:
        """Return [x, y, w, h] if a saved geometry is still on a connected screen, else []."""
        g = parse_geometry(store.get_settings().get("window_geometry"))
        if g is None:
            return []
        for screen in QGuiApplication.screens():
            r = screen.availableGeometry()
            if is_on_screen(g, Geometry(r.x(), r.y(), r.width(), r.height())):
                return [g.x, g.y, g.width, g.height]
        return []

    @Slot(result=bool)
    def auto_hide_enabled(self) -> bool:
        return store.get_settings().get("auto_hide_on_blur") == "true"

    @Slot(result=bool)
    def toggle_auto_hide(self) -> bool:
        nxt = not self.auto_hide_enabled()
        store.get_settings().set("auto_hide_on_blur", "true" if nxt else "false")
        self.autoHideChanged.emit(nxt)
        return nxt

    @Slot(str)
    def open_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    @Slot()
    def export_obsidian(self) -> None:
        """Export the current note as a new note in the user's last-focused Obsidian vault.

        Flushes any pending edit so the exported body matches what's on screen, then
        opens an `obsidian://new?name=...&content=...` URI. Obsidian creates the note
        in its default new-note location of that vault.
        """
        self.flush()
        name = obsidian.derive_note_name(self._state.content)
        url = obsidian.build_new_note_url(name, self._state.content)
        QDesktopServices.openUrl(QUrl(url))

    @Slot()
    def request_toggle(self) -> None:
        # Called from the global-shortcut thread (queued onto the GUI thread).
        self.toggleWindowRequested.emit()

    # ---- editor ----
    @Slot(int, int, result="QVariantMap")
    def line_render(self, line: int, cursor_line: int) -> dict:
        """Per-line render data for the bespoke editor: styled spans + checkbox.

        Returns {"text": raw line text, "checkbox": ""|"checked"|"unchecked",
                 "spans": [{text,color,italic,strike,hidden,link,url}, ...]}.

        Links are shortened on non-cursor lines per the `link_shortening` setting
        and the per-note expand set; `span.url` carries the full URL so click/copy
        use the stored truth. `hyperlink_features=False` suppresses links entirely.
        """
        settings = store.get_settings()
        hyperlink_features = settings.get("hyperlink_features") != "false"
        shorten = hyperlink_features and settings.get("link_shortening") != "false"
        content = self._state.content
        occ = link_occurrence_by_offset(content) if shorten else {}
        pal = theme.palette_for(self._theme_mode(), self._os_scheme())
        lr = line_render_spans(
            content,
            line,
            cursor_line,
            palette=pal,
            shorten=shorten,
            expand_set=self._expanded_urls,
            occurrence_by_offset=occ,
            hyperlink_features=hyperlink_features,
        )
        lines = content.split("\n")
        raw = lines[line] if 0 <= line < len(lines) else ""
        return {
            "text": raw,
            "checkbox": lr.checkbox or "",
            "spans": [
                {
                    "text": s.text,
                    "color": s.color,
                    "italic": s.italic,
                    "strike": s.strike,
                    "hidden": s.hidden,
                    "link": s.link,
                    "url": s.url,
                }
                for s in lr.spans
            ],
        }

    @Slot(str)
    def toggle_link_expand(self, url: str) -> None:
        """Toggle a URL's membership in the per-note expanded set, then re-render.

        When a URL is expanded it renders full-length regardless of the
        auto-shortening setting. Toggling again re-shortens it.
        """
        if not url:
            return
        if url in self._expanded_urls:
            self._expanded_urls.discard(url)
        else:
            self._expanded_urls.add(url)
        self.contentChanged.emit()

    @Slot(int)
    def toggle_checkbox(self, line: int) -> None:
        """Toggle the trailing /x on a todo checklist line, then re-emit content."""
        lines = self._state.content.split("\n")
        if not (0 <= line < len(lines)):
            return
        text = lines[line]
        # Only meaningful for non-heading, non-comment, non-empty todo items.
        if text.strip() == "" or text.startswith("#") or text.startswith("//"):
            return
        lines[line] = text[:-2] if text.endswith("/x") else text + "/x"
        self.edit("\n".join(lines))

    # ---- clipboard OCR ----
    @Slot(result=str)
    def paste_or_ocr(self) -> str:
        """Ctrl+V handler. Returns text to paste now, or "" to wait for OCR.

        - clipboard has an image → "", starts async OCR; result via ocrComplete.
        - clipboard has text → returns it; QML pastes immediately.
        - empty clipboard → "".
        """
        cb = QGuiApplication.clipboard()
        img = cb.image()
        if not img.isNull():
            self.ocrStatus.emit("Recognizing…", False)
            self._start_ocr(img)
            return ""
        return cb.text()

    def _start_ocr(self, image: QImage) -> None:
        """Encode the image to PNG on the GUI thread, then OCR on a worker."""
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        image.save(buf, "PNG")
        png = bytes(buf.data())
        lang = store.get_settings().get("ocr_lang") or "eng"
        t = threading.Thread(target=self._ocr_worker, args=(png, lang), daemon=True)
        t.start()

    def _ocr_worker(self, png: bytes, lang: str) -> None:
        """Runs on a daemon thread; emits signals delivered to the GUI thread."""
        try:
            text = ocr.run_ocr(png, lang=lang)
        except ocr.OcrUnavailable:
            self.ocrStatus.emit(
                "OCR needs tesseract: sudo apt install tesseract-ocr", True
            )
            return
        except ocr.OcrFailed as e:
            self.ocrStatus.emit(f"OCR failed: {e}", True)
            return
        except Exception as e:
            self.ocrStatus.emit(f"OCR failed: {e}", True)
            return
        if not text:
            self.ocrStatus.emit("No text recognized", True)
            return
        self.ocrComplete.emit(text)
