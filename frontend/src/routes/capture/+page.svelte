<script>
  import { onMount } from 'svelte';
  import { captures } from '$lib/api.js';

  let items = [];
  let showProcessed = false;
  let busy = {};        // capture id → bool
  let dayFull = {};     // capture id → bool ("today" full; offer backlog retry)
  let rowErr = {};      // capture id → string (transient error other than dayFull)

  async function load() {
    items = await captures.list();
  }
  onMount(load);

  $: visible = items.filter((c) => showProcessed || !c.processed);

  async function convert(c, target) {
    if (busy[c.id]) return;
    busy[c.id] = true;
    rowErr[c.id] = '';
    try {
      await captures.convert(c.id, target);
      dayFull[c.id] = false;
      await load();
    } catch (e) {
      const msg = e?.message || 'failed';
      if (target === 'today' && /day cap reached/i.test(msg)) {
        dayFull[c.id] = true;
      } else {
        rowErr[c.id] = msg;
      }
    } finally {
      busy[c.id] = false;
      busy = busy;
      dayFull = dayFull;
      rowErr = rowErr;
    }
  }

  async function discard(c) {
    if (busy[c.id]) return;
    busy[c.id] = true;
    rowErr[c.id] = '';
    try {
      await captures.process(c.id);
      await load();
    } catch (e) {
      rowErr[c.id] = e?.message || 'failed';
    } finally {
      busy[c.id] = false;
      busy = busy;
      rowErr = rowErr;
    }
  }
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
        <li class="surface rounded-md px-4 py-3">
          <div class="flex items-start gap-3">
            <div class="flex-1 min-w-0">
              <p class="text-ink-100 whitespace-pre-wrap" class:text-ink-500={c.processed}>{c.content}</p>
              <p class="text-xs text-ink-600 font-mono mt-1">
                {new Date(c.created_at + 'Z').toLocaleString()}
              </p>
            </div>
            {#if !c.processed}
              <div class="flex flex-wrap gap-1.5 justify-end">
                <button
                  class="btn text-xs"
                  on:click={() => convert(c, 'today')}
                  disabled={busy[c.id]}
                >→ today</button>
                <button
                  class="btn-ghost text-xs"
                  on:click={() => convert(c, 'backlog')}
                  disabled={busy[c.id]}
                >→ backlog</button>
                <button
                  class="btn-ghost text-xs text-ink-500"
                  on:click={() => discard(c)}
                  disabled={busy[c.id]}
                >discard</button>
              </div>
            {/if}
          </div>
          {#if dayFull[c.id]}
            <div class="mt-2 border border-frog/40 bg-frog/5 rounded-md px-3 py-2 flex items-center justify-between gap-3">
              <span class="text-ink-300 text-xs">today is full — send to backlog?</span>
              <div class="flex gap-2">
                <button class="btn-primary text-xs" on:click={() => convert(c, 'backlog')} disabled={busy[c.id]}>
                  → backlog
                </button>
                <button class="btn-ghost text-xs" on:click={() => (dayFull[c.id] = false, dayFull = dayFull)}>
                  dismiss
                </button>
              </div>
            </div>
          {/if}
          {#if rowErr[c.id]}
            <p class="mt-2 text-rust text-xs">{rowErr[c.id]}</p>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>
