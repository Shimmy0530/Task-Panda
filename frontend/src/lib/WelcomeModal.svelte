<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { auth } from '$lib/api.js';

  export let open = false;
  export let replay = false;

  const dispatch = createEventDispatcher();

  let step = 0;
  let dismissing = false;

  const steps = [
    {
      icon: '🌅',
      title: 'Start with the morning ritual',
      body: `Each morning, the Ritual screen helps you set the day. Pick up to 5 tasks and mark one "do first." For anything you didn't finish yesterday, you decide what to pull forward, drop, or mark done — and you can pull items in from the backlog too.`
    },
    {
      icon: '📋',
      title: 'The Plan screen keeps your day small',
      body: `Plan shows today's 5 tasks with the "do first" one called out. Anything beyond 5 lives in the backlog until you graduate it forward.`
    },
    {
      icon: '🍅',
      title: 'Focus runs a 25-minute timer',
      body: `The Focus screen starts a 25-minute timer on whichever task you choose — and you can switch tasks or take a break whenever you want. You can also dictate notes by voice while you work.`
    },
    {
      icon: '💡',
      title: 'Capture catches stray thoughts',
      body: `Hit ⌘ . (or the + button on mobile) anywhere in the app to drop a thought into your inbox. Triage it later — don't break flow now.`
    }
  ];

  $: isLast = step === steps.length - 1;

  async function dismiss({ goMorning } = { goMorning: false }) {
    if (dismissing) return;
    dismissing = true;
    try {
      if (!replay) {
        try { await auth.welcome(); } catch {}
      }
      if (goMorning) await goto('/morning');
    } finally {
      open = false;
      step = 0;
      dismissing = false;
      dispatch('close');
    }
  }

  function next() {
    if (isLast) dismiss({ goMorning: true });
    else step += 1;
  }

  function back() {
    if (step > 0) step -= 1;
  }

  function onKey(e) {
    if (!open) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      dismiss();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      next();
    }
  }

  onMount(() => window.addEventListener('keydown', onKey));
  onDestroy(() => window.removeEventListener('keydown', onKey));
</script>

{#if open}
  <div
    class="fixed inset-0 bg-ink-950/85 backdrop-blur-sm flex items-start justify-center pt-24 z-50"
    on:click={() => dismiss()}
  >
    <div
      class="surface rounded-lg p-6 w-full max-w-lg mx-4"
      on:click|stopPropagation
      role="dialog"
      aria-modal="true"
      aria-labelledby="welcome-title"
    >
      <div class="text-5xl text-center mb-3" aria-hidden="true">{steps[step].icon}</div>
      <h2 id="welcome-title" class="font-display text-xl text-ink-100 text-center mb-2">
        {steps[step].title}
      </h2>
      <p class="text-sm text-ink-300 leading-relaxed text-center mb-6">
        {steps[step].body}
      </p>

      <div class="flex items-center justify-between text-xs">
        <button
          class="text-ink-500 hover:text-ink-300 underline-offset-2 hover:underline"
          on:click={() => dismiss()}
          disabled={dismissing}
        >skip tour</button>

        <span class="font-mono text-ink-500">{step + 1} / {steps.length}</span>

        <div class="flex items-center gap-2">
          <button
            class="btn-ghost text-xs"
            on:click={back}
            disabled={step === 0 || dismissing}
          >back</button>
          <button
            class="btn-primary text-xs"
            on:click={next}
            disabled={dismissing}
          >
            {#if isLast}start your morning ritual{:else}next{/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
