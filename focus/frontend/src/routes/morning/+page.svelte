<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { morning, localToday } from '$lib/api.js';

  const today = localToday();
  let step = 0; // 0 intro, 1 carry, 2 frog, 3 supporting, 4 confirm, 5 done
  let yest = [];
  let yestActions = {}; // task_id -> 'carry'|'drop'|'done'|null
  let todayExisting = [];
  let frogTitle = '';
  let frogNotes = '';
  let support1 = '';
  let support2 = '';
  let saving = false;
  let err = '';

  onMount(async () => {
    try {
      const s = await morning.state(today);
      if (s.ritual_done) {
        goto('/plan', { replaceState: true });
        return;
      }
      yest = s.yesterday_open || [];
      todayExisting = s.today_existing || [];

      // Default actions: yesterday's frog → carry, others → null (forces decision)
      yestActions = Object.fromEntries(
        yest.map((t) => [t.id, t.is_frog ? 'carry' : null])
      );

      // If a frog is already set for today, pre-fill it
      const existingFrog = todayExisting.find((t) => t.is_frog);
      if (existingFrog) frogTitle = existingFrog.title;
    } catch (e) {
      err = e.message;
    }
  });

  function next() {
    if (step === 1 && yest.some((t) => !yestActions[t.id])) {
      err = 'Decide on each carry-over before continuing.';
      return;
    }
    if (step === 2 && !frogTitle.trim()) {
      err = 'Pick a frog. The boring, important one.';
      return;
    }
    err = '';
    step += 1;
  }

  function back() {
    err = '';
    step = Math.max(0, step - 1);
  }

  async function commit() {
    saving = true;
    err = '';
    try {
      await morning.complete({
        today_date: today,
        yesterday_actions: yest
          .filter((t) => yestActions[t.id])
          .map((t) => ({ task_id: t.id, action: yestActions[t.id] })),
        frog_title: frogTitle.trim(),
        frog_notes: frogNotes.trim() || null,
        supporting_titles: [support1, support2].filter((s) => s.trim())
      });
      step = 5;
      // small pause for the user to read the closing line, then plan
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

  $: dateLine = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric'
  });
</script>

<div class="max-w-2xl mx-auto pt-4 pb-20 min-h-[80vh] flex flex-col">
  <!-- Step indicator -->
  {#if step > 0 && step < 5}
    <div class="flex items-center gap-2 mb-12">
      {#each [1, 2, 3, 4] as n}
        <div
          class="h-px flex-1 transition-colors"
          class:bg-frog={step >= n}
          class:bg-ink-700={step < n}
        ></div>
      {/each}
      <span class="text-ink-500 font-mono text-xs ml-2">{step}/4</span>
    </div>
  {/if}

  <div class="flex-1">
    <!-- Step 0: intro -->
    {#if step === 0}
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

    <!-- Step 1: carry-forward -->
    {:else if step === 1}
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
              <p class="text-ink-100 mb-3">
                {t.is_frog ? '🐸 ' : ''}{t.title}
              </p>
              <div class="flex gap-2 flex-wrap">
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

    <!-- Step 2: frog -->
    {:else if step === 2}
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
          placeholder="e.g. Q3 inspection report — keep it abstract"
          bind:value={frogTitle}
          on:keydown={(e) => e.key === 'Enter' && next()}
        />
        <textarea
          class="input text-sm font-mono min-h-[80px] resize-none"
          placeholder="optional notes — what's the actual blocker?"
          bind:value={frogNotes}
        ></textarea>
        <p class="text-xs text-ink-600">
          ⚠ no case data. abstractions only.
        </p>
      </div>

    <!-- Step 3: supporting -->
    {:else if step === 3}
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

    <!-- Step 4: confirm -->
    {:else if step === 4}
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
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>

    <!-- Step 5: done -->
    {:else if step === 5}
      <div class="text-center py-24">
        <p class="font-display text-4xl text-ink-100 tracking-tightest leading-none mb-4">
          set.
        </p>
        <p class="text-ink-500 text-sm font-mono">eat the frog first.</p>
      </div>
    {/if}

    {#if err}<p class="text-rust text-sm mt-6">{err}</p>{/if}
  </div>

  <!-- Step nav -->
  {#if step > 0 && step < 4}
    <div class="flex justify-between items-center pt-8 mt-8 border-t border-ink-800">
      <button class="btn-ghost" on:click={back}>← back</button>
      <button class="btn-primary" on:click={next}>next →</button>
    </div>
  {:else if step === 4}
    <div class="flex justify-between items-center pt-8 mt-8 border-t border-ink-800">
      <button class="btn-ghost" on:click={back}>← change something</button>
      <button class="btn-primary" on:click={commit} disabled={saving}>
        {saving ? 'committing…' : 'commit · begin the day'}
      </button>
    </div>
  {/if}
</div>
