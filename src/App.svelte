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
  import { listen } from "@tauri-apps/api/event";

  let textareaEl: HTMLTextAreaElement;

  function handleInput() {
    setContent(textareaEl.value);
    scheduleSave();
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
    loadNotes().then(() => focusEditor());

    const appWindow = getCurrentWindow();

    let alwaysOnTop = true;
    getSetting("always_on_top").then((val) => {
      alwaysOnTop = val !== "false";
      appWindow.setAlwaysOnTop(alwaysOnTop);
    });

    const unlistenNewNote = listen("tray-new-note", () => {
      addNote().then(() => focusEditor());
    });

    const unlistenToggleAoT = listen("tray-toggle-always-on-top", () => {
      alwaysOnTop = !alwaysOnTop;
      appWindow.setAlwaysOnTop(alwaysOnTop);
      setSetting("always_on_top", alwaysOnTop ? "true" : "false");
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
        focusEditor();
      } else {
        flushSave();
      }
    });

    return () => {
      flushSave();
      unlistenFocus.then((unlisten) => unlisten());
      unlistenNewNote.then((unlisten) => unlisten());
      unlistenToggleAoT.then((unlisten) => unlisten());
      unlistenQuit.then((unlisten) => unlisten());
      unlistenClose.then((unlisten) => unlisten());
    };
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<main>
  <div class="drag-region" data-tauri-drag-region></div>
  <textarea
    bind:this={textareaEl}
    value={getContent()}
    oninput={handleInput}
    onpaste={handlePaste}
    placeholder="Start typing..."
    spellcheck="false"
    autocomplete="off"
  ></textarea>

  <span class="position">{getCurrentIndex() + 1}/{noteCount()}</span>
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

  textarea {
    flex: 1;
    width: 100%;
    border: none;
    outline: none;
    resize: none;
    background: transparent;
    font-family: inherit;
    font-size: 15px;
    line-height: 1.7;
    color: #2c2c2c;
    padding: 0.75rem 1.25rem;
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
