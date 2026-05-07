<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { tasks as tasksApi, llm, sessions as sessionsApi, auth, morning, localToday } from '$lib/api.js';

  let items = [];
  let newTitle = '';
  let newNotes = '';
  let newIsFrog = false;
  let firstActions = {}; // task_id -> string
  let loadingAction = {};
  let err = '';
  let ritualPending = false;

  async function load() {
    items = await tasksApi.list();
  }

  onMount(async () => {
    const today = localToday();
    try {
      const me = await auth.me();
      const ritualToday = me.last_ritual_date === today;
      await load();
      if (!ritualToday) {
        if (items.length === 0) {
          // Force the ritual on a fresh day
          goto('/morning', { replaceState: true });
          return;
        }
        ritualPending = true; // soft banner
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
        is_frog: newIsFrog && !hasFrog
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
    await tasksApi.update(t.id, { status: t.status === 'done' ? 'pending' : 'done' });
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
            <h3
              class="text-xl text-ink-100 leading-snug"
              class:line-through={frog.status === 'done'}
              class:text-ink-500={frog.status === 'done'}
            >
              {frog.title}
            </h3>
            {#if frog.notes}<p class="text-ink-400 text-sm mt-1">{frog.notes}</p>{/if}

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
        <li class="surface rounded-md px-4 py-3 flex items-start gap-3">
          <button
            class="mt-1 w-4 h-4 rounded border border-ink-500 flex-none flex items-center justify-center"
            class:!bg-moss={t.status === 'done'}
            on:click={() => toggleDone(t)}
          >
            {#if t.status === 'done'}<span class="text-ink-950 text-[10px]">✓</span>{/if}
          </button>
          <div class="flex-1 min-w-0">
            <p
              class="text-ink-100"
              class:line-through={t.status === 'done'}
              class:text-ink-500={t.status === 'done'}
            >
              {t.title}
            </p>
            {#if t.notes}<p class="text-ink-500 text-sm">{t.notes}</p>{/if}
          </div>
          <div class="flex items-center gap-1">
            {#if t.status !== 'done'}
              <button class="btn-ghost text-xs" on:click={() => startFocus(t, 25)}>focus</button>
              <a class="btn-ghost text-xs" href="/dictate?task={t.id}" title="dictate">🎙</a>
              {#if !hasFrog}
                <button class="btn-ghost text-xs text-frog" on:click={() => makeFrog(t)}>→ frog</button>
              {/if}
            {/if}
            <button class="btn-ghost text-ink-600 hover:text-rust" on:click={() => remove(t)}>×</button>
          </div>
        </li>
      {/each}
    </ul>

    <!-- New task form -->
    <div class="mt-4 surface rounded-md p-4 space-y-3">
      <input
        class="input"
        placeholder="add task — keep titles abstract, no case data"
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

  <footer class="pt-6 border-t border-ink-800 flex justify-end">
    <button class="btn-ghost text-xs text-ink-600 hover:text-ink-300" on:click={redoMorning}>
      redo morning ritual
    </button>
  </footer>
</div>
