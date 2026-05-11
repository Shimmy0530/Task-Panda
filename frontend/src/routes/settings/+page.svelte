<script>
  import { onMount } from 'svelte';
  import { settings as settingsApi, auth, validateNewPassword } from '$lib/api.js';
  import { user } from '$lib/stores.js';
  import WelcomeModal from '$lib/WelcomeModal.svelte';

  let stuckThreshold = 5;
  let saved = false;
  let showReplay = false;
  let savedTimer = null;
  let err = '';
  let loaded = false;

  // Change password
  let currentPw = '';
  let newPw = '';
  let confirmPw = '';
  let pwBusy = false;
  let pwErr = '';
  let pwSaved = false;

  // TOTP enrollment
  let totpBusy = false;
  let totpErr = '';
  let totpUri = '';
  let totpSecret = '';
  let totpConfirmCode = '';
  let totpDisablePw = '';

  onMount(async () => {
    try {
      const r = await settingsApi.get();
      stuckThreshold = r.stuck_threshold_days;
    } catch (e) {
      err = e.message;
    } finally {
      loaded = true;
    }
  });

  async function save() {
    err = '';
    const v = Number(stuckThreshold);
    if (!Number.isInteger(v) || v < 1 || v > 30) {
      err = 'must be an integer between 1 and 30';
      return;
    }
    try {
      const r = await settingsApi.update({ stuck_threshold_days: v });
      stuckThreshold = r.stuck_threshold_days;
      saved = true;
      if (savedTimer) clearTimeout(savedTimer);
      savedTimer = setTimeout(() => (saved = false), 1500);
    } catch (e) {
      err = e.message;
    }
  }

  async function changePassword() {
    pwErr = '';
    pwSaved = false;
    const v = validateNewPassword(newPw, confirmPw);
    if (v) { pwErr = v; return; }
    pwBusy = true;
    try {
      await auth.changePassword(currentPw, newPw);
      currentPw = newPw = confirmPw = '';
      pwSaved = true;
      setTimeout(() => (pwSaved = false), 2500);
    } catch (e) {
      pwErr = e.message;
    } finally {
      pwBusy = false;
    }
  }

  async function startTotp() {
    totpErr = '';
    totpBusy = true;
    try {
      const r = await auth.totpSetup();
      totpUri = r.uri;
      totpSecret = r.secret;
    } catch (e) {
      totpErr = e.message;
    } finally {
      totpBusy = false;
    }
  }

  async function confirmTotp() {
    totpErr = '';
    totpBusy = true;
    try {
      await auth.totpConfirm(totpConfirmCode);
      const me = await auth.me();
      user.set(me);
      totpUri = '';
      totpSecret = '';
      totpConfirmCode = '';
    } catch (e) {
      totpErr = e.message;
    } finally {
      totpBusy = false;
    }
  }

  function cancelTotp() {
    totpUri = '';
    totpSecret = '';
    totpConfirmCode = '';
    totpErr = '';
  }

  async function disableTotp() {
    totpErr = '';
    totpBusy = true;
    try {
      await auth.totpDisable(totpDisablePw);
      totpDisablePw = '';
      const me = await auth.me();
      user.set(me);
    } catch (e) {
      totpErr = e.message;
    } finally {
      totpBusy = false;
    }
  }
</script>

<div class="space-y-8">
  <header>
    <p class="label mb-2">settings</p>
    <h1 class="font-display text-3xl text-ink-100 tracking-tightest leading-none">
      knobs.
    </h1>
  </header>

  {#if loaded}
    <section class="surface rounded-md p-5 space-y-3">
      <label class="block">
        <span class="text-ink-200 text-sm">stuck threshold (days)</span>
        <input
          class="input mt-2 w-32 font-mono"
          type="number"
          min="1"
          max="30"
          bind:value={stuckThreshold}
          on:blur={save}
          on:keydown={(e) => e.key === 'Enter' && e.target.blur()}
        />
      </label>
      <p class="text-ink-500 text-xs">
        Days a task can be carried before the morning ritual flags it as stuck.
      </p>
      {#if saved}<p class="text-moss text-xs">saved</p>{/if}
      {#if err}<p class="text-rust text-xs">{err}</p>{/if}
    </section>
  {/if}

  <!-- Security -->
  <section id="security" class="surface rounded-md p-5 space-y-4">
    <div>
      <p class="label mb-1">security</p>
      <h2 class="text-ink-100 text-lg">change password</h2>
    </div>
    <div class="space-y-3">
      <label class="block">
        <span class="text-ink-200 text-sm">current password</span>
        <input class="input mt-1" type="password" autocomplete="current-password" bind:value={currentPw} />
      </label>
      <label class="block">
        <span class="text-ink-200 text-sm">new password</span>
        <input class="input mt-1" type="password" autocomplete="new-password" bind:value={newPw} />
      </label>
      <label class="block">
        <span class="text-ink-200 text-sm">confirm new password</span>
        <input class="input mt-1" type="password" autocomplete="new-password" bind:value={confirmPw} />
      </label>
      <div class="flex items-center gap-3">
        <button
          class="btn-primary"
          on:click={changePassword}
          disabled={pwBusy || !currentPw || !newPw || !confirmPw}
        >
          {pwBusy ? 'saving…' : 'update password'}
        </button>
        {#if pwSaved}<span class="text-moss text-xs">password updated</span>{/if}
        {#if pwErr}<span class="text-rust text-xs">{pwErr}</span>{/if}
      </div>
    </div>
  </section>

  <!-- TOTP -->
  <section id="totp" class="surface rounded-md p-5 space-y-4">
    <div>
      <p class="label mb-1">two-factor auth</p>
      {#if $user?.totp_enrolled}
        <h2 class="text-ink-100 text-lg">authenticator: <span class="text-moss">on</span></h2>
        <p class="text-ink-500 text-xs mt-1">A 6-digit code from your authenticator app is required at sign-in.</p>
      {:else}
        <h2 class="text-ink-100 text-lg">authenticator: <span class="text-ink-500">off</span></h2>
        <p class="text-ink-500 text-xs mt-1">Add a TOTP code to your sign-in (Aegis, 1Password, Bitwarden, Authy…).</p>
      {/if}
    </div>

    {#if $user?.totp_enrolled}
      <div class="space-y-3">
        <label class="block">
          <span class="text-ink-200 text-sm">password (to disable)</span>
          <input class="input mt-1" type="password" autocomplete="current-password" bind:value={totpDisablePw} />
        </label>
        <button
          class="btn-ghost text-rust border border-rust/40"
          on:click={disableTotp}
          disabled={totpBusy || !totpDisablePw}
        >disable 2fa</button>
      </div>
    {:else if !totpUri}
      <button class="btn-primary" on:click={startTotp} disabled={totpBusy}>
        {totpBusy ? 'generating…' : 'set up authenticator'}
      </button>
    {:else}
      <div class="space-y-3">
        <p class="text-ink-300 text-sm">
          Scan or paste this URI into your authenticator app, then enter the 6-digit code below.
        </p>
        <code class="block text-[11px] font-mono bg-ink-950/60 border border-ink-800 rounded p-2 break-all">
          {totpUri}
        </code>
        <p class="text-ink-500 text-xs">
          Or enter the secret manually:
          <code class="font-mono text-ink-300">{totpSecret}</code>
        </p>
        <label class="block">
          <span class="text-ink-200 text-sm">6-digit code</span>
          <input
            class="input mt-1 font-mono tracking-widest text-center w-32"
            type="text"
            inputmode="numeric"
            pattern="[0-9]*"
            maxlength="6"
            placeholder="000000"
            bind:value={totpConfirmCode}
          />
        </label>
        <div class="flex gap-2">
          <button
            class="btn-primary"
            on:click={confirmTotp}
            disabled={totpBusy || totpConfirmCode.length !== 6}
          >confirm</button>
          <button class="btn-ghost" on:click={cancelTotp} disabled={totpBusy}>cancel</button>
        </div>
      </div>
    {/if}

    {#if totpErr}<p class="text-rust text-xs">{totpErr}</p>{/if}
  </section>

  <!-- Help -->
  <section class="surface rounded-md p-5 space-y-3">
    <p class="label mb-1">help</p>
    <button class="btn-ghost" on:click={() => (showReplay = true)}>
      replay welcome tour
    </button>
  </section>
</div>

{#if showReplay}
  <WelcomeModal bind:open={showReplay} replay={true} on:close={() => (showReplay = false)} />
{/if}
