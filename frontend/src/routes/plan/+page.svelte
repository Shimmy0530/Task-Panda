<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { tasks as tasksApi, llm, sessions as sessionsApi, auth, morning, localToday } from '$lib/api.js';
  import Subtasks from '$lib/Subtasks.svelte';

  let items = [];
  let backlogCount = 0;
  let newTitle = '';
  let newNotes = '';
  let newIsFrog = false;
  let firstActions = {}; // task_id -> string
  let loadingAction = {};
  let err = '';
  let ritualPending = false;
  let expanded = {}; // task_id -> bool (subtask panel open)
  let nudgeId = null; // task whose subtasks all just became done; flashes "mark done?"
  let nudgeTimer = null;
  let copiedId = null;
  let copiedTimer = null;

  async function load() {
    items = await tasksApi.list();
    try {
      const bl = await tasksApi.backlog();
      backlogCount = bl.length;
    } catch {}
  }

  onMount(async () => {
    const today = localToday();
    try {
      const me = await auth.me();
      const ritualToday = me.last_ritual_date === today;
      await load();
      if (!ritualToday) {
        if (items.length === 0) {
          goto('/morning', { replaceState: true });
          return;
        }
        ritualPending = true;
      }
    } catch {
      await load();
    }
  });

  $: frog = items.find((t) => t.is_frog);
  $: others = items.filter((t) => !t.is_frog);
  $: hasFrog = !!frog;

  async function addTask() {
    err = '';
    if (!newTitle.trim()) return;
    try {
      await tasksApi.create({
        title: newTitle.trim(),
        notes: newNotes.trim() || null,
        is_frog: newIsFrog && !hasFrog,
        day_date: localToday()
      });
      newTitle = '';
      newNotes = '';
      newIsFrog = false;
      await load();
    } catch (e) {
      err = e.message;
    }
  }

  async function toggleDone(t) {
    if (t.status !== 'done' && (t.subtasks || []).some((s) => !s.done) && (t.subtasks || []).length > 0) {
      const open = t.subtasks.filter((s) => !s.done).length;
      const total = t.subtasks.length;
      if (!confirm(`${open} of ${total} subtasks open. Mark done anyway?`)) return;
    }
    await tasksApi.update(t.id, { status: t.status === 'done' ? 'pending' : 'done' });
    if (nudgeId === t.id) clearNudge();
    await load();
  }

  async function makeFrog(t) {
    if (hasFrog) return;
    await tasksApi.update(t.id, { is_frog: true });
    await load();
  }

  async function remove(t) {
    if (!confirm(`Delete "${t.title}"?`)) return;
    await tasksApi.remove(t.id);
    await load();
  }

  async function getFirstAction(t) {
    loadingAction[t.id] = true;
    loadingAction = loadingAction;
    try {
      const r = await llm.firstAction(t.title, t.notes);
      firstActions[t.id] = r.action;
      firstActions = firstActions;
    } catch (e) {
      firstActions[t.id] = `(LLM error: ${e.message})`;
      firstActions = firstActions;
    } finally {
      loadingAction[t.id] = false;
      loadingAction = loadingAction;
    }
  }

  async function startFocus(t, mins) {
    const s = await sessionsApi.start(t.id, mins * 60);
    goto(`/focus?session=${s.id}&task=${t.id}`);
  }

  async function redoMorning() {
    if (!confirm('Redo the morning ritual? Today’s tasks stay; you can re-pick the frog and supporting tasks.')) return;
    await morning.reset();
    goto('/morning');
  }

  function toggleExpand(t) {
    expanded[t.id] = !expanded[t.id];
    expanded = expanded;
  }

  async function onSubtasksChange(t, subtasks) {
    const had = (t.subtasks || []).filter((s) => s.done).length;
    const total = subtasks.length;
    const doneNow = subtasks.filter((s) => s.done).length;
    await tasksApi.update(t.id, { subtasks });
    if (total > 0 && doneNow === total && t.status !== 'done' && doneNow > had) {
      nudgeId = t.id;
      if (nudgeTimer) clearTimeout(nudgeTimer);
      nudgeTimer = setTimeout(() => clearNudge(), 8000);
    }
    await load();
  }

  function clearNudge() {
    nudgeId = null;
    if (nudgeTimer) clearTimeout(nudgeTimer);
    nudgeTimer = null;
  }

  async function cycleEffort(t) {
    const cycle = [null, 'S', 'M', 'L'];
    const i = cycle.indexOf(t.effort ?? null);
    const next = cycle[(i + 1) % cycle.length];
    await tasksApi.update(t.id, { effort: next });
    await load();
  }

  async function copyTask(t) {
    try {
      await tasksApi.copy(t.id);
      copiedId = t.id;
      if (copiedTimer) clearTimeout(copiedTimer);
      copiedTimer = setTimeout(() => (copiedId = null), 2000);
      await load();
    } catch (e) {
      err = e.message;
    }
  }

  function effortLabel(e) {
    return e || '—';
  }
</script>

<div class="space-y-10">
  <header>
    <p class="label mb-2">today</p>
    <h1 class="font-display text-4xl text-ink-100 tracking-tightest leading-none">
      {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
    </h1>
  </header>

  {#if ritualPending}
    <div class="border border-frog/40 bg-frog/5 rounded-md p-4 flex items-center justify-between">
      <p class="text-ink-200 text-sm">
        <span class="font-display text-base">good morning.</span>
        <span class="text-ink-400">the day starts cleaner with a 1-min plan.</span>
      </p>
      <a class="btn-primary text-xs" href="/morning">begin →</a>
    </div>
  {/if}

  <!-- Frog -->
  <section>
    <p class="label mb-3">🐸 frog — eat first</p>
    {#if frog}
      <div class="surface rounded-lg p-5 border-frog/40 frog-pulse" class:!border-moss={frog.status === 'done'}>
        <div class="flex items-start gap-3">
          <button
            class="mt-1 w-5 h-5 rounded border border-ink-500 flex-none flex items-center justify-center"
            class:!bg-moss={frog.status === 'done'}
            on:click={() => toggleDone(frog)}
            aria-label="toggle done"
          >
            {#if frog.status === 'done'}<span class="text-ink-950 text-xs">✓</span>{/if}
          </button>
          <div class="flex-1 min-w-0">
            <div class="flex items-start gap-2">
              <h3
                class="text-xl text-ink-100 leading-snug flex-1"
                class:line-through={frog.status === 'done'}
                class:text-ink-500={frog.status === 'done'}
              >
                {frog.title}
              </h3>
              <button
                class="btn-ghost text-xs px-2 border border-ink-700 rounded font-mono"
                on:click={() => cycleEffort(frog)}
                title="effort: small / medium / large"
              >{effortLabel(frog.effort)}</button>
              <button
                class="btn-ghost text-xs"
                on:click={() => copyTask(frog)}
                title="copy as new task today"
              >📋</button>
            </div>
            {#if frog.notes}<p class="text-ink-400 text-sm mt-1">{frog.notes}</p>{/if}

            <div class="mt-3">
              {#if (frog.subtasks || []).length > 0}
                <button class="btn-ghost text-xs" on:click={() => toggleExpand(frog)}>
                  ▸ {(frog.subtasks || []).filter((s) => s.done).length}/{frog.subtasks.length} subtasks
                </button>
              {:else}
                <button class="btn-ghost text-xs text-ink-500" on:click={() => toggleExpand(frog)}>
                  + break down
                </button>
              {/if}
            </div>

            {#if expanded[frog.id]}
              <div class="mt-3 pl-2 border-l border-ink-700">
                <Subtasks task={frog} onChange={(st) => onSubtasksChange(frog, st)} />
              </div>
            {/if}

            {#if nudgeId === frog.id}
              <div class="mt-3 border border-moss/50 bg-moss/10 rounded-md p-2 flex items-center justify-between">
                <span class="text-moss text-xs">all subtasks done — mark task as done?</span>
                <div class="flex gap-2">
                  <button class="btn-primary text-xs" on:click={() => toggleDone(frog)}>mark done</button>
                  <button class="btn-ghost text-xs" on:click={clearNudge}>dismiss</button>
                </div>
              </div>
            {/if}

            {#if frog.status !== 'done'}
              <div class="mt-4 flex flex-wrap gap-2">
                <button class="btn-primary" on:click={() => startFocus(frog, 25)}>start 25</button>
                <button class="btn" on:click={() => startFocus(frog, 50)}>start 50</button>
                <button class="btn" on:click={() => startFocus(frog, 10)}>just 10</button>
                <a class="btn" href="/dictate?task={frog.id}">🎙 dictate</a>
                <button class="btn-ghost" on:click={() => getFirstAction(frog)} disabled={loadingAction[frog.id]}>
                  {loadingAction[frog.id] ? 'thinking…' : 'first move?'}
                </button>
              </div>
              {#if firstActions[frog.id]}
                <div class="mt-3 border-l-2 border-frog pl-3 text-ink-200 text-sm italic">
                  {firstActions[frog.id]}
                </div>
              {/if}
            {/if}
          </div>
          <button class="btn-ghost text-ink-600 hover:text-rust" on:click={() => remove(frog)} aria-label="delete">×</button>
        </div>
        {#if copiedId === frog.id}
          <p class="text-moss text-xs mt-2 italic">copied to today</p>
        {/if}
      </div>
    {:else}
      <div class="border border-dashed border-ink-700 rounded-lg p-5 text-ink-500 text-sm">
        Mark one task as the frog. The boring, important one. <br />
        <span class="text-ink-600">No frog = no traction.</span>
      </div>
    {/if}
  </section>

  <!-- Other tasks -->
  <section>
    <p class="label mb-3">other</p>
    <ul class="space-y-2">
      {#each others as t (t.id)}
        <li class="surface rounded-md px-4 py-3">
          <div class="flex items-start gap-3">
            <button
              class="mt-1 w-4 h-4 rounded border border-ink-500 flex-none flex items-center justify-center"
              class:!bg-moss={t.status === 'done'}
              on:click={() => toggleDone(t)}
            >
              {#if t.status === 'done'}<span class="text-ink-950 text-[10px]">✓</span>{/if}
            </button>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <p
                  class="text-ink-100 flex-1"
                  class:line-through={t.status === 'done'}
                  class:text-ink-500={t.status === 'done'}
                >
                  {t.title}
                </p>
                <button
                  class="btn-ghost text-[10px] px-1.5 border border-ink-700 rounded font-mono"
                  on:click={() => cycleEffort(t)}
                  title="effort: small / medium / large"
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
              {#if nudgeId === t.id}
                <div class="mt-2 border border-moss/50 bg-moss/10 rounded-md p-2 flex items-center justify-between">
                  <span class="text-moss text-xs">all subtasks done — mark task as done?</span>
                  <div class="flex gap-2">
                    <button class="btn-primary text-xs" on:click={() => toggleDone(t)}>mark done</button>
                    <button class="btn-ghost text-xs" on:click={clearNudge}>dismiss</button>
                  </div>
                </div>
              {/if}
              {#if copiedId === t.id}
                <p class="text-moss text-xs mt-1 italic">copied to today</p>
              {/if}
            </div>
            <div class="flex items-center gap-1">
              {#if t.status !== 'done'}
                <button class="btn-ghost text-xs" on:click={() => startFocus(t, 25)}>focus</button>
                <a class="btn-ghost text-xs" href="/dictate?task={t.id}" title="dictate">🎙</a>
                {#if !hasFrog}
                  <button class="btn-ghost text-xs text-frog" on:click={() => makeFrog(t)}>→ frog</button>
                {/if}
              {/if}
              <button class="btn-ghost text-xs" on:click={() => copyTask(t)} title="copy as new task today">📋</button>
              <button class="btn-ghost text-ink-600 hover:text-rust" on:click={() => remove(t)}>×</button>
            </div>
          </div>
        </li>
      {/each}
    </ul>

    <!-- New task form -->
    <div class="mt-4 surface rounded-md p-4 space-y-3">
      <input
        class="input"
        placeholder="add task"
        bind:value={newTitle}
        on:keydown={(e) => e.key === 'Enter' && !e.shiftKey && addTask()}
      />
      <textarea class="input text-sm font-mono min-h-[60px] resize-none" placeholder="optional notes" bind:value={newNotes}></textarea>
      <div class="flex items-center justify-between">
        <label class="flex items-center gap-2 text-sm text-ink-400">
          <input type="checkbox" bind:checked={newIsFrog} disabled={hasFrog} />
          mark as frog {#if hasFrog}<span class="text-ink-600">(already set)</span>{/if}
        </label>
        <button class="btn-primary" on:click={addTask}>add</button>
      </div>
      {#if err}<p class="text-rust text-sm">{err}</p>{/if}
    </div>
  </section>

  <footer class="pt-6 border-t border-ink-800 flex items-center justify-between">
    {#if backlogCount > 0}
      <a class="text-xs text-ink-500 hover:text-ink-200 font-mono" href="/backlog">📦 backlog ({backlogCount})</a>
    {:else}
      <a class="text-xs text-ink-600 hover:text-ink-300 font-mono" href="/backlog">📦 backlog</a>
    {/if}
    <button class="btn-ghost text-xs text-ink-600 hover:text-ink-300" on:click={redoMorning}>
      redo morning ritual
    </button>
  </footer>
</div>
