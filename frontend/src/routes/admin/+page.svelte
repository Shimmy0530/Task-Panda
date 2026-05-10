<script>
  import { goto } from '$app/navigation';
  import { admin as adminApi, validateNewPassword } from '$lib/api.js';
  import { user } from '$lib/stores.js';

  let users = [];
  let loaded = false;
  let err = '';

  // Create form
  let newUsername = '';
  let newPassword = '';
  let newConfirm = '';
  let newIsAdmin = false;
  let createBusy = false;
  let createErr = '';

  // Per-row reset state. resetFor === user.id when the inline form is open.
  let resetFor = null;
  let resetPw = '';
  let resetConfirm = '';
  let resetBusy = false;
  let resetErr = '';
  let resetSavedFor = null;

  // Wait until the layout has resolved $user, then either redirect or load.
  // A simple early-return in onMount races with layout's auth.me() and can
  // leave the page hung on "loading…" forever for an admin who hard-refreshes.
  let triggered = false;
  $: if (!triggered && $user) {
    triggered = true;
    if ($user.is_admin) load();
    else goto('/');
  }

  async function load() {
    err = '';
    try {
      users = await adminApi.users();
    } catch (e) {
      err = e.message;
    } finally {
      loaded = true;
    }
  }

  async function createUser() {
    createErr = '';
    const v = validateNewPassword(newPassword, newConfirm);
    if (v) { createErr = v; return; }
    createBusy = true;
    try {
      await adminApi.createUser({
        username: newUsername.trim(),
        password: newPassword,
        is_admin: newIsAdmin
      });
      newUsername = newPassword = newConfirm = '';
      newIsAdmin = false;
      await load();
    } catch (e) {
      createErr = e.message;
    } finally {
      createBusy = false;
    }
  }

  function openReset(u) {
    resetFor = u.id;
    resetPw = '';
    resetConfirm = '';
    resetErr = '';
  }

  function cancelReset() {
    resetFor = null;
    resetPw = '';
    resetConfirm = '';
    resetErr = '';
  }

  async function submitReset(u) {
    resetErr = '';
    const v = validateNewPassword(resetPw, resetConfirm);
    if (v) { resetErr = v; return; }
    resetBusy = true;
    try {
      await adminApi.resetPassword(u.id, resetPw);
      resetSavedFor = u.id;
      setTimeout(() => {
        if (resetSavedFor === u.id) resetSavedFor = null;
      }, 4000);
      cancelReset();
    } catch (e) {
      resetErr = e.message;
    } finally {
      resetBusy = false;
    }
  }

  async function toggleDisable(u) {
    if (u.id === $user?.id) return;
    try {
      if (u.disabled_at) {
        await adminApi.enable(u.id);
      } else {
        if (!confirm(`Disable ${u.username}? They'll be signed out on their next request.`)) return;
        await adminApi.disable(u.id);
      }
      await load();
    } catch (e) {
      err = e.message;
    }
  }
</script>

<div class="space-y-8">
  <header>
    <p class="label mb-2">admin</p>
    <h1 class="font-display text-3xl text-ink-100 tracking-tightest leading-none">
      users.
    </h1>
  </header>

  {#if !loaded}
    <p class="text-ink-500 text-sm">loading…</p>
  {:else}
    <section class="surface rounded-md overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-ink-900/40 text-left">
          <tr class="text-ink-500 text-xs uppercase tracking-wide">
            <th class="px-4 py-2 font-normal">username</th>
            <th class="px-4 py-2 font-normal">role</th>
            <th class="px-4 py-2 font-normal">2fa</th>
            <th class="px-4 py-2 font-normal">status</th>
            <th class="px-4 py-2 font-normal text-right">actions</th>
          </tr>
        </thead>
        <tbody>
          {#each users as u (u.id)}
            <tr class="border-t border-ink-800/60 align-top">
              <td class="px-4 py-3 text-ink-100 font-mono">
                {u.username}
                {#if u.id === $user?.id}<span class="text-ink-600 text-[10px] ml-1">(you)</span>{/if}
              </td>
              <td class="px-4 py-3 text-ink-400">{u.is_admin ? 'admin' : 'user'}</td>
              <td class="px-4 py-3 text-ink-400">{u.totp_enrolled ? 'on' : 'off'}</td>
              <td class="px-4 py-3">
                {#if u.disabled_at}
                  <span class="text-rust text-xs">disabled</span>
                {:else}
                  <span class="text-moss text-xs">active</span>
                {/if}
              </td>
              <td class="px-4 py-3 text-right">
                {#if u.id !== $user?.id}
                  <button
                    class="btn-ghost text-xs"
                    on:click={() => openReset(u)}
                  >reset password</button>
                  <button
                    class="btn-ghost text-xs"
                    on:click={() => toggleDisable(u)}
                  >{u.disabled_at ? 'enable' : 'disable'}</button>
                {:else}
                  <span class="text-ink-600 text-xs italic">use settings →</span>
                {/if}
                {#if resetSavedFor === u.id}
                  <p class="text-moss text-xs mt-1 italic">password updated — share it with {u.username} now.</p>
                {/if}
              </td>
            </tr>
            {#if resetFor === u.id}
              <tr class="border-t border-ink-800/60 bg-ink-900/20">
                <td class="px-4 py-4" colspan="5">
                  <div class="max-w-md space-y-3">
                    <p class="text-ink-300 text-sm">
                      Set a new password for <span class="font-mono">{u.username}</span>.
                      Share it with them privately; they can change it from settings.
                    </p>
                    <label class="block">
                      <span class="text-ink-200 text-xs">new password</span>
                      <input class="input mt-1" type="password" bind:value={resetPw} autocomplete="new-password" />
                    </label>
                    <label class="block">
                      <span class="text-ink-200 text-xs">confirm</span>
                      <input class="input mt-1" type="password" bind:value={resetConfirm} autocomplete="new-password" />
                    </label>
                    <div class="flex gap-2">
                      <button
                        class="btn-primary text-sm"
                        on:click={() => submitReset(u)}
                        disabled={resetBusy || !resetPw || !resetConfirm}
                      >{resetBusy ? 'saving…' : 'set password'}</button>
                      <button class="btn-ghost text-sm" on:click={cancelReset}>cancel</button>
                    </div>
                    {#if resetErr}<p class="text-rust text-xs">{resetErr}</p>{/if}
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
      {#if err}<p class="text-rust text-xs px-4 py-2">{err}</p>{/if}
    </section>

    <!-- Create user -->
    <section class="surface rounded-md p-5 space-y-3">
      <h2 class="text-ink-100 text-lg">add user</h2>
      <label class="block">
        <span class="text-ink-200 text-sm">username</span>
        <input
          class="input mt-1 font-mono"
          type="text"
          autocomplete="off"
          bind:value={newUsername}
          placeholder="alphanumeric, _ or -"
        />
      </label>
      <label class="block">
        <span class="text-ink-200 text-sm">password (≥12 chars)</span>
        <input class="input mt-1" type="password" autocomplete="new-password" bind:value={newPassword} />
      </label>
      <label class="block">
        <span class="text-ink-200 text-sm">confirm password</span>
        <input class="input mt-1" type="password" autocomplete="new-password" bind:value={newConfirm} />
      </label>
      <label class="flex items-center gap-2 text-sm text-ink-300">
        <input type="checkbox" bind:checked={newIsAdmin} />
        admin
      </label>
      <div class="flex items-center gap-3">
        <button
          class="btn-primary"
          on:click={createUser}
          disabled={createBusy || !newUsername.trim() || !newPassword || !newConfirm}
        >{createBusy ? 'creating…' : 'create user'}</button>
        {#if createErr}<span class="text-rust text-xs">{createErr}</span>{/if}
      </div>
    </section>
  {/if}
</div>
