<script>
  import '../app.css';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { auth, captures } from '$lib/api.js';

  let user = null;
  let showCapture = false;
  let captureText = '';

  onMount(async () => {
    try {
      user = await auth.me();
    } catch {
      if (!$page.url.pathname.startsWith('/login')) goto('/login');
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  function onKey(e) {
    // Cmd/Ctrl + . opens capture from anywhere
    if ((e.metaKey || e.ctrlKey) && e.key === '.') {
      e.preventDefault();
      showCapture = true;
    }
    if (e.key === 'Escape' && showCapture) showCapture = false;
  }

  async function saveCapture() {
    if (!captureText.trim()) return (showCapture = false);
    await captures.create(captureText.trim());
    captureText = '';
    showCapture = false;
  }
</script>

<div class="min-h-dvh">
  {#if user}
    <header class="border-b border-ink-700/60">
      <nav class="max-w-3xl mx-auto px-5 py-4 flex items-center gap-6 text-sm">
        <a href="/" class="font-display text-lg tracking-tightest text-ink-100">focus</a>
        <a href="/plan" class="text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/plan')}>plan</a>
        <a href="/focus" class="text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/focus')}>focus</a>
        <a href="/dictate" class="text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/dictate')}>dictate</a>
        <a href="/capture" class="text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/capture')}>inbox</a>
        <a href="/review" class="text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/review')}>review</a>
        <span class="ml-auto text-ink-500 font-mono text-xs hidden sm:block">⌘ . capture</span>
      </nav>
    </header>
  {/if}

  <main class="max-w-3xl mx-auto px-5 py-8">
    <slot />
  </main>

  {#if showCapture}
    <div
      class="fixed inset-0 bg-ink-950/85 backdrop-blur-sm flex items-start justify-center pt-32 z-50"
      on:click={() => (showCapture = false)}
    >
      <div class="surface rounded-lg p-5 w-full max-w-lg mx-4" on:click|stopPropagation>
        <p class="label mb-2">capture — drops to inbox, breaks no flow</p>
        <textarea
          class="input min-h-[120px] resize-none font-mono text-sm"
          autofocus
          bind:value={captureText}
          on:keydown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') saveCapture();
          }}
          placeholder="what just pulled at your attention?"
        ></textarea>
        <p class="text-xs text-ink-500 mt-2">
          ⚠ no case data. titles only. ⌘↵ save · esc cancel
        </p>
        <div class="flex justify-end gap-2 mt-3">
          <button class="btn-ghost" on:click={() => (showCapture = false)}>cancel</button>
          <button class="btn-primary" on:click={saveCapture}>save</button>
        </div>
      </div>
    </div>
  {/if}
</div>
