<script>
  import { onMount } from 'svelte';
  import { sessions, llm } from '$lib/api.js';

  let today = null;
  let week = [];
  let summary = '';
  let summaryBusy = false;
  let summaryErr = '';

  onMount(async () => {
    today = await sessions.today();
    week = await sessions.week();
  });

  function fmt(secs) {
    const m = Math.round(secs / 60);
    if (m < 60) return `${m}m`;
    return `${Math.floor(m / 60)}h ${m % 60}m`;
  }

  async function generateSummary() {
    summaryBusy = true;
    summaryErr = '';
    try {
      const r = await llm.weeklyReview();
      summary = r.summary;
    } catch (e) {
      summaryErr = e.message;
    } finally {
      summaryBusy = false;
    }
  }

  // Tiny safe markdown renderer for trusted, short server output:
  // - lines starting with `## ` become h3
  // - lines starting with `- ` group into <ul>
  // - blank lines split paragraphs
  function renderSummary(md) {
    const lines = md.split('\n');
    const out = [];
    let listOpen = false;
    const closeList = () => {
      if (listOpen) {
        out.push('</ul>');
        listOpen = false;
      }
    };
    const esc = (s) => s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    let para = [];
    const flushPara = () => {
      if (para.length) {
        out.push(`<p class="text-ink-200 text-sm leading-relaxed mb-3">${esc(para.join(' '))}</p>`);
        para = [];
      }
    };
    for (const raw of lines) {
      const line = raw.trim();
      if (!line) {
        flushPara();
        closeList();
        continue;
      }
      if (line.startsWith('## ')) {
        flushPara();
        closeList();
        out.push(`<h3 class="label mt-4 mb-2">${esc(line.slice(3))}</h3>`);
      } else if (line.startsWith('- ')) {
        flushPara();
        if (!listOpen) {
          out.push('<ul class="space-y-1 mb-3 list-disc list-inside text-ink-200 text-sm">');
          listOpen = true;
        }
        out.push(`<li>${esc(line.slice(2))}</li>`);
      } else {
        closeList();
        para.push(line);
      }
    }
    flushPara();
    closeList();
    return out.join('\n');
  }

  $: maxWeek = Math.max(1, ...week.map((d) => d.total_seconds));
  $: hasWeekData = week.some((d) => d.total_seconds > 0);
</script>

<div class="space-y-10">
  <header>
    <p class="label mb-2">review</p>
    <h1 class="font-display text-3xl text-ink-100 tracking-tightest">where the time went</h1>
  </header>

  {#if today}
    <section class="surface rounded-lg p-5">
      <p class="label mb-3">today</p>
      <div class="grid grid-cols-3 gap-6 font-mono">
        <div>
          <div class="text-3xl text-ink-100">{fmt(today.total_seconds)}</div>
          <div class="text-xs text-ink-500 mt-1">total focused</div>
        </div>
        <div>
          <div class="text-3xl text-frog">{fmt(today.frog_seconds)}</div>
          <div class="text-xs text-ink-500 mt-1">on the frog</div>
        </div>
        <div>
          <div class="text-3xl text-ink-200">{Math.round(today.frog_ratio * 100)}%</div>
          <div class="text-xs text-ink-500 mt-1">frog ratio</div>
        </div>
      </div>
      {#if today.total_seconds > 0 && today.frog_ratio < 0.3}
        <p class="text-rust text-sm mt-4 italic">
          Less than 30% on the frog. The interesting work won today.
        </p>
      {:else if today.frog_ratio >= 0.5}
        <p class="text-moss text-sm mt-4 italic">
          Frog majority. Good day.
        </p>
      {/if}
    </section>
  {/if}

  {#if hasWeekData}
    <section>
      <p class="label mb-3">this week, in review</p>
      {#if !summary}
        <button class="btn" on:click={generateSummary} disabled={summaryBusy}>
          {summaryBusy ? 'thinking…' : '✨ generate this week\'s summary'}
        </button>
        {#if summaryErr}<p class="text-rust text-xs mt-2">{summaryErr}</p>{/if}
      {:else}
        <div class="surface rounded-lg p-5">
          {@html renderSummary(summary)}
        </div>
        <button class="btn-ghost text-xs mt-2" on:click={() => (summary = '')}>regenerate</button>
      {/if}
    </section>
  {/if}

  <section>
    <p class="label mb-3">last 7 days</p>
    <div class="space-y-1">
      {#each week as d}
        <div class="flex items-center gap-3 text-sm font-mono">
          <span class="text-ink-500 w-20">{new Date(d.day + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'numeric', day: 'numeric' })}</span>
          <div class="flex-1 h-6 bg-ink-900 rounded relative overflow-hidden">
            {#if d.total_seconds > 0}
              <div
                class="absolute left-0 top-0 h-full bg-ink-700"
                style="width: {(d.total_seconds / maxWeek) * 100}%"
              ></div>
              <div
                class="absolute left-0 top-0 h-full bg-frog"
                style="width: {(d.frog_seconds / maxWeek) * 100}%"
              ></div>
            {/if}
          </div>
          <span class="text-ink-400 w-20 text-right">{fmt(d.total_seconds)}</span>
        </div>
      {/each}
    </div>
    <p class="text-xs text-ink-600 mt-3">
      <span class="text-frog">amber</span> = frog · <span class="text-ink-400">grey</span> = other
    </p>
  </section>
</div>
