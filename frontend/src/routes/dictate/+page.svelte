<script>
  import { onDestroy, onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { tasks as tasksApi, sessions as sessionsApi } from '$lib/api.js';

  let boundTask = null;            // task object if ?task=<id>
  let allTasks = [];               // today's tasks for the picker
  let selectedTaskId = null;       // for picker mode

  let recorder = null;
  let stream = null;
  let chunks = [];
  let recording = false;
  let elapsed = 0;
  let timer = null;
  let processing = false;
  let transcript = '';
  let outline = '';
  let outlining = false;
  let saving = false;
  let saved = false;
  let err = '';
  let levelMeter = 0;
  let audioCtx = null;
  let analyser = null;
  let levelRaf = null;

  onMount(async () => {
    const tid = $page.url.searchParams.get('task');
    if (tid) {
      try {
        boundTask = await tasksApi.get(tid);
        selectedTaskId = boundTask.id;
      } catch {
        boundTask = null;
      }
    }
    allTasks = await tasksApi.list();
  });

  async function start() {
    err = '';
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      const mimes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
      const mime = mimes.find((m) => MediaRecorder.isTypeSupported?.(m)) || '';
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
      chunks = [];
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.push(e.data);
      };
      recorder.onstop = () => process(mime);
      recorder.start(1000);
      recording = true;
      const t0 = Date.now();
      timer = setInterval(() => {
        elapsed = Math.floor((Date.now() - t0) / 1000);
        if (elapsed >= 600) stop();
      }, 250);

      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(stream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        levelMeter = Math.min(1, Math.sqrt(sum / buf.length) * 3);
        levelRaf = requestAnimationFrame(tick);
      };
      tick();
    } catch (e) {
      err = `Mic error: ${e.message}`;
    }
  }

  function stop() {
    if (recorder && recording) {
      recorder.stop();
      stream?.getTracks().forEach((t) => t.stop());
      recording = false;
      clearInterval(timer);
      cancelAnimationFrame(levelRaf);
      audioCtx?.close();
      levelMeter = 0;
    }
  }

  async function process(mime) {
    processing = true;
    err = '';
    try {
      const blob = new Blob(chunks, { type: mime || 'audio/webm' });
      if (blob.size === 0) {
        err = 'No audio captured.';
        return;
      }
      if (blob.size > 25 * 1024 * 1024) {
        err = 'Recording too large (>25 MB).';
        return;
      }
      const fd = new FormData();
      const ext = (mime || 'audio/webm').includes('mp4') ? 'm4a' : 'webm';
      fd.append('file', blob, `dictation.${ext}`);
      const res = await fetch('/api/transcribe', {
        method: 'POST',
        credentials: 'include',
        body: fd
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || res.statusText);
      }
      const data = await res.json();
      transcript = data.transcript || '';
    } catch (e) {
      err = e.message;
    } finally {
      processing = false;
    }
  }

  async function makeOutline() {
    outlining = true;
    err = '';
    try {
      const res = await fetch('/api/outline', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript,
          task_id: selectedTaskId || boundTask?.id || null
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'failed');
      outline = data.outline;
    } catch (e) {
      err = e.message;
    } finally {
      outlining = false;
    }
  }

  async function saveToTask() {
    const tid = selectedTaskId || boundTask?.id;
    if (!tid) {
      err = 'Pick a task first.';
      return;
    }
    saving = true;
    err = '';
    try {
      await tasksApi.appendDictation(tid, outline, transcript);
      saved = true;
    } catch (e) {
      err = e.message;
    } finally {
      saving = false;
    }
  }

  async function saveAndFocus(minutes) {
    await saveToTask();
    if (!err) {
      const tid = selectedTaskId || boundTask?.id;
      const s = await sessionsApi.start(tid, minutes * 60);
      goto(`/focus?session=${s.id}&task=${tid}`);
    }
  }

  function copy(text) {
    navigator.clipboard.writeText(text);
  }

  function reset() {
    transcript = '';
    outline = '';
    elapsed = 0;
    chunks = [];
    err = '';
    saved = false;
  }

  onDestroy(() => {
    if (timer) clearInterval(timer);
    if (levelRaf) cancelAnimationFrame(levelRaf);
    stream?.getTracks().forEach((t) => t.stop());
    audioCtx?.close();
  });

  $: mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
  $: ss = String(elapsed % 60).padStart(2, '0');
  $: pickerOptions = allTasks.filter((t) => t.status !== 'done');
</script>

<div class="space-y-6">
  <header>
    <p class="label mb-2">dictate</p>
    <h1 class="font-display text-3xl text-ink-100 tracking-tightest">talk it out</h1>
    {#if boundTask}
      <div class="mt-3 flex items-baseline gap-2 flex-wrap">
        <span class="text-ink-500 text-sm">working on:</span>
        <span class="font-display text-xl text-ink-100">{boundTask.title}</span>
        {#if boundTask.is_frog}<span class="text-frog text-xs">🐸 frog</span>{/if}
      </div>
    {:else}
      <p class="text-ink-400 text-sm mt-2 leading-relaxed">
        Ramble for a few minutes. Get back a structured outline you can save to a task.
      </p>
    {/if}
  </header>

  {#if !transcript && !processing}
    <div class="surface rounded-lg p-10 flex flex-col items-center">
      <button
        class="relative w-32 h-32 rounded-full transition-all flex items-center justify-center text-4xl text-ink-950 select-none"
        class:bg-frog={!recording}
        class:bg-rust={recording}
        on:click={recording ? stop : start}
        aria-label={recording ? 'stop' : 'start'}
      >
        {#if recording}
          <span
            class="absolute inset-0 rounded-full bg-rust/30"
            style="transform: scale({1 + levelMeter * 0.6}); transition: transform 60ms;"
          ></span>
        {/if}
        <span class="relative z-10">{recording ? '■' : '●'}</span>
      </button>
      <p class="font-mono text-3xl mt-8 text-ink-100 tabular-nums">{mm}:{ss}</p>
      <p class="text-xs text-ink-500 mt-2 font-mono">
        {recording ? 'recording — tap to stop · 10 min cap' : 'tap to start'}
      </p>
      {#if err}<p class="text-rust text-sm mt-4">{err}</p>{/if}
    </div>
  {/if}

  {#if processing}
    <div class="surface rounded-lg p-10 text-center">
      <p class="font-mono text-ink-400 animate-pulse">transcribing…</p>
    </div>
  {/if}

  {#if transcript}
    <section class="space-y-5">
      <div class="surface rounded-lg p-5">
        <div class="flex items-center justify-between mb-3">
          <p class="label">transcript</p>
          <div class="flex gap-1">
            <button class="btn-ghost text-xs" on:click={() => copy(transcript)}>copy</button>
            <button class="btn-ghost text-xs" on:click={reset}>discard</button>
          </div>
        </div>
        <textarea
          class="input min-h-[160px] font-mono text-sm leading-relaxed"
          bind:value={transcript}
        ></textarea>
        <p class="text-xs text-ink-600 mt-2">edit before outlining if you want to scrub anything.</p>
      </div>

      {#if !outline}
        <div class="flex justify-center">
          <button class="btn-primary" on:click={makeOutline} disabled={outlining}>
            {outlining ? 'thinking…' : 'turn this into an outline'}
          </button>
        </div>
      {/if}

      {#if outline}
        <div class="surface rounded-lg p-5 border-frog/30">
          <div class="flex items-center justify-between mb-3">
            <p class="label">outline</p>
            <button class="btn-ghost text-xs" on:click={() => copy(outline)}>copy</button>
          </div>
          <pre class="text-ink-100 whitespace-pre-wrap font-body text-sm leading-relaxed">{outline}</pre>
        </div>

        {#if saved}
          <div class="border border-moss/40 bg-moss/10 rounded-md p-4 text-sm">
            <p class="text-moss font-mono text-xs tracking-widest uppercase mb-1">saved</p>
            <p class="text-ink-200">
              Outline appended to <strong>{boundTask?.title || allTasks.find(t => t.id === selectedTaskId)?.title}</strong>'s notes.
            </p>
            <div class="flex gap-2 mt-3">
              <a href="/plan" class="btn">back to plan</a>
              <button class="btn-primary" on:click={() => saveAndFocus(25)}>focus 25 now</button>
            </div>
          </div>
        {:else}
          <div class="surface rounded-md p-5 space-y-3">
            {#if !boundTask}
              <div>
                <label class="label block mb-2">save to task</label>
                {#if pickerOptions.length === 0}
                  <p class="text-ink-500 text-sm italic">No open tasks today. <a href="/plan" class="text-frog">add one</a> first.</p>
                {:else}
                  <select class="input" bind:value={selectedTaskId}>
                    <option value={null}>— pick a task —</option>
                    {#each pickerOptions as t}
                      <option value={t.id}>{t.is_frog ? '🐸 ' : ''}{t.title}</option>
                    {/each}
                  </select>
                {/if}
              </div>
            {/if}

            <div class="flex flex-wrap gap-2 justify-end">
              <button class="btn" on:click={reset}>discard</button>
              <button class="btn" on:click={saveToTask} disabled={saving || !(boundTask || selectedTaskId)}>
                {saving ? 'saving…' : 'save to task'}
              </button>
              <button
                class="btn-primary"
                on:click={() => saveAndFocus(25)}
                disabled={saving || !(boundTask || selectedTaskId)}
              >
                save + focus 25
              </button>
            </div>
          </div>
        {/if}
      {/if}

      {#if err}<p class="text-rust text-sm">{err}</p>{/if}
    </section>
  {/if}
</div>
