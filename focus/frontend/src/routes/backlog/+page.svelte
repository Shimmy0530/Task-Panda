<script>
  import { onMount } from 'svelte';
  import { tasks as tasksApi, localToday } from '$lib/api.js';
  import Subtasks from '$lib/Subtasks.svelte';

  let items = [];
  let newTitle = '';
  let newNotes = '';
  let err = '';
  let rowErr = {}; // task_id -> string
  let expanded = {}; // task_id -> bool

  async function load() {
    items = await tasksApi.backlog();
  }

  onMount(load);

  async function add() {
    err = '';
    if (!newTitle.trim()) return;
    try {
      await tasksApi.create({
        title: newTitle.trim(),
        notes: newNotes.trim() || null,
        is_frog: false,
        day_date: null
      });
      newTitle = '';
      newNotes = '';
      await load();
    } catch (e) {
      err = e.message;
    }
  }

  async function graduate(t) {
    rowErr[t.id] = '';
    try {
      await tasksApi.update(t.id, { day_date: localToday() });
      await load();
    } catch (e) {
      rowErr[t.id] = e.message;
      rowErr = rowErr;
    }
  }

  async function remove(t) {
    if (!confirm(`Delete "${t.title}"?`)) return;
    await tasksApi.remove(t.id);
    await load();
  }

  async function cycleEffort(t) {
    const cycle = [null, 'S', 'M', 'L'];
    const i = cycle.indexOf(t.effort ?? null);
    const next = cycle[(i + 1) % cycle.length];
    await tasksApi.update(t.id, { effort: next });
    await load();
  }

  function toggleExpand(t) {
    expanded[t.id] = !expanded[t.id];
    expanded = expanded;
  }

  async function onSubtasksChange(t, subtasks) {
    await tasksApi.update(t.id, { subtasks });
    await load();
  }

  function effortLabel(e) {
    return e || '—';
  }
</script>

<div class="space-y-8">
  <header>
    <p class="label mb-2">📦 backlog</p>
    <h1 class="font-display text-3xl text-ink-100 tracking-tightest leading-none">
      everything you want to do, just not today.
    </h1>
    <p class="text-ink-500 text-sm mt-2">
      The morning ritual lets you pull 0–2 of these into today.
    </p>
  </header>

  <section>
    <ul class="space-y-2">
      {#each items as t (t.id)}
        <li class="surface rounded-md px-4 py-3">
          <div class="flex items-start gap-3">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <p class="text-ink-100 flex-1 truncate">{t.title}</p>
                <button
                  class="btn-ghost text-[10px] px-1.5 border border-ink-700 rounded font-mono"
                  on:click={() => cycleEffort(t)}
                  title="effort"
                >{effortLabel(t.effort)}</button>
              </div>
              {#if t.notes}<p class="text-ink-500 text-sm">{t.notes}</p>{/if}
              <div class="mt-1">
                {#if (t.subtasks || []).length > 0}
                  <button class="btn-ghost text-[11px]" on:click={() => toggleExpand(t)}>
                    ▸ {(t.subtasks || []).filter((s) => s.done).length}/{t.subtasks.length} subtasks
                  </button>
                {:else}
                  <button class="btn-ghost text-[11px] text-ink-500" on:click={() => toggleExpand(t)}>
                    + break down
                  </button>
                {/if}
              </div>
              {#if expanded[t.id]}
                <div class="mt-2 pl-2 border-l border-ink-700">
                  <Subtasks task={t} onChange={(st) => onSubtasksChange(t, st)} />
                </div>
              {/if}
              {#if rowErr[t.id]}
                <p class="text-rust text-xs mt-2">{rowErr[t.id]}</p>
              {/if}
            </div>
            <div class="flex items-center gap-1">
              <button class="btn text-xs" on:click={() => graduate(t)} title="pull to today">→ today</button>
              <button class="btn-ghost text-ink-600 hover:text-rust" on:click={() => remove(t)}>×</button>
            </div>
          </div>
        </li>
      {:else}
        <li class="border border-dashed border-ink-700 rounded-md p-5 text-ink-500 text-sm italic">
          backlog is empty. anything that's not for today belongs here.
        </li>
      {/each}
    </ul>

    <div class="mt-4 surface rounded-md p-4 space-y-3">
      <input
        class="input"
        placeholder="add to backlog"
        bind:value={newTitle}
        on:keydown={(e) => e.key === 'Enter' && !e.shiftKey && add()}
      />
      <textarea class="input text-sm font-mono min-h-[60px] resize-none" placeholder="optional notes" bind:value={newNotes}></textarea>
      <div class="flex justify-end">
        <button class="btn-primary" on:click={add}>add to backlog</button>
      </div>
      {#if err}<p class="text-rust text-sm">{err}</p>{/if}
    </div>
  </section>
</div>
