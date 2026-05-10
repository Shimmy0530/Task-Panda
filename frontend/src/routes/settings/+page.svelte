<script>
  import { onMount } from 'svelte';
  import { settings as settingsApi } from '$lib/api.js';

  let stuckThreshold = 5;
  let saved = false;
  let savedTimer = null;
  let err = '';
  let loaded = false;

  onMount(async () => {
    try {
      const r = await settingsApi.get();
      stuckThreshold = r.stuck_threshold_days;
    } catch (e) {
      err = e.message;
    } finally {
      loaded = true;
    }
  });

  async function save() {
    err = '';
    const v = Number(stuckThreshold);
    if (!Number.isInteger(v) || v < 1 || v > 30) {
      err = 'must be an integer between 1 and 30';
      return;
    }
    try {
      const r = await settingsApi.update({ stuck_threshold_days: v });
      stuckThreshold = r.stuck_threshold_days;
      saved = true;
      if (savedTimer) clearTimeout(savedTimer);
      savedTimer = setTimeout(() => (saved = false), 1500);
    } catch (e) {
      err = e.message;
    }
  }
</script>

<div class="space-y-8">
  <header>
    <p class="label mb-2">settings</p>
    <h1 class="font-display text-3xl text-ink-100 tracking-tightest leading-none">
      knobs.
    </h1>
  </header>

  {#if loaded}
    <section class="surface rounded-md p-5 space-y-3">
      <label class="block">
        <span class="text-ink-200 text-sm">stuck threshold (days)</span>
        <input
          class="input mt-2 w-32 font-mono"
          type="number"
          min="1"
          max="30"
          bind:value={stuckThreshold}
          on:blur={save}
          on:keydown={(e) => e.key === 'Enter' && e.target.blur()}
        />
      </label>
      <p class="text-ink-500 text-xs">
        Days a task can be carried before the morning ritual flags it as stuck.
      </p>
      {#if saved}<p class="text-moss text-xs">saved</p>{/if}
      {#if err}<p class="text-rust text-xs">{err}</p>{/if}
    </section>
  {/if}
</div>
