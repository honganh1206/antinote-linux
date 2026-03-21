<script lang="ts">
  import { getContent } from "./lib/noteState.svelte";
  import { getKeywordTitle } from "./lib/keywords.svelte";
  import { parseTodoLines } from "./lib/keywords/todo";

  let {
    overlayEl = $bindable(),
    cursorLine = 0,
  }: { overlayEl?: HTMLDivElement; cursorLine?: number } = $props();

  const content = $derived(getContent());
  const keywordLine = $derived(content.split("\n")[0]);
  const lines = $derived(parseTodoLines(content));
  const title = $derived(getKeywordTitle());
  // cursorLine is 0-indexed from full content; overlay starts at line 1
  const cursorOverlayIndex = $derived(cursorLine - 1);
</script>

<div class="todo-overlay" bind:this={overlayEl}>
  <div class="line keyword-line">{keywordLine}</div>
  {#each lines as line, i}
    {#if line.type === "empty"}
      <div class="line">&nbsp;</div>
    {:else if line.type === "heading"}
      <div class="line heading h{line.headingLevel}">{line.text}</div>
    {:else if line.type === "comment"}
      <div class="line comment">{line.text}</div>
    {:else if line.type === "checklist-item-checked" && i !== cursorOverlayIndex}
      <div class="line checked">
        <span class="checkbox">&#9745 </span><s>{line.text}</s>
      </div>
    {:else if line.type === "checklist-item-checked"}
      <div class="line"><span class="checkbox">&#9744 </span>{line.text}/x</div>
    {:else}
      <div class="line"><span class="checkbox">&#9744 </span>{line.text}</div>
    {/if}
  {/each}
</div>

<style>
  .todo-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    padding: 0.75rem 1.25rem 0.75rem calc(1.75rem + 1.2em);
    font-family: inherit;
    font-size: 15px;
    line-height: 1.7;
    color: #2c2c2c;
    pointer-events: none;
    overflow: hidden;
  }

  .line {
    position: relative;
    min-height: 1lh;
  }

  .keyword-line {
    color: #b0a99f;
  }

  .checkbox {
    position: absolute;
    left: -1.2em;
    color: #b0a99f;
  }

  .h1 {
    color: #d45d00;
  }

  .h2 {
    color: #2e8b57;
  }

  .h3 {
    color: #5a7ec2;
  }

  .comment {
    color: #b0a99f;
    font-style: italic;
  }

  .checked {
    color: #b0a99f;
  }

  .checked s {
    text-decoration: line-through;
  }
</style>
