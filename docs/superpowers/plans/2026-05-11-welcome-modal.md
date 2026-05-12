# Welcome Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a 4-step welcome modal once per user on first login, with a Replay link in /settings.

**Architecture:** New nullable `welcomed_at` DATETIME on `users`, added via additive `ALTER TABLE` in `init_db()`. A new `POST /api/auth/welcome` stamps the column for the current user. The user payload from `user_dict()` (in `backend/app/auth.py`) gains a `welcomed_at` key, which the frontend reads after `auth.me()`. A new `<WelcomeModal>` Svelte component owns the 4-step UI and the `auth.welcome()` API call (skipped in replay mode). It is mounted from `+layout.svelte` when `user.welcomed_at` is null, and from `/settings` on demand.

**Tech Stack:** SQLite + SQLAlchemy, FastAPI, SvelteKit + Tailwind. No test framework — verification is manual per the project's `CLAUDE.md`.

**Spec reference:** `docs/superpowers/specs/2026-05-11-welcome-modal-design.md`.

---

## File touch list

**New:**
- `frontend/src/lib/WelcomeModal.svelte` — the modal component (4 steps, next/back/skip).

**Modified:**
- `backend/app/db.py` — append one ALTER TABLE inside `init_db()`'s `ddl` list.
- `backend/app/models.py` — add `welcomed_at` to `User`.
- `backend/app/auth.py` — add `welcomed_at` to the dict returned by `user_dict()`.
- `backend/app/routers/auth.py` — add `POST /api/auth/welcome`.
- `frontend/src/lib/api.js` — add `welcome` to the `auth` export.
- `frontend/src/lib/stores.js` — extend the `user` shape comment to mention `welcomed_at`.
- `frontend/src/routes/+layout.svelte` — conditional `<WelcomeModal>` mount.
- `frontend/src/routes/settings/+page.svelte` — "Replay welcome tour" button + modal mount.

---

## Task 1: Add `welcomed_at` column on `User`

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/db.py`

- [ ] **Step 1: Add the column on the SQLAlchemy model**

In `backend/app/models.py`, inside the `User` class, immediately after the existing `approved_at` line, add:

```python
    welcomed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

(`datetime` and `DateTime` are already imported.)

- [ ] **Step 2: Add the additive migration**

In `backend/app/db.py`, append a new line to the `ddl` list inside `init_db()`. Put it next to the other `ALTER TABLE users ...` lines (after the `approved_at` line is fine):

```python
"ALTER TABLE users ADD COLUMN welcomed_at DATETIME",
```

The existing surrounding `try` / `except OperationalError: pass` block already makes this idempotent. No backfill — `NULL` is the desired default per the spec.

- [ ] **Step 3: Restart the backend and verify the column exists**

Run:

```bash
docker compose up -d --build backend
```

Then verify:

```bash
docker compose exec backend python -c "from sqlalchemy import create_engine, inspect; from app.config import settings; print('welcomed_at' in [c['name'] for c in inspect(create_engine(settings.DATABASE_URL)).get_columns('users')])"
```

Expected output: `True`

Alternative quick check via sqlite directly on the host (works only if your local dev uses the bind-mounted SQLite file):

```bash
sqlite3 data/focus.db "PRAGMA table_info(users);"
```

Expected: a row containing `welcomed_at|DATETIME|0||0` in the output.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models.py backend/app/db.py
git commit -s -m "Add welcomed_at column on User

Nullable DATETIME, NULL = user hasn't seen the welcome tour yet.
Additive migration in init_db(); no backfill so existing users
will see the tour once on their next login.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Expose `welcomed_at` in `user_dict()`

**Files:**
- Modify: `backend/app/auth.py:73-80`

- [ ] **Step 1: Add the field to `user_dict()`**

In `backend/app/auth.py`, find `user_dict(user: User) -> dict` (around line 73). Add a new key after `last_ritual_date`:

```python
def user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "totp_enrolled": bool(user.totp_secret),
        "last_ritual_date": user.last_ritual_date.isoformat() if user.last_ritual_date else None,
        "welcomed_at": user.welcomed_at.isoformat() if user.welcomed_at else None,
    }
```

- [ ] **Step 2: Restart the backend and verify the field appears**

```bash
docker compose up -d --build backend
```

While logged in to the local dev instance, open the browser DevTools network tab, navigate to any page, find the `GET /api/auth/me` request, and confirm the JSON response includes `"welcomed_at": null` (or a timestamp, if you have one stamped already).

If you don't have a logged-in session handy, hit the endpoint via curl with the session cookie:

```bash
curl -k -s -b "focus_session=<your-jwt>" https://task-panda.localhost:17842/api/auth/me | jq .
```

Expected: JSON object including a `welcomed_at` field (`null` for an existing user).

- [ ] **Step 3: Commit**

```bash
git add backend/app/auth.py
git commit -s -m "Expose welcomed_at on the user payload

Adds the field to user_dict() so /api/auth/me, /api/auth/login,
and /api/auth/setup all surface it without further changes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Add `POST /api/auth/welcome` endpoint

**Files:**
- Modify: `backend/app/routers/auth.py`

- [ ] **Step 1: Add the endpoint**

In `backend/app/routers/auth.py`, after the existing `/me` endpoint (around line 137), add:

```python
@router.post("/welcome", status_code=status.HTTP_204_NO_CONTENT)
def mark_welcomed(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Stamp the current user as having seen the welcome tour.
    Idempotent: calling again just refreshes the timestamp."""
    user.welcomed_at = datetime.utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

`datetime`, `status`, `Depends`, and `current_user` are already imported. Add `Response` to the existing FastAPI import line if it's not already there (it is — used by `_set_session_cookie`).

- [ ] **Step 2: Restart and verify with curl**

```bash
docker compose up -d --build backend
```

Then, with your local session cookie, call the endpoint:

```bash
curl -k -s -i -X POST -b "focus_session=<your-jwt>" https://task-panda.localhost:17842/api/auth/welcome
```

Expected: `HTTP/1.1 204 No Content` and no body.

Then check `/api/auth/me`:

```bash
curl -k -s -b "focus_session=<your-jwt>" https://task-panda.localhost:17842/api/auth/me | jq .welcomed_at
```

Expected: an ISO-8601 timestamp (e.g. `"2026-05-11T18:42:13.881234"`).

- [ ] **Step 3: Verify unauthenticated calls 401**

```bash
curl -k -s -i -X POST https://task-panda.localhost:17842/api/auth/welcome
```

Expected: `HTTP/1.1 401 Unauthorized` (or similar — whatever `current_user()` raises without a cookie).

- [ ] **Step 4: Reset the timestamp for further frontend testing**

You'll want `welcomed_at` back to NULL so the modal shows up later when testing the frontend. Run:

```bash
sqlite3 data/focus.db "UPDATE users SET welcomed_at = NULL WHERE id = <your-user-id>;"
```

(Your user id is in the `/api/auth/me` response.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/auth.py
git commit -s -m "Add POST /api/auth/welcome endpoint

Idempotent stamp of welcomed_at on the current user. Returns 204.
Used by the upcoming welcome-tour modal on dismiss.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Add `auth.welcome()` to the frontend API client

**Files:**
- Modify: `frontend/src/lib/api.js`
- Modify: `frontend/src/lib/stores.js`

- [ ] **Step 1: Add the client method**

In `frontend/src/lib/api.js`, inside the `auth` object literal (around lines 38–51), add a new method after `totpDisable`:

```js
  totpDisable: (password) => api.post('/api/auth/totp/disable', { password }),
  welcome: () => api.post('/api/auth/welcome')
```

(Make sure to add the trailing comma to the line above it, then the new line.)

- [ ] **Step 2: Update the user-store shape comment**

In `frontend/src/lib/stores.js`, update the comment on the `user` writable so future readers know `welcomed_at` exists:

```js
// Populated by +layout.svelte after auth.me() succeeds; null while unauthenticated.
// Shape: { id, username, is_admin, totp_enrolled, last_ritual_date, welcomed_at }
```

- [ ] **Step 3: Verify from the browser console**

After running `npm run dev` (or `docker compose up -d --build frontend`), open the deployed app, log in, and from the DevTools console run:

```js
const { auth } = await import('/src/lib/api.js');
await auth.welcome();
```

Expected: resolves to `null` (because the wrapper returns null on 204). Then refresh the page and confirm `welcomed_at` is now a string in the `/api/auth/me` response.

Reset for later testing:

```bash
sqlite3 data/focus.db "UPDATE users SET welcomed_at = NULL WHERE id = <your-user-id>;"
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.js frontend/src/lib/stores.js
git commit -s -m "Add auth.welcome() client method

Wraps POST /api/auth/welcome. Used by the welcome-tour modal
on dismiss (skipped when replaying from settings).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Create `WelcomeModal.svelte`

**Files:**
- Create: `frontend/src/lib/WelcomeModal.svelte`

- [ ] **Step 1: Create the component**

Create `frontend/src/lib/WelcomeModal.svelte` with this exact content:

```svelte
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
```

Note: `surface`, `btn-ghost`, `btn-primary`, and the `ink-*` / `frog-*` Tailwind classes are project-wide and defined in `frontend/src/app.css` / `tailwind.config.js`. They match the existing capture modal, so the welcome modal will look like it belongs.

- [ ] **Step 2: Verify the file compiles**

If the dev server isn't already running:

```bash
cd frontend && npm run dev
```

Watch the terminal output — there should be no Svelte compile errors mentioning `WelcomeModal.svelte`. Don't worry about it being unused yet; that's Task 6.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/WelcomeModal.svelte
git commit -s -m "Add WelcomeModal component

Four-step welcome tour (ritual / plan / focus / capture) with
next, back, and skip-tour controls. Final step CTA navigates to
/morning. Accepts a 'replay' prop that suppresses the stamping
API call when the modal is opened from /settings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Mount the modal in the root layout

**Files:**
- Modify: `frontend/src/routes/+layout.svelte`

- [ ] **Step 1: Import the modal and add state**

Open `frontend/src/routes/+layout.svelte`. In the `<script>` block, add the import (near the top, with the other `$lib` imports):

```js
import WelcomeModal from '$lib/WelcomeModal.svelte';
```

Then add a state variable next to the existing `showCapture`:

```js
let showWelcome = false;
```

- [ ] **Step 2: Trigger the modal in onMount**

Replace the existing auth block inside `onMount` (currently lines 13–19):

```js
try {
  user.set(await auth.me());
} catch {
  user.set(null);
  if (!$page.url.pathname.startsWith('/login')) goto('/login');
}
```

with:

```js
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
```

- [ ] **Step 3: Add the close handler**

In the same `<script>` block, add a new function alongside the existing handlers (e.g. above `signOut`):

```js
function handleWelcomeClose() {
  showWelcome = false;
  user.update((u) => (u ? { ...u, welcomed_at: new Date().toISOString() } : u));
}
```

- [ ] **Step 4: Mount the component in the template**

In the layout's template, immediately after the closing `{/if}` of the existing capture modal block (around line 171), add:

```svelte
{#if showWelcome && $user}
  <WelcomeModal bind:open={showWelcome} on:close={handleWelcomeClose} />
{/if}
```

- [ ] **Step 5: Manually verify the trigger**

Make sure your test user's `welcomed_at` is NULL:

```bash
sqlite3 data/focus.db "UPDATE users SET welcomed_at = NULL WHERE id = <your-user-id>;"
```

Then in the browser, hard-reload the app (`Ctrl+Shift+R`) while logged in. You should see the welcome modal appear on top of whatever page you were on.

Verification checklist (do these in one session, in order):

  - Modal appears on first authenticated page load.
  - Step indicator reads `1 / 4`.
  - Pressing **next** advances steps. Step 4's primary button reads "start your morning ritual."
  - Pressing **back** goes backwards; the back button is disabled on step 1.
  - Pressing **Esc** dismisses the modal. After dismiss, refresh the page — the modal does NOT reappear.
  - Reset welcomed_at again, refresh, and this time step through all 4 steps. The final CTA navigates to `/morning` AND the modal does not reappear after.
  - Reset welcomed_at, refresh, click **skip tour** — modal closes, stays on the same page, modal does not reappear on next refresh.
  - Reset welcomed_at, refresh, click the modal backdrop (outside the card) — modal closes (treated as a dismiss); welcomed_at is stamped.

If any of these fail, fix and re-test before moving on.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/+layout.svelte
git commit -s -m "Show welcome modal on first authenticated load

Layout watches user.welcomed_at after auth.me() and mounts
WelcomeModal once when it's null. handleWelcomeClose
optimistically updates the local user store so the modal does
not re-trigger during the session.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Add Replay link in /settings

**Files:**
- Modify: `frontend/src/routes/settings/+page.svelte`

- [ ] **Step 1: Import and add state**

Open `frontend/src/routes/settings/+page.svelte`. In the `<script>` block, add the import (with the other imports near the top):

```js
import WelcomeModal from '$lib/WelcomeModal.svelte';
```

Add a state variable alongside the existing flags (e.g. near `let saved = false;`):

```js
let showReplay = false;
```

- [ ] **Step 2: Add the replay button and the modal mount in the template**

At the bottom of the page's main content (after the last existing settings card but inside the same wrapper — pattern-match what's already there), add:

```svelte
<section class="mt-8">
  <h2 class="label mb-3">help</h2>
  <button class="btn-ghost" on:click={() => (showReplay = true)}>
    replay welcome tour
  </button>
</section>

{#if showReplay}
  <WelcomeModal bind:open={showReplay} replay={true} on:close={() => (showReplay = false)} />
{/if}
```

If the existing settings page doesn't use `<section>` wrappers, follow whatever the surrounding pattern is (`<div class="...">` blocks for each settings card). Keep the visual style consistent — small heading, a single ghost button.

- [ ] **Step 3: Manually verify the replay flow**

In the browser, with a user whose `welcomed_at` is already stamped (i.e., they've dismissed the modal at least once), navigate to `/settings`. Open DevTools → Network and filter on `auth/welcome`. Then:

  - Click **replay welcome tour**. The modal appears.
  - Step through to the final CTA. The modal closes, you navigate to `/morning`.
  - In the Network tab, confirm that **no** `POST /api/auth/welcome` request was sent during replay. (That's the point of `replay={true}`.)
  - Go back to `/settings`, click replay again, this time press **Esc**. Modal closes. Still no `POST /api/auth/welcome`.
  - Refresh `/settings`. The replay button is still there and still works.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/settings/+page.svelte
git commit -s -m "Add 'replay welcome tour' button in /settings

Mounts the same WelcomeModal component with replay={true} so the
stamp-on-dismiss API call is skipped. Useful for users who want
to re-read the orientation after dismissing it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: End-to-end manual verification

No code changes in this task — just a final pass over the whole feature before declaring done.

- [ ] **Step 1: Reset for a clean run**

```bash
sqlite3 data/focus.db "UPDATE users SET welcomed_at = NULL WHERE id = <your-user-id>;"
```

- [ ] **Step 2: Walk the happy path**

In the browser:
  - Hard-reload the app while logged in. Welcome modal appears.
  - Step through all 4 steps, reading each one. Verify the copy reads cleanly and emoji render correctly.
  - Click "start your morning ritual." You land on `/morning`. Welcome modal is gone.
  - Navigate away and back to other pages. Modal does NOT reappear.

- [ ] **Step 3: Walk the skip path**

```bash
sqlite3 data/focus.db "UPDATE users SET welcomed_at = NULL WHERE id = <your-user-id>;"
```

  - Hard-reload. Welcome modal appears.
  - Click **skip tour**. Modal closes. You stay on the current page.
  - Hard-reload — modal does NOT reappear.

- [ ] **Step 4: Walk the replay path**

  - Navigate to `/settings`. Click **replay welcome tour**. Modal appears.
  - Step through, click the final CTA. Confirm you land on `/morning`.
  - Navigate back to `/settings`. Click replay again. Press Esc. Modal closes.
  - Open `/api/auth/me` (e.g. via DevTools network tab while navigating). `welcomed_at` is still the original stamp from earlier — replay never overwrote it.

- [ ] **Step 5: Mobile breakpoint check**

In DevTools, switch to a small viewport (e.g. 375×667). Reset `welcomed_at` to NULL, refresh. Modal should:
  - Be readable on mobile.
  - Not overflow horizontally.
  - Footer buttons still tappable (back, next, skip tour) without overlapping.
  - Step indicator and buttons may wrap if needed; that's acceptable, but they must not be cut off.

- [ ] **Step 6: Admin-created user check (optional but recommended)**

  - Log in as admin (your current user). Go to `/admin`. Create a new non-admin user.
  - Log out, log in as the new user. The welcome modal appears.
  - Dismiss it. Refresh — does not reappear. Done.

- [ ] **Step 7: Final commit if anything was tweaked during verification**

If you adjusted copy, padding, breakpoints, etc. during verification:

```bash
git add -A
git commit -s -m "Polish welcome modal layout/copy from verification pass

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

Otherwise skip the commit and proceed to declaring done.

- [ ] **Step 8: Optional — open a PR**

Project workflow is squash-merge via `gh pr merge`. If you've been working on a branch:

```bash
gh pr create --title "Add first-login welcome tour" --body "$(cat <<'EOF'
## Summary
- 4-step welcome modal shown once per user on first authenticated load
- Stored as User.welcomed_at; new POST /api/auth/welcome stamps it
- Replay link in /settings re-opens the same modal without re-stamping

## Test plan
- [x] Fresh login → modal appears, step through, lands on /morning
- [x] Skip tour → dismisses without re-appearing
- [x] Esc/backdrop dismiss → stamps and does not re-appear
- [x] Settings → replay tour → no extra POST /api/auth/welcome
- [x] Mobile breakpoint readable
- [x] Admin-created new user sees the tour once

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

If working directly on `main` (the existing repo pattern, per recent commits), this step is optional — squash-merge isn't applicable.

---

## Done criteria

The feature is complete when:

- All 8 tasks above are checked off.
- All commits are pushed.
- A clean test user (welcomed_at NULL) sees the modal on first authenticated load, can dismiss it via any of the three exits (final CTA, skip, Esc/backdrop), and never sees it again automatically.
- The replay button in /settings works without re-stamping.
- No console errors or Svelte compile warnings touching `WelcomeModal.svelte`.
