<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { auth } from '$lib/api.js';

  let password = '';
  let totpCode = '';
  let totpRequired = false;
  let busy = false;
  let err = '';

  onMount(async () => {
    // If already signed in, bounce to plan
    try {
      await auth.me();
      goto('/plan', { replaceState: true });
      return;
    } catch {}

    try {
      const cfg = await auth.config();
      totpRequired = !!cfg.totp_required;
    } catch {}
  });

  async function submit() {
    if (busy) return;
    busy = true;
    err = '';
    try {
      await auth.login(password, totpCode || null);
      goto('/plan');
    } catch (e) {
      err = e.message || 'Sign in failed';
      // wipe the code on failure so re-entry is clean; keep password
      totpCode = '';
    } finally {
      busy = false;
    }
  }
</script>

<div class="max-w-md mx-auto pt-24">
  <img
    src="/logo.png"
    alt="Task Panda"
    class="w-56 mb-6 -ml-3"
    width="480"
    height="320"
  />
  <p class="text-ink-400 mb-10 leading-relaxed">
    A quiet observatory for the work you keep avoiding.
  </p>

  <!-- Hidden username field for password manager autofill -->
  <input type="text" name="username" autocomplete="username" value="owner" class="hidden" />

  <div class="space-y-4">
    <div>
      <label class="label block mb-1.5" for="pw">password</label>
      <input
        id="pw"
        type="password"
        autocomplete="current-password"
        class="input"
        bind:value={password}
        on:keydown={(e) => e.key === 'Enter' && submit()}
        autofocus
      />
    </div>

    {#if totpRequired}
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
    {/if}

    {#if err}
      <p class="text-rust text-sm">{err}</p>
    {/if}

    <button
      class="btn-primary w-full"
      on:click={submit}
      disabled={busy || !password || (totpRequired && totpCode.length !== 6)}
    >
      {busy ? 'signing in…' : 'sign in'}
    </button>
  </div>
</div>
