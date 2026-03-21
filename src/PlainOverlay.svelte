<script lang="ts">
  import { getContent } from "./lib/noteState.svelte";
  import { parsePlainLines } from "./lib/keywords/todo";

  let { overlayEl = $bindable() }: { overlayEl?: HTMLDivElement } = $props();

  const lines = $derived(parsePlainLines(getContent()));
</script>

<div class="plain-overlay" bind:this={overlayEl}>
  {#each lines as line}
    {#if line.type === "heading"}
      <div class="line heading h{line.headingLevel}">{line.text}</div>
    {:else if line.type === "empty"}
      <div class="line">&nbsp;</div>
    {:else}
      <div class="line">{line.text}</div>
    {/if}
  {/each}
</div>

<style>
  .plain-overlay {
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
    min-height: 1lh;
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
</style>
