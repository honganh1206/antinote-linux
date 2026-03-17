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
    if (event.ctrlKey && event.key === "PageUp") {
      event.preventDefault();
      navigatePrev();
    } else if (event.ctrlKey && event.key === "PageDown") {
      event.preventDefault();
      navigateNext();
    } else if (event.ctrlKey && event.key === "n") {
      event.preventDefault();
      addNote();
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
    const unlistenFocus = appWindow.onFocusChanged(
      ({ payload: focused }) => {
        if (focused) {
          focusEditor();
        } else {
          flushSave();
        }
      }
    );

    return () => {
      flushSave();
      unlistenFocus.then((unlisten) => unlisten());
    };
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<main>
  <nav>
    <div class="nav-left">
      <button
        onclick={navigatePrev}
        disabled={getCurrentIndex() === 0}
        title="Previous note (Ctrl+PageUp)"
      >
        ‹
      </button>
      <span class="position">{getCurrentIndex() + 1} / {noteCount()}</span>
      <button
        onclick={navigateNext}
        disabled={getCurrentIndex() >= noteCount() - 1}
        title="Next note (Ctrl+PageDown)"
      >
        ›
      </button>
    </div>
    <div class="nav-right">
      <button onclick={addNote} title="New note (Ctrl+N)">+</button>
      <button onclick={handleDelete} class="delete" title="Delete note">×</button>
    </div>
  </nav>

  <textarea
    bind:this={textareaEl}
    value={getContent()}
    oninput={handleInput}
    onpaste={handlePaste}
    placeholder="Start typing..."
    spellcheck="false"
    autocomplete="off"
  ></textarea>
</main>

<style>
  :global(*) {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  :global(body) {
    font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
    background-color: #faf8f5;
    color: #2c2c2c;
    overflow: hidden;
  }

  main {
    display: flex;
    flex-direction: column;
    height: 100vh;
  }

  nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.4rem 0.75rem;
    border-bottom: 1px solid #e8e4df;
    user-select: none;
    flex-shrink: 0;
  }

  .nav-left, .nav-right {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .position {
    font-size: 12px;
    color: #999;
    min-width: 3rem;
    text-align: center;
  }

  nav button {
    background: none;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    font-size: 18px;
    color: #888;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }

  nav button:hover:not(:disabled) {
    background: #eee8e2;
    color: #555;
  }

  nav button:disabled {
    opacity: 0.3;
    cursor: default;
  }

  nav button.delete:hover:not(:disabled) {
    background: #fde8e8;
    color: #c44;
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
</style>
