<script>
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { sessions as sessionsApi, tasks as tasksApi } from '$lib/api.js';

  let sessionId = null;
  let taskId = null;
  let task = null;
  let elapsed = 0;
  let durationSec = 1500;
  let timer = null;
  let running = false;
  let elapsedBeforeRun = 0;
  let runStartedAt = null;
  let endChimePlayed = false;
  let showContext = false;
  let subErr = '';
  let breakPrompt = false; // shown after the session has been ended

  // ADHD: variable reward — pick a different end tone each session
  const tones = [528, 432, 396, 639, 741];
  const tone = tones[Math.floor(Math.random() * tones.length)];

  onMount(async () => {
    sessionId = $page.url.searchParams.get('session');
    taskId = $page.url.searchParams.get('task');
    if (!sessionId || !taskId) {
      goto('/plan');
      return;
    }
    const all = await tasksApi.list();
    task = all.find((t) => String(t.id) === String(taskId));
    if (!task) {
      goto('/plan');
      return;
    }

    // Try fullscreen + wake lock for desk focus
    try {
      await document.documentElement.requestFullscreen?.();
    } catch {}
    try {
      if ('wakeLock' in navigator) await navigator.wakeLock.request('screen');
    } catch {}

    document.body.classList.add('focus-mode');
    start();
  });

  onDestroy(() => {
    if (timer) clearInterval(timer);
    document.body.classList.remove('focus-mode');
  });

  function tick() {
    const segMs = runStartedAt ? Date.now() - runStartedAt : 0;
    elapsed = Math.floor((elapsedBeforeRun + segMs) / 1000);
    if (elapsed >= durationSec && !endChimePlayed) {
      endChimePlayed = true;
      playEnd();
    }
  }

  function start() {
    running = true;
    runStartedAt = Date.now();
    timer = setInterval(tick, 250);
  }

  function pause() {
    if (!running) return;
    elapsedBeforeRun += Date.now() - runStartedAt;
    runStartedAt = null;
    running = false;
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function resume() {
    if (running) return;
    runStartedAt = Date.now();
    running = true;
    timer = setInterval(tick, 250);
  }

  function playEnd() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = tone;
      osc.connect(gain);
      gain.connect(ctx.destination);
      gain.gain.setValueAtTime(0, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.15, ctx.currentTime + 0.05);
      gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 1.6);
      osc.start();
      osc.stop(ctx.currentTime + 1.7);
    } catch {}
  }

  async function finish(completed) {
    if (!sessionId) return;
    if (timer) clearInterval(timer);
    timer = null;
    running = false;
    if (sessionId !== 'ended') {
      await sessionsApi.end(sessionId, completed);
      sessionId = 'ended';
    }
    breakPrompt = true;
  }

  async function takeBreak(mins) {
    document.body.classList.remove('focus-mode');
    goto(`/timer?mode=break&d=${mins}`);
  }

  async function backToPlan() {
    document.body.classList.remove('focus-mode');
    if (document.fullscreenElement) await document.exitFullscreen?.();
    goto('/plan');
  }

  $: remaining = Math.max(0, durationSec - elapsed);
  $: mm = String(Math.floor(remaining / 60)).padStart(2, '0');
  $: ss = String(remaining % 60).padStart(2, '0');
  $: progress = Math.min(100, (elapsed / durationSec) * 100);
  $: overtime = elapsed > durationSec;
  $: doneCount = (task?.subtasks || []).filter((s) => s.done).length;

  async function toggleSub(id) {
    if (!task) return;
    const before = task.subtasks;
    const next = task.subtasks.map((s) => (s.id === id ? { ...s, done: !s.done } : s));
    task = { ...task, subtasks: next };
    try {
      const updated = await tasksApi.update(task.id, { subtasks: next });
      task = updated;
      subErr = '';
    } catch (e) {
      task = { ...task, subtasks: before };
      subErr = e?.message || 'subtask save failed';
      setTimeout(() => (subErr = ''), 4000);
    }
  }

  // Body-double nudge: every 12 min, brief check-in
  let nudge = null;
  $: {
    if (running && elapsed > 0 && elapsed % 720 === 0 && task) {
      nudge = `${Math.floor(elapsed / 60)} min in — still on "${task.title}"?`;
      setTimeout(() => (nudge = null), 6000);
    }
  }
</script>

<div class="fixed inset-0 flex flex-col items-center justify-center px-6">
  {#if task}
    <p class="label mb-4 text-ink-500">
      {task.is_frog ? '🐸 frog' : 'focus'}
    </p>
    <h1 class="font-display text-3xl md:text-4xl text-ink-200 text-center tracking-tightest max-w-2xl leading-tight">
      {task.title}
    </h1>

    {#if task.next_action}
      <p class="mt-4 text-ink-300 text-base text-center max-w-xl">
        next move · <span class="text-ink-100">{task.next_action}</span>
      </p>
    {/if}

    <div
      class="font-mono text-[18vw] md:text-[14vw] leading-none mt-12 tabular-nums tracking-tighter"
      class:text-frog={overtime}
      class:text-ink-100={!overtime}
    >
      {mm}:{ss}
    </div>

    <div class="w-full max-w-xl mt-8 h-px bg-ink-800 relative">
      <div
        class="absolute left-0 top-0 h-px bg-frog transition-[width] duration-300"
        style="width: {progress}%"
      ></div>
    </div>

    {#if (task.subtasks || []).length > 0}
      <div class="w-full max-w-xl mt-8">
        <p class="label mb-2">subtasks · {doneCount}/{task.subtasks.length} done</p>
        <ul class="space-y-1.5">
          {#each task.subtasks as s (s.id)}
            <li class="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={s.done}
                on:change={() => toggleSub(s.id)}
              />
              <span class:line-through={s.done} class:text-ink-500={s.done}>{s.title}</span>
            </li>
          {/each}
        </ul>
        {#if subErr}
          <p class="mt-2 text-rust text-xs">{subErr}</p>
        {/if}
      </div>
    {/if}

    {#if nudge}
      <div class="mt-8 text-ink-400 text-sm italic animate-pulse">{nudge}</div>
    {/if}

    {#if breakPrompt}
      <div class="mt-12 flex flex-col items-center gap-3">
        <p class="text-ink-300 text-sm">session ended. take a break?</p>
        <div class="flex flex-wrap gap-3 justify-center">
          <button class="btn-primary" on:click={() => takeBreak(5)}>5 min break</button>
          <button class="btn" on:click={() => takeBreak(10)}>10 min break</button>
          <button class="btn-ghost" on:click={backToPlan}>skip — back to plan</button>
        </div>
      </div>
    {:else}
      <div class="mt-12 flex gap-3">
        <button class="btn" on:click={() => finish(false)}>stop early</button>
        {#if running}
          <button class="btn" on:click={pause}>pause</button>
        {:else}
          <button class="btn" on:click={resume}>resume</button>
        {/if}
        <button class="btn-primary" on:click={() => finish(true)}>finish</button>
      </div>
    {/if}

    {#if task.notes}
      <button
        class="mt-6 text-ink-500 hover:text-ink-200 text-xs font-mono tracking-wider"
        on:click={() => (showContext = !showContext)}
      >
        {showContext ? '✕ hide context' : 'ⓘ context'}
      </button>
    {/if}

    <p class="mt-4 text-xs text-ink-600 font-mono">
      {#if !running}paused{:else if overtime}overtime — finish or stop{:else}screen will not sleep{/if}
    </p>
  {/if}
</div>

{#if showContext && task?.notes}
  <div
    class="fixed inset-0 bg-ink-950/95 backdrop-blur-sm z-40 overflow-auto"
    on:click={() => (showContext = false)}
  >
    <div class="max-w-2xl mx-auto px-6 py-12" on:click|stopPropagation>
      <div class="flex items-center justify-between mb-4">
        <p class="label">context · {task.title}</p>
        <button class="btn-ghost" on:click={() => (showContext = false)}>close ✕</button>
      </div>
      <pre class="text-ink-200 whitespace-pre-wrap font-body text-sm leading-relaxed">{task.notes}</pre>
      <p class="text-xs text-ink-600 mt-6 font-mono">tap anywhere outside to dismiss</p>
    </div>
  </div>
{/if}
