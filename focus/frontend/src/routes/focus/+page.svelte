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
  let endChimePlayed = false;
  let showContext = false;

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

  function start() {
    running = true;
    const t0 = Date.now();
    timer = setInterval(() => {
      elapsed = Math.floor((Date.now() - t0) / 1000);
      if (elapsed >= durationSec && !endChimePlayed) {
        endChimePlayed = true;
        playEnd();
      }
    }, 250);
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
    await sessionsApi.end(sessionId, completed);
    if (completed) {
      // Mark frog done? leave to user — show review
    }
    document.body.classList.remove('focus-mode');
    if (document.fullscreenElement) await document.exitFullscreen?.();
    goto('/plan');
  }

  $: remaining = Math.max(0, durationSec - elapsed);
  $: mm = String(Math.floor(remaining / 60)).padStart(2, '0');
  $: ss = String(remaining % 60).padStart(2, '0');
  $: progress = Math.min(100, (elapsed / durationSec) * 100);
  $: overtime = elapsed > durationSec;

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

    {#if nudge}
      <div class="mt-8 text-ink-400 text-sm italic animate-pulse">{nudge}</div>
    {/if}

    <div class="mt-12 flex gap-3">
      <button class="btn" on:click={() => finish(false)}>stop early</button>
      <button class="btn-primary" on:click={() => finish(true)}>finish</button>
    </div>

    {#if task.notes}
      <button
        class="mt-6 text-ink-500 hover:text-ink-200 text-xs font-mono tracking-wider"
        on:click={() => (showContext = !showContext)}
      >
        {showContext ? '✕ hide context' : 'ⓘ context'}
      </button>
    {/if}

    <p class="mt-4 text-xs text-ink-600 font-mono">
      {overtime ? 'overtime — finish or stop' : 'screen will not sleep'}
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
