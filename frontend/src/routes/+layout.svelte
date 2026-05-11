<script>
  import '../app.css';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { auth, captures } from '$lib/api.js';
  import { user } from '$lib/stores.js';
  import WelcomeModal from '$lib/WelcomeModal.svelte';

  let showCapture = false;
  let showWelcome = false;
  let captureText = '';
  let menuOpen = false;

  onMount(async () => {
    try {
      const me = await auth.me();
      user.set(me);
      if (!me.welcomed_at && !$page.url.pathname.startsWith('/login')) {
        showWelcome = true;
      }
    } catch {
      user.set(null);
      if (!$page.url.pathname.startsWith('/login')) goto('/login');
    }
    window.addEventListener('keydown', onKey);
    window.addEventListener('click', onWindowClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('click', onWindowClick);
    };
  });

  function onKey(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === '.') {
      e.preventDefault();
      showCapture = true;
    }
    if (e.key === 'Escape') {
      if (showCapture) showCapture = false;
      if (menuOpen) menuOpen = false;
    }
  }

  function onWindowClick(e) {
    if (!menuOpen) return;
    if (!e.target.closest('[data-user-menu]')) menuOpen = false;
  }

  async function saveCapture() {
    if (!captureText.trim()) return (showCapture = false);
    await captures.create(captureText.trim());
    captureText = '';
    showCapture = false;
  }

  function handleWelcomeClose() {
    showWelcome = false;
    user.update((u) => (u ? { ...u, welcomed_at: new Date().toISOString() } : u));
  }

  async function signOut() {
    menuOpen = false;
    try {
      await auth.logout();
    } catch {}
    user.set(null);
    goto('/login');
  }
</script>

<div class="min-h-dvh">
  {#if $user}
    <header class="border-b border-ink-700/60">
      <nav class="max-w-3xl mx-auto px-5 py-4 flex items-center gap-6 text-sm">
        <a href="/" class="flex items-center gap-2 text-ink-100" aria-label="Task Panda — home">
          <img src="/logo-mark.png" alt="" class="h-7 w-7" width="28" height="28" />
          <span class="font-display text-lg tracking-tightest">task panda</span>
        </a>
        <a href="/plan" class="hidden sm:inline text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/plan')}>plan</a>
        <a href="/focus" class="hidden sm:inline text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/focus')}>focus</a>
        <a href="/dictate" class="hidden sm:inline text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/dictate')}>dictate</a>
        <a href="/capture" class="hidden sm:inline text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/capture')}>inbox</a>
        <a href="/review" class="hidden sm:inline text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/review')}>review</a>
        <a href="/settings" class="hidden sm:inline text-ink-400 hover:text-ink-100" class:!text-ink-100={$page.url.pathname.startsWith('/settings')}>settings</a>

        <div class="ml-auto flex items-center gap-4">
          <span class="text-ink-500 font-mono text-xs hidden sm:block">⌘ . capture</span>
          <div class="relative" data-user-menu>
            <button
              class="flex items-center gap-1 text-ink-400 hover:text-ink-100 font-mono text-xs"
              on:click|stopPropagation={() => (menuOpen = !menuOpen)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              <span>{$user.username}</span>
              <span class="text-ink-600">▾</span>
            </button>
            {#if menuOpen}
              <div class="absolute right-0 mt-2 w-44 surface rounded-md py-2 z-40 shadow-lg" role="menu">
                <a
                  href="/settings#security"
                  class="block px-3 py-1.5 text-xs text-ink-300 hover:text-ink-100 hover:bg-ink-800/60"
                  on:click={() => (menuOpen = false)}
                >change password</a>
                <a
                  href="/settings#totp"
                  class="block px-3 py-1.5 text-xs text-ink-300 hover:text-ink-100 hover:bg-ink-800/60"
                  on:click={() => (menuOpen = false)}
                >authenticator</a>
                {#if $user.is_admin}
                  <a
                    href="/admin"
                    class="block px-3 py-1.5 text-xs text-ink-300 hover:text-ink-100 hover:bg-ink-800/60"
                    on:click={() => (menuOpen = false)}
                  >admin</a>
                {/if}
                <button
                  class="block w-full text-left px-3 py-1.5 text-xs text-rust hover:bg-ink-800/60"
                  on:click={signOut}
                >sign out</button>
              </div>
            {/if}
          </div>
        </div>
      </nav>
    </header>
  {/if}

  <main class="max-w-3xl mx-auto px-5 py-8 pb-28 sm:pb-8">
    <slot />
  </main>

  {#if $user}
    <nav
      class="sm:hidden fixed bottom-0 inset-x-0 z-30 border-t border-ink-700/60 bg-ink-950/95 backdrop-blur"
      style="padding-bottom: env(safe-area-inset-bottom)"
      aria-label="primary"
    >
      <div class="flex items-stretch justify-around text-xs">
        <a href="/plan" class="flex-1 text-center py-3 text-ink-400" class:!text-ink-100={$page.url.pathname.startsWith('/plan')}>plan</a>
        <a href="/focus" class="flex-1 text-center py-3 text-ink-400" class:!text-ink-100={$page.url.pathname.startsWith('/focus')}>focus</a>
        <a href="/dictate" class="flex-1 text-center py-3 text-ink-400" class:!text-ink-100={$page.url.pathname.startsWith('/dictate')}>dictate</a>
        <a href="/capture" class="flex-1 text-center py-3 text-ink-400" class:!text-ink-100={$page.url.pathname.startsWith('/capture')}>inbox</a>
        <a href="/review" class="flex-1 text-center py-3 text-ink-400" class:!text-ink-100={$page.url.pathname.startsWith('/review')}>review</a>
      </div>
    </nav>

    <button
      class="sm:hidden fixed right-5 z-30 h-14 w-14 rounded-full bg-frog text-ink-950 text-3xl leading-none font-semibold shadow-lg flex items-center justify-center hover:bg-frog-glow transition"
      style="bottom: calc(4.25rem + env(safe-area-inset-bottom))"
      on:click={() => (showCapture = true)}
      aria-label="capture a thought"
    >+</button>
  {/if}

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
          ⌘↵ save · esc cancel
        </p>
        <div class="flex justify-end gap-2 mt-3">
          <button class="btn-ghost" on:click={() => (showCapture = false)}>cancel</button>
          <button class="btn-primary" on:click={saveCapture}>save</button>
        </div>
      </div>
    </div>
  {/if}

  {#if showWelcome && $user}
    <WelcomeModal bind:open={showWelcome} on:close={handleWelcomeClose} />
  {/if}
</div>
