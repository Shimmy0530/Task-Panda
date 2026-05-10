<script>
  import { onMount } from 'svelte';
  import { captures } from '$lib/api.js';

  let items = [];
  let showProcessed = false;

  async function load() {
    items = await captures.list();
  }
  onMount(load);

  async function done(c) {
    await captures.process(c.id);
    await load();
  }

  $: visible = items.filter((c) => showProcessed || !c.processed);
</script>

<div class="space-y-6">
  <header class="flex items-end justify-between">
    <div>
      <p class="label mb-2">inbox</p>
      <h1 class="font-display text-3xl text-ink-100 tracking-tightest">captured thoughts</h1>
    </div>
    <label class="flex items-center gap-2 text-sm text-ink-400">
      <input type="checkbox" bind:checked={showProcessed} /> show processed
    </label>
  </header>

  <p class="text-ink-500 text-sm">
    Press <span class="font-mono text-ink-300">⌘.</span> from anywhere to capture without breaking flow.
  </p>

  {#if visible.length === 0}
    <p class="text-ink-600 italic">empty.</p>
  {:else}
    <ul class="space-y-2">
      {#each visible as c (c.id)}
        <li class="surface rounded-md px-4 py-3 flex items-start gap-3">
          <button
            class="mt-1 w-4 h-4 rounded border border-ink-500 flex-none"
            class:!bg-moss={c.processed}
            on:click={() => !c.processed && done(c)}
            aria-label="mark processed"
          ></button>
          <div class="flex-1 min-w-0">
            <p class="text-ink-100 whitespace-pre-wrap" class:text-ink-500={c.processed}>{c.content}</p>
            <p class="text-xs text-ink-600 font-mono mt-1">
              {new Date(c.created_at + 'Z').toLocaleString()}
            </p>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>
