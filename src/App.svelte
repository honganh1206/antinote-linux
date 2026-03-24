<script lang="ts">
  import { onMount } from "svelte";
  import { getCurrentWindow } from "@tauri-apps/api/window";
  import {
    loadNotes,
    getContent,
    setContent,
    getCurrentIndex,
    noteCount,
    scheduleSave,
    flushSave,
    navigatePrev,
    navigateNext,
    addNote,
    removeCurrentNote,
  } from "./lib/noteState.svelte";
  import { getSetting, setSetting } from "./lib/db";
  import {
    restoreWindowGeometry,
    trackWindowGeometry,
  } from "./lib/windowState";
  import { getActiveMode } from "./lib/keywords.svelte";
  import TodoOverlay from "./TodoOverlay.svelte";
  import PlainOverlay from "./PlainOverlay.svelte";
  import SlashPicker from "./SlashPicker.svelte";
  import { listen } from "@tauri-apps/api/event";

  let textareaEl: HTMLTextAreaElement;
  let overlayEl: HTMLDivElement;
  let showSlashPicker = $state(false);
  let cursorLine = $state(0);

  function updateCursorLine() {
    if (!textareaEl) return;
    const pos = textareaEl.selectionStart;
    const textBefore = getContent().slice(0, pos);
    cursorLine = textBefore.split("\n").length - 1;
  }

  function handleScroll() {
    if (overlayEl) {
      overlayEl.scrollTop = textareaEl.scrollTop;
    }
  }

  function checkSlashPicker() {
    const content = getContent();
    const firstLine = content.split("\n")[0];
    showSlashPicker = firstLine === "/" && textareaEl.selectionStart <= 1;
  }

  function handleSlashSelect(keyword: string) {
    const content = getContent();
    const newlineIdx = content.indexOf("\n");
    const rest = newlineIdx !== -1 ? content.slice(newlineIdx) : "";
    setContent(keyword + rest);
    showSlashPicker = false;
    textareaEl.value = getContent();
    const pos = keyword.length;
    textareaEl.setSelectionRange(pos, pos);
    textareaEl.focus();
    scheduleSave();
  }

  function handleSlashDismiss() {
    showSlashPicker = false;
    textareaEl.focus();
  }

  function handleInput() {
    setContent(textareaEl.value);
    scheduleSave();
    checkSlashPicker();
    updateCursorLine();
  }

  function handlePaste(event: ClipboardEvent) {
    event.preventDefault();
    const text = event.clipboardData?.getData("text/plain") ?? "";
    const el = event.target as HTMLTextAreaElement;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const current = getContent();
    setContent(current.slice(0, start) + text + current.slice(end));

    const newPos = start + text.length;
    requestAnimationFrame(() => {
      el.setSelectionRange(newPos, newPos);
    });
    scheduleSave();
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.ctrlKey && event.key === "h") {
      event.preventDefault();
      navigatePrev();
    } else if (event.ctrlKey && event.key === "l") {
      event.preventDefault();
      navigateNext();
    } else if (event.ctrlKey && event.key === "n") {
      event.preventDefault();
      addNote();
    } else if (event.ctrlKey && event.key === "d") {
      event.preventDefault();
      handleDelete();
    }
  }

  async function handleDelete() {
    const current = getContent();
    if (current.trim().length > 0) {
      if (!confirm("Delete this note?")) return;
    }
    await removeCurrentNote();
  }

  function focusEditor() {
    textareaEl?.focus();
  }

  onMount(() => {
    // restoreWindowGeometry may fail if the DB isn't ready yet (e.g., first launch,
    // migration in progress). Errors are silently caught so loadNotes always runs.
    restoreWindowGeometry().catch(() => {});
    loadNotes().then(() => focusEditor());

    const appWindow = getCurrentWindow();

    let alwaysOnTop = true;
    getSetting("always_on_top").then((val) => {
      alwaysOnTop = val !== "false";
      appWindow.setAlwaysOnTop(alwaysOnTop);
    });

    let autoHideOnBlur = false;
    getSetting("auto_hide_on_blur").then((val) => {
      autoHideOnBlur = val === "true";
    });

    let autoHideTimer: ReturnType<typeof setTimeout> | null = null;

    const unlistenGeometry = trackWindowGeometry();

    const unlistenNewNote = listen("tray-new-note", () => {
      addNote().then(() => focusEditor());
    });

    const unlistenToggleAoT = listen("tray-toggle-always-on-top", () => {
      alwaysOnTop = !alwaysOnTop;
      appWindow.setAlwaysOnTop(alwaysOnTop);
      setSetting("always_on_top", alwaysOnTop ? "true" : "false");
    });

    const unlistenToggleAutoHide = listen("tray-toggle-auto-hide", () => {
      autoHideOnBlur = !autoHideOnBlur;
      setSetting("auto_hide_on_blur", autoHideOnBlur ? "true" : "false");
    });

    const unlistenQuit = listen("tray-quit", () => {
      flushSave();
    });

    const unlistenClose = appWindow.onCloseRequested(async (event) => {
      event.preventDefault();
      await flushSave();
      appWindow.destroy();
    });

    const unlistenFocus = appWindow.onFocusChanged(({ payload: focused }) => {
      if (focused) {
        if (autoHideTimer) {
          clearTimeout(autoHideTimer);
          autoHideTimer = null;
        }
        focusEditor();
      } else {
        flushSave();
        if (autoHideOnBlur) {
          autoHideTimer = setTimeout(() => {
            autoHideTimer = null;
            appWindow.hide();
          }, 300);
        }
      }
    });

    return () => {
      flushSave();
      if (autoHideTimer) clearTimeout(autoHideTimer);
      unlistenGeometry.then((unlisten) => unlisten());
      unlistenFocus.then((unlisten) => unlisten());
      unlistenNewNote.then((unlisten) => unlisten());
      unlistenToggleAoT.then((unlisten) => unlisten());
      unlistenToggleAutoHide.then((unlisten) => unlisten());
      unlistenQuit.then((unlisten) => unlisten());
      unlistenClose.then((unlisten) => unlisten());
    };
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<main>
  <div class="drag-region" data-tauri-drag-region></div>
  <div class="editor-wrapper">
    <textarea
      bind:this={textareaEl}
      class="overlay-active"
      value={getContent()}
      oninput={handleInput}
      onpaste={handlePaste}
      onscroll={handleScroll}
      onclick={updateCursorLine}
      onkeyup={updateCursorLine}
      placeholder="Start typing..."
      spellcheck="false"
      autocomplete="off"
    ></textarea>
    {#if getActiveMode() === "todo"}
      <TodoOverlay bind:overlayEl {cursorLine} />
    {:else}
      <PlainOverlay bind:overlayEl />
    {/if}
    {#if showSlashPicker}
      <SlashPicker
        onselect={handleSlashSelect}
        ondismiss={handleSlashDismiss}
      />
    {/if}
  </div>

  <span class="position"
    >{#if getActiveMode()}{getActiveMode()} ·
    {/if}{getCurrentIndex() + 1}/{noteCount()}</span
  >
</main>

<style>
  :global(*) {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  :global(html),
  :global(body),
  :global(#app) {
    background: transparent;
    overflow: hidden;
    height: 100%;
  }

  :global(body) {
    font-family:
      system-ui,
      -apple-system,
      sans-serif;
    color: #2c2c2c;
  }

  main {
    position: relative;
    display: flex;
    flex-direction: column;
    height: 100%;
    background-color: #faf8f5;
    border-radius: 10px;
    overflow: hidden;
  }

  .drag-region {
    height: 16px;
    flex-shrink: 0;
    cursor: grab;
  }

  .editor-wrapper {
    position: relative;
    flex: 1;
    overflow: auto;
  }

  textarea {
    width: 100%;
    height: 100%;
    border: none;
    outline: none;
    resize: none;
    background: transparent;
    font-family: inherit;
    font-size: 15px;
    line-height: 1.7;
    color: #2c2c2c;
    padding: 0.75rem 1.25rem 0.75rem calc(1.75rem + 1.2em);
  }

  textarea.overlay-active {
    color: transparent;
    caret-color: #2c2c2c;
  }

  textarea::placeholder {
    color: #b0a99f;
  }

  .position {
    position: absolute;
    bottom: 8px;
    right: 12px;
    font-size: 11px;
    color: #b0a99f;
    user-select: none;
    pointer-events: none;
  }
</style>
