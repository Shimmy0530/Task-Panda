<script>
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';

  let durationSec = 300;
  let mode = 'timer'; // 'timer' | 'break'
  let label = '';
  let elapsed = 0;
  let timer = null;
  let running = false;
  let elapsedBeforeRun = 0;
  let runStartedAt = null;
  let endChimePlayed = false;
  let wakeLock = null;

  const tones = [528, 432, 396, 639, 741];
  const tone = tones[Math.floor(Math.random() * tones.length)];

  function clampMins(n) {
    if (!Number.isFinite(n)) return 5;
    return Math.max(1, Math.min(120, Math.round(n)));
  }

  onMount(async () => {
    const m = $page.url.searchParams.get('mode');
    if (m === 'break') mode = 'break';
    const d = parseInt($page.url.searchParams.get('d') || '', 10);
    const defaultMins = mode === 'break' ? 5 : 15;
    const mins = Number.isFinite(d) ? clampMins(d) : defaultMins;
    durationSec = mins * 60;
    label = $page.url.searchParams.get('label') || '';

    try {
      await document.documentElement.requestFullscreen?.();
    } catch {}
    try {
      if ('wakeLock' in navigator) wakeLock = await navigator.wakeLock.request('screen');
    } catch {}

    document.body.classList.add('focus-mode');
    start();
  });

  onDestroy(() => {
    if (timer) clearInterval(timer);
    document.body.classList.remove('focus-mode');
    try { wakeLock?.release(); } catch {}
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

  function extend(extraMins) {
    durationSec += extraMins * 60;
    endChimePlayed = false;
    if (!running) resume();
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

  async function exit() {
    if (timer) clearInterval(timer);
    document.body.classList.remove('focus-mode');
    if (document.fullscreenElement) await document.exitFullscreen?.();
    goto('/plan');
  }

  $: remaining = Math.max(0, durationSec - elapsed);
  $: mm = String(Math.floor(remaining / 60)).padStart(2, '0');
  $: ss = String(remaining % 60).padStart(2, '0');
  $: progress = Math.min(100, (elapsed / durationSec) * 100);
  $: overtime = elapsed > durationSec;
  $: totalMins = Math.round(durationSec / 60);
  $: heading = label
    ? label
    : mode === 'break'
      ? `${totalMins} min · step away`
      : `${totalMins} min · timer`;
  $: footnote = !running
    ? 'paused'
    : overtime
      ? 'overtime'
      : mode === 'break'
        ? 'stretch · water · look out a window'
        : 'screen will not sleep';
</script>

<div class="fixed inset-0 flex flex-col items-center justify-center px-6">
  <p class="label mb-4 text-ink-500">{mode === 'break' ? 'break' : 'timer'}</p>
  <h1 class="font-display text-3xl md:text-4xl text-ink-200 text-center tracking-tightest max-w-2xl leading-tight">
    {heading}
  </h1>

  <div
    class="font-mono text-[18vw] md:text-[14vw] leading-none mt-12 tabular-nums tracking-tighter"
    class:text-frog={overtime}
    class:text-moss={!overtime && mode === 'break'}
    class:text-ink-100={!overtime && mode !== 'break'}
  >
    {mm}:{ss}
  </div>

  <div class="w-full max-w-xl mt-8 h-px bg-ink-800 relative">
    <div
      class="absolute left-0 top-0 h-px transition-[width] duration-300"
      class:bg-moss={mode === 'break'}
      class:bg-frog={mode !== 'break'}
      style="width: {progress}%"
    ></div>
  </div>

  {#if overtime && mode === 'break'}
    <p class="mt-8 text-ink-300 text-sm italic">break's up — head back when you're ready.</p>
  {/if}

  <div class="mt-12 flex flex-wrap gap-3 justify-center">
    {#if running}
      <button class="btn" on:click={pause}>pause</button>
    {:else}
      <button class="btn" on:click={resume}>resume</button>
    {/if}
    <button class="btn" on:click={() => extend(5)}>+5 min</button>
    <button class="btn-primary" on:click={exit}>back to plan</button>
  </div>

  <p class="mt-4 text-xs text-ink-600 font-mono">{footnote}</p>
</div>
