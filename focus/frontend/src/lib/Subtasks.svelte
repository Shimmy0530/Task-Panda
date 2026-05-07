<script>
  import { llm } from '$lib/api.js';

  // Props
  export let task; // must include subtasks: [{id, title, done}]
  export let onChange; // (newSubtasks: list) => Promise<void>
  export let allowAI = true;

  let local = (task.subtasks || []).map((s) => ({ ...s }));
  let editingId = null;
  let editingValue = '';
  let newTitle = '';
  let staging = null; // null | array of {id, title, done, picked}
  let aiBusy = false;
  let aiEmpty = false;
  let err = '';

  // Re-sync if the parent reloads with fresh data — but only when not actively editing.
  $: if (task && editingId === null && staging === null) {
    local = (task.subtasks || []).map((s) => ({ ...s }));
  }

  function uid() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
    return Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  async function commit() {
    err = '';
    try {
      await onChange(local.map(({ id, title, done }) => ({ id, title, done })));
    } catch (e) {
      err = e.message;
    }
  }

  async function toggleDone(id) {
    local = local.map((s) => (s.id === id ? { ...s, done: !s.done } : s));
    await commit();
  }

  async function add() {
    const t = newTitle.trim();
    if (!t) return;
    local = [...local, { id: uid(), title: t, done: false }];
    newTitle = '';
    await commit();
  }

  async function remove(id) {
    local = local.filter((s) => s.id !== id);
    await commit();
  }

  function startEdit(s) {
    editingId = s.id;
    editingValue = s.title;
  }

  function cancelEdit() {
    editingId = null;
    editingValue = '';
  }

  async function saveEdit() {
    const v = editingValue.trim();
    const id = editingId;
    if (!v) {
      cancelEdit();
      return;
    }
    local = local.map((s) => (s.id === id ? { ...s, title: v } : s));
    cancelEdit();
    await commit();
  }

  async function move(id, dir) {
    const idx = local.findIndex((s) => s.id === id);
    if (idx < 0) return;
    const nxt = idx + dir;
    if (nxt < 0 || nxt >= local.length) return;
    const copy = local.slice();
    [copy[idx], copy[nxt]] = [copy[nxt], copy[idx]];
    local = copy;
    await commit();
  }

  async function aiBreakdown() {
    aiBusy = true;
    aiEmpty = false;
    err = '';
    try {
      const r = await llm.subtasks(task.id);
      const items = r.subtasks || [];
      if (items.length === 0) {
        aiEmpty = true;
        staging = null;
      } else {
        staging = items.map((s) => ({ ...s, picked: true }));
      }
    } catch (e) {
      err = e.message;
    } finally {
      aiBusy = false;
    }
  }

  function togglePick(id) {
    staging = staging.map((s) => (s.id === id ? { ...s, picked: !s.picked } : s));
  }

  async function keepStaged() {
    const picked = staging.filter((s) => s.picked).map((s) => ({ id: s.id, title: s.title, done: false }));
    if (picked.length) {
      local = [...local, ...picked];
      staging = null;
      await commit();
    } else {
      staging = null;
    }
  }

  function cancelStaging() {
    staging = null;
  }

  $: pickedCount = staging ? staging.filter((s) => s.picked).length : 0;
</script>

<div class="space-y-2">
  <ul class="space-y-1">
    {#each local as s, i (s.id)}
      <li class="flex items-center gap-2 text-sm">
        <button
          type="button"
          class="w-4 h-4 rounded border border-ink-500 flex-none flex items-center justify-center"
          class:!bg-moss={s.done}
          on:click={() => toggleDone(s.id)}
          aria-label="toggle done"
        >
          {#if s.done}<span class="text-ink-950 text-[10px]">✓</span>{/if}
        </button>

        {#if editingId === s.id}
          <input
            class="input flex-1 text-sm py-1"
            bind:value={editingValue}
            autofocus
            on:keydown={(e) => {
              if (e.key === 'Enter') saveEdit();
              if (e.key === 'Escape') cancelEdit();
            }}
            on:blur={saveEdit}
          />
        {:else}
          <button
            type="button"
            class="flex-1 text-left text-ink-100 hover:text-ink-300 truncate"
            class:line-through={s.done}
            class:!text-ink-500={s.done}
            on:click={() => startEdit(s)}
            title="click to rename"
          >
            {s.title}
          </button>
        {/if}

        <button
          type="button"
          class="btn-ghost text-ink-600 hover:text-ink-200 text-xs px-1"
          on:click={() => move(s.id, -1)}
          disabled={i === 0}
          aria-label="move up"
        >↑</button>
        <button
          type="button"
          class="btn-ghost text-ink-600 hover:text-ink-200 text-xs px-1"
          on:click={() => move(s.id, 1)}
          disabled={i === local.length - 1}
          aria-label="move down"
        >↓</button>
        <button
          type="button"
          class="btn-ghost text-ink-600 hover:text-rust text-xs px-1"
          on:click={() => remove(s.id)}
          aria-label="delete"
        >×</button>
      </li>
    {/each}
  </ul>

  <div class="flex items-center gap-2">
    <input
      class="input text-sm py-1 flex-1"
      placeholder="add subtask"
      bind:value={newTitle}
      on:keydown={(e) => e.key === 'Enter' && add()}
    />
    <button class="btn text-xs" on:click={add} disabled={!newTitle.trim()}>add</button>
    {#if allowAI}
      <button class="btn-ghost text-xs" on:click={aiBreakdown} disabled={aiBusy}>
        {aiBusy ? 'thinking…' : (staging ? '✨ regenerate' : '✨ break this down')}
      </button>
    {/if}
  </div>

  {#if aiEmpty}
    <p class="text-xs text-ink-500 italic">
      AI thinks this is already small. Add subtasks manually anyway?
    </p>
  {/if}

  {#if staging}
    <div class="border border-frog/40 bg-frog/5 rounded-md p-3 space-y-2">
      <p class="label text-frog">suggestions — uncheck to skip, then keep</p>
      <ul class="space-y-1">
        {#each staging as s (s.id)}
          <li class="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={s.picked} on:change={() => togglePick(s.id)} />
            <span class="text-ink-200">{s.title}</span>
          </li>
        {/each}
      </ul>
      <div class="flex items-center gap-2">
        <button class="btn-primary text-xs" on:click={keepStaged} disabled={pickedCount === 0}>
          keep selected ({pickedCount})
        </button>
        <button class="btn-ghost text-xs" on:click={cancelStaging}>cancel</button>
      </div>
    </div>
  {/if}

  {#if err}<p class="text-rust text-xs">{err}</p>{/if}
</div>
