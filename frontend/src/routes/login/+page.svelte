<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { auth, validateNewPassword } from '$lib/api.js';
  import { user } from '$lib/stores.js';

  // 'loading' | 'signup' (first-run admin) | 'login' | 'register' (open signup, pending)
  let mode = 'loading';
  let username = '';
  let password = '';
  let confirm = '';
  let totpCode = '';
  let showTotp = false;
  let busy = false;
  let err = '';
  let pendingNotice = '';

  onMount(async () => {
    try {
      const me = await auth.me();
      user.set(me);
      goto('/plan', { replaceState: true });
      return;
    } catch {
      user.set(null);
    }

    try {
      const r = await auth.setupRequired();
      mode = r.setup_required ? 'signup' : 'login';
    } catch {
      mode = 'login';
    }
  });

  function switchMode(next) {
    err = '';
    pendingNotice = '';
    password = '';
    confirm = '';
    totpCode = '';
    showTotp = false;
    mode = next;
  }

  async function submit() {
    if (busy) return;
    err = '';

    if (mode === 'signup') {
      const v = validateNewPassword(password, confirm);
      if (v) { err = v; return; }
      busy = true;
      try {
        const r = await auth.setup(username.trim(), password);
        user.set(r.user);
        goto('/plan');
      } catch (e) {
        err = e.message || 'Sign up failed';
      } finally {
        busy = false;
      }
      return;
    }

    if (mode === 'register') {
      const v = validateNewPassword(password, confirm);
      if (v) { err = v; return; }
      busy = true;
      try {
        await auth.register(username.trim(), password);
        pendingNotice = `Account requested for "${username.trim()}". An admin needs to approve it before you can sign in.`;
        switchMode('login');
      } catch (e) {
        err = e.message || 'Registration failed';
      } finally {
        busy = false;
      }
      return;
    }

    busy = true;
    try {
      const r = await auth.login(username.trim(), password, totpCode || null);
      user.set(r.user);
      goto('/plan');
    } catch (e) {
      err = e.message || 'Sign in failed';
      totpCode = '';
    } finally {
      busy = false;
    }
  }

  $: needsConfirm = mode === 'signup' || mode === 'register';
  $: canSubmit = needsConfirm
    ? username.trim() && password && confirm
    : username.trim() && password;
</script>

<div class="max-w-md mx-auto pt-24">
  <img
    src="/logo.png"
    alt="Task Panda"
    class="w-56 mb-6 -ml-3"
    width="480"
    height="320"
  />

  {#if mode === 'loading'}
    <p class="text-ink-500 text-sm">…</p>
  {:else if mode === 'signup'}
    <p class="label mb-1">first run</p>
    <h1 class="font-display text-2xl text-ink-100 tracking-tightest leading-none mb-3">create the admin account.</h1>
    <p class="text-ink-400 mb-8 leading-relaxed text-sm">
      No accounts exist yet. The first sign-up here becomes the admin and can approve other users from the admin page later.
    </p>
  {:else if mode === 'register'}
    <p class="label mb-1">request access</p>
    <h1 class="font-display text-2xl text-ink-100 tracking-tightest leading-none mb-3">create an account.</h1>
    <p class="text-ink-400 mb-8 leading-relaxed text-sm">
      Pick a username and password. An admin will review and approve before you can sign in.
    </p>
  {:else}
    <p class="text-ink-400 mb-10 leading-relaxed">
      A quiet observatory for the work you keep avoiding.
    </p>
  {/if}

  {#if mode !== 'loading'}
    {#if pendingNotice}
      <p class="text-moss text-sm mb-6 leading-relaxed">{pendingNotice}</p>
    {/if}

    <div class="space-y-4">
      <div>
        <label class="label block mb-1.5" for="un">username</label>
        <input
          id="un"
          type="text"
          autocomplete="username"
          class="input"
          bind:value={username}
          on:keydown={(e) => e.key === 'Enter' && submit()}
          autofocus
        />
      </div>

      <div>
        <label class="label block mb-1.5" for="pw">password</label>
        <input
          id="pw"
          type="password"
          autocomplete={needsConfirm ? 'new-password' : 'current-password'}
          class="input"
          bind:value={password}
          on:keydown={(e) => e.key === 'Enter' && submit()}
        />
        {#if needsConfirm}
          <p class="text-ink-600 text-xs mt-1">at least 12 characters</p>
        {/if}
      </div>

      {#if needsConfirm}
        <div>
          <label class="label block mb-1.5" for="cf">confirm password</label>
          <input
            id="cf"
            type="password"
            autocomplete="new-password"
            class="input"
            bind:value={confirm}
            on:keydown={(e) => e.key === 'Enter' && submit()}
          />
        </div>
      {:else if showTotp}
        <div>
          <label class="label block mb-1.5" for="totp">2fa code</label>
          <input
            id="totp"
            type="text"
            inputmode="numeric"
            pattern="[0-9]*"
            maxlength="6"
            autocomplete="one-time-code"
            class="input font-mono tracking-widest text-center"
            placeholder="000000"
            bind:value={totpCode}
            on:keydown={(e) => e.key === 'Enter' && submit()}
          />
        </div>
      {:else}
        <button
          type="button"
          class="text-xs text-ink-500 hover:text-ink-300"
          on:click={() => (showTotp = true)}
        >
          I have a 2fa code →
        </button>
      {/if}

      {#if err}
        <p class="text-rust text-sm">{err}</p>
      {/if}

      <button
        class="btn-primary w-full"
        on:click={submit}
        disabled={busy || !canSubmit}
      >
        {#if busy}
          {#if mode === 'signup'}creating account…
          {:else if mode === 'register'}submitting…
          {:else}signing in…
          {/if}
        {:else}
          {#if mode === 'signup'}create admin account
          {:else if mode === 'register'}request account
          {:else}sign in
          {/if}
        {/if}
      </button>

      {#if mode === 'login'}
        <p class="text-ink-500 text-xs text-center pt-1">
          new here?
          <button
            type="button"
            class="text-ink-300 hover:text-ink-100 underline-offset-2 hover:underline"
            on:click={() => switchMode('register')}
          >request an account</button>
        </p>
      {:else if mode === 'register'}
        <p class="text-ink-500 text-xs text-center pt-1">
          already have one?
          <button
            type="button"
            class="text-ink-300 hover:text-ink-100 underline-offset-2 hover:underline"
            on:click={() => switchMode('login')}
          >sign in</button>
        </p>
      {/if}
    </div>
  {/if}
</div>
