<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { morning, localToday } from '$lib/api.js';

  const today = localToday();

  // Step IDs are strings to keep order explicit. Conditional steps are inserted at runtime.
  const BASE_STEPS = ['intro', 'carry', 'frog', 'support', 'confirm'];
  let stepFlow = BASE_STEPS.slice();
  let stepIdx = 0;
  $: stepId = stepFlow[stepIdx];

  let yest = [];
  let yestActions = {};
  let todayExisting = [];
  let frogTitle = '';
  let frogNotes = '';
  let support1 = '';
  let support2 = '';
  let saving = false;
  let err = '';

  let stuckYesterday = [];
  let stuckThreshold = 5;
  let backlogTop = [];
  let staleBacklog = [];
  let pullSelected = new Set();
  let staleActions = {}; // task_id -> 'drop' | 'keep' | null

  onMount(async () => {
    try {
      const s = await morning.state(today);
      if (s.ritual_done) {
        goto('/plan', { replaceState: true });
        return;
      }
      yest = s.yesterday_open || [];
      todayExisting = s.today_existing || [];
      stuckYesterday = s.stuck_yesterday || [];
      stuckThreshold = s.stuck_threshold_days || 5;
      backlogTop = s.backlog_top || [];
      staleBacklog = s.stale_backlog || [];

      yestActions = Object.fromEntries(
        yest.map((t) => [t.id, t.is_frog ? 'carry' : null])
      );
      staleActions = Object.fromEntries(staleBacklog.map((t) => [t.id, null]));

      const existingFrog = todayExisting.find((t) => t.is_frog);
      if (existingFrog) frogTitle = existingFrog.title;

      // Build step flow with conditional insertions.
      const flow = ['intro', 'carry', 'frog', 'support'];
      if (backlogTop.length > 0) flow.push('pull');
      if (staleBacklog.length > 0) flow.push('stale');
      flow.push('confirm');
      stepFlow = flow;
    } catch (e) {
      err = e.message;
    }
  });

  function next() {
    if (stepId === 'carry' && yest.some((t) => !yestActions[t.id])) {
      err = 'Decide on each carry-over before continuing.';
      return;
    }
    if (stepId === 'frog' && !frogTitle.trim()) {
      err = 'Pick a frog. The boring, important one.';
      return;
    }
    if (stepId === 'stale' && staleBacklog.some((t) => !staleActions[t.id])) {
      err = 'Drop or keep each stale item before continuing.';
      return;
    }
    err = '';
    stepIdx = Math.min(stepFlow.length - 1, stepIdx + 1);
  }

  function back() {
    err = '';
    stepIdx = Math.max(0, stepIdx - 1);
  }

  function togglePull(id) {
    const next = new Set(pullSelected);
    if (next.has(id)) {
      next.delete(id);
    } else {
      if (next.size >= 2) return;
      next.add(id);
    }
    pullSelected = next;
  }

  async function commit() {
    saving = true;
    err = '';
    try {
      const dropped = Object.entries(staleActions)
        .filter(([, v]) => v === 'drop')
        .map(([id]) => Number(id));
      const kept = Object.entries(staleActions)
        .filter(([, v]) => v === 'keep')
        .map(([id]) => Number(id));

      await morning.complete({
        today_date: today,
        yesterday_actions: yest
          .filter((t) => yestActions[t.id])
          .map((t) => ({ task_id: t.id, action: yestActions[t.id] })),
        frog_title: frogTitle.trim(),
        frog_notes: frogNotes.trim() || null,
        supporting_titles: [support1, support2].filter((s) => s.trim()),
        pull_from_backlog: [...pullSelected],
        dropped_stale_ids: dropped,
        kept_stale_ids: kept
      });
      stepIdx = stepFlow.length; // sentinel = "done"
      setTimeout(() => goto('/plan'), 1400);
    } catch (e) {
      err = e.message;
    } finally {
      saving = false;
    }
  }

  async function skipToday() {
    if (!confirm('Skip the morning ritual for today? You can still add tasks manually.')) return;
    await morning.skip(today);
    goto('/plan');
  }

  function subtaskChip(t) {
    if (!t.subtasks || t.subtasks.length === 0) return '';
    const done = t.subtasks.filter((s) => s.done).length;
    return `${done}/${t.subtasks.length} done`;
  }

  function isStuck(t) {
    return stuckYesterday.includes(t.id);
  }

  $: dateLine = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric'
  });

  // Visible step indicator: collapse "pull" and "stale" into "extras"
  // so the bar still reads as 4 segments, matching the user's mental model.
  $: visibleStep = (() => {
    if (stepId === 'intro') return 0;
    if (stepId === 'carry') return 1;
    if (stepId === 'frog') return 2;
    if (stepId === 'support') return 3;
    if (stepId === 'pull' || stepId === 'stale') return 3;
    if (stepId === 'confirm') return 4;
    return 5; // done
  })();

  $: pulledTasks = backlogTop.filter((t) => pullSelected.has(t.id));
</script>

<div class="max-w-2xl mx-auto pt-4 pb-20 min-h-[80vh] flex flex-col">
  <!-- Step indicator -->
  {#if visibleStep > 0 && visibleStep < 5}
    <div class="flex items-center gap-2 mb-12">
      {#each [1, 2, 3, 4] as n}
        <div
          class="h-px flex-1 transition-colors"
          class:bg-frog={visibleStep >= n}
          class:bg-ink-700={visibleStep < n}
        ></div>
      {/each}
      <span class="text-ink-500 font-mono text-xs ml-2">{visibleStep}/4</span>
    </div>
  {/if}

  <div class="flex-1">
    {#if stepId === 'intro'}
      <div class="text-center py-16">
        <p class="label mb-4 text-ink-500">{dateLine}</p>
        <h1 class="font-display text-5xl md:text-6xl text-ink-100 tracking-tightest leading-none mb-6">
          good morning.
        </h1>
        <p class="text-ink-300 max-w-md mx-auto leading-relaxed mb-12">
          A few minutes here saves you the whole day from drift.
          We'll handle yesterday, name the frog, and pick at most two more.
        </p>
        <button class="btn-primary text-base px-8 py-3" on:click={next}>begin</button>
        <div class="mt-6">
          <button class="btn-ghost text-xs" on:click={skipToday}>skip today</button>
        </div>
      </div>

    {:else if stepId === 'carry'}
      <h2 class="font-display text-3xl text-ink-100 tracking-tightest leading-tight mb-3">
        yesterday, what survives?
      </h2>
      <p class="text-ink-400 text-sm mb-8 leading-relaxed">
        Each one: carry forward, mark it done, or drop it. No third option — drift dies in the third option.
      </p>

      {#if yest.length === 0}
        <div class="surface rounded-md p-6 text-ink-500 italic">
          Nothing open from yesterday. Clean slate.
        </div>
      {:else}
        <ul class="space-y-2">
          {#each yest as t (t.id)}
            <li class="surface rounded-md p-4">
              {#if isStuck(t)}
                <div class="border border-rust/40 bg-rust/5 rounded px-3 py-2 mb-3 text-rust text-xs">
                  stuck {t.carried_count} day{t.carried_count === 1 ? '' : 's'} — re-frame, break down, or drop.
                </div>
              {/if}
              <p class="text-ink-100 mb-1">
                {t.is_frog ? '🐸 ' : ''}{t.title}
              </p>
              {#if subtaskChip(t)}
                <p class="text-ink-500 text-xs mb-2">{subtaskChip(t)}</p>
              {/if}
              <div class="flex gap-2 flex-wrap mt-2">
                <button
                  class="btn text-xs"
                  class:!border-frog={yestActions[t.id] === 'carry'}
                  class:!text-frog={yestActions[t.id] === 'carry'}
                  on:click={() => (yestActions[t.id] = 'carry')}
                >carry forward</button>
                <button
                  class="btn text-xs"
                  class:!border-moss={yestActions[t.id] === 'done'}
                  class:!text-moss={yestActions[t.id] === 'done'}
                  on:click={() => (yestActions[t.id] = 'done')}
                >mark done</button>
                <button
                  class="btn text-xs"
                  class:!border-rust={yestActions[t.id] === 'drop'}
                  class:!text-rust={yestActions[t.id] === 'drop'}
                  on:click={() => (yestActions[t.id] = 'drop')}
                >drop it</button>
              </div>
            </li>
          {/each}
        </ul>
      {/if}

    {:else if stepId === 'frog'}
      <h2 class="font-display text-3xl text-ink-100 tracking-tightest leading-tight mb-3">
        what's the frog?
      </h2>
      <p class="text-ink-400 text-sm mb-8 leading-relaxed">
        The boring, important one. The thing you'll avoid all day if you don't name it now.
      </p>

      <div class="space-y-3">
        <input
          class="input text-lg"
          autofocus
          placeholder="e.g. Q3 inspection report"
          bind:value={frogTitle}
          on:keydown={(e) => e.key === 'Enter' && next()}
        />
        <textarea
          class="input text-sm font-mono min-h-[80px] resize-none"
          placeholder="optional notes — what's the actual blocker?"
          bind:value={frogNotes}
        ></textarea>
      </div>

    {:else if stepId === 'support'}
      <h2 class="font-display text-3xl text-ink-100 tracking-tightest leading-tight mb-3">
        two more, separate.
      </h2>
      <p class="text-ink-400 text-sm mb-8 leading-relaxed">
        Up to two other independent things to get done today.
        Each is its own task with its own pomodoro — not a step inside the frog.
        Leave blank if there's nothing real.
      </p>

      <ul class="space-y-2">
        <li class="surface rounded-md px-4 py-3 flex items-baseline gap-3">
          <span class="label text-ink-600 w-12 flex-none">task 1</span>
          <span class="text-frog">🐸</span>
          <span class="text-ink-200 text-sm flex-1 truncate">{frogTitle}</span>
          <span class="text-ink-600 text-[10px] uppercase tracking-wider">locked in</span>
        </li>
        <li class="flex items-baseline gap-3">
          <span class="label text-ink-600 w-12 flex-none">task 2</span>
          <input class="input flex-1" placeholder="another independent task (optional)" bind:value={support1} />
        </li>
        <li class="flex items-baseline gap-3">
          <span class="label text-ink-600 w-12 flex-none">task 3</span>
          <input class="input flex-1" placeholder="another independent task (optional)" bind:value={support2} />
        </li>
      </ul>

    {:else if stepId === 'pull'}
      <h2 class="font-display text-3xl text-ink-100 tracking-tightest leading-tight mb-3">
        pull anything in?
      </h2>
      <p class="text-ink-400 text-sm mb-8 leading-relaxed">
        From the backlog. Pick 0–2. They'll graduate to today.
      </p>

      <ul class="space-y-2">
        {#each backlogTop as t (t.id)}
          {@const checked = pullSelected.has(t.id)}
          {@const disabled = !checked && pullSelected.size >= 2}
          <li class="surface rounded-md p-3 flex items-center gap-3">
            <input
              type="checkbox"
              checked={checked}
              {disabled}
              on:change={() => togglePull(t.id)}
            />
            <div class="flex-1 min-w-0">
              <p class="text-ink-100 truncate">{t.title}</p>
              {#if subtaskChip(t)}
                <p class="text-ink-500 text-xs">{subtaskChip(t)}</p>
              {/if}
            </div>
            {#if t.effort}<span class="text-ink-600 text-xs font-mono">{t.effort}</span>{/if}
          </li>
        {/each}
      </ul>
      <p class="text-xs text-ink-600 mt-3">{pullSelected.size}/2 selected</p>

    {:else if stepId === 'stale'}
      <h2 class="font-display text-3xl text-ink-100 tracking-tightest leading-tight mb-3">
        backlog hygiene.
      </h2>
      <p class="text-ink-400 text-sm mb-8 leading-relaxed">
        These have been sitting for 30+ days. Drop or keep — keeping resets the clock.
      </p>

      <ul class="space-y-2">
        {#each staleBacklog as t (t.id)}
          <li class="surface rounded-md p-4">
            <p class="text-ink-100 mb-2">{t.title}</p>
            <div class="flex gap-2">
              <button
                class="btn text-xs"
                class:!border-rust={staleActions[t.id] === 'drop'}
                class:!text-rust={staleActions[t.id] === 'drop'}
                on:click={() => (staleActions[t.id] = 'drop')}
              >drop</button>
              <button
                class="btn text-xs"
                class:!border-moss={staleActions[t.id] === 'keep'}
                class:!text-moss={staleActions[t.id] === 'keep'}
                on:click={() => (staleActions[t.id] = 'keep')}
              >keep</button>
            </div>
          </li>
        {/each}
      </ul>

    {:else if stepId === 'confirm'}
      <h2 class="font-display text-3xl text-ink-100 tracking-tightest leading-tight mb-3">
        the day, in three lines.
      </h2>
      <p class="text-ink-400 text-sm mb-8">read it back. commit if it's right.</p>

      <div class="surface rounded-lg p-6 space-y-4">
        <div class="flex items-baseline gap-3">
          <span class="text-frog text-2xl">🐸</span>
          <span class="text-ink-100 text-lg">{frogTitle}</span>
        </div>
        {#if frogNotes}
          <p class="text-ink-500 text-sm pl-9 -mt-2 italic">{frogNotes}</p>
        {/if}
        {#each [support1, support2].filter((s) => s.trim()) as s}
          <div class="flex items-baseline gap-3">
            <span class="text-ink-600">·</span>
            <span class="text-ink-300">{s}</span>
          </div>
        {/each}

        {#if pulledTasks.length}
          <div class="border-t border-ink-700 pt-4">
            <p class="label mb-2">pulled from backlog</p>
            <ul class="text-sm space-y-1">
              {#each pulledTasks as t}
                <li class="text-ink-300">
                  <span class="text-frog">↑</span> {t.title}
                  {#if subtaskChip(t)}<span class="text-ink-600 text-xs ml-2">{subtaskChip(t)}</span>{/if}
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if yest.length}
          <div class="border-t border-ink-700 pt-4 mt-4">
            <p class="label mb-2">yesterday</p>
            <ul class="text-sm space-y-1">
              {#each yest as t}
                <li class="text-ink-500">
                  {#if yestActions[t.id] === 'carry'}<span class="text-frog">→</span>{/if}
                  {#if yestActions[t.id] === 'done'}<span class="text-moss">✓</span>{/if}
                  {#if yestActions[t.id] === 'drop'}<span class="text-rust">×</span>{/if}
                  {t.title}
                  {#if subtaskChip(t)}<span class="text-ink-600 text-xs ml-2">{subtaskChip(t)}</span>{/if}
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>

    {:else}
      <div class="text-center py-24">
        <p class="font-display text-4xl text-ink-100 tracking-tightest leading-none mb-4">
          set.
        </p>
        <p class="text-ink-500 text-sm font-mono">eat the frog first.</p>
      </div>
    {/if}

    {#if err}<p class="text-rust text-sm mt-6">{err}</p>{/if}
  </div>

  {#if stepId !== 'intro' && stepId !== 'confirm' && visibleStep < 5}
    <div class="flex justify-between items-center pt-8 mt-8 border-t border-ink-800">
      <button class="btn-ghost" on:click={back}>← back</button>
      <button class="btn-primary" on:click={next}>next →</button>
    </div>
  {:else if stepId === 'confirm'}
    <div class="flex justify-between items-center pt-8 mt-8 border-t border-ink-800">
      <button class="btn-ghost" on:click={back}>← change something</button>
      <button class="btn-primary" on:click={commit} disabled={saving}>
        {saving ? 'committing…' : 'commit · begin the day'}
      </button>
    </div>
  {/if}
</div>
