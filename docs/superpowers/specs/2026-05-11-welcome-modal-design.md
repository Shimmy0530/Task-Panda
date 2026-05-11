# First-login welcome tour — design

**Date:** 2026-05-11
**Status:** Approved, ready for implementation plan

## Goal

When a user logs in for the first time (or, for existing users, on their next login after this ships), show a 4-step modal that introduces the core loop of Task Panda: morning ritual → plan → focus → capture. Once dismissed (or skipped), it never appears again automatically, but can be replayed from `/settings`.

## User stories

- As a brand-new user (created by an admin), the first time I log in I see a short tour explaining what the app does and where to start.
- As the first-run admin, the same tour appears after I complete `/setup`.
- As any user who has already used Task Panda before this feature shipped, I see the tour exactly once on my next login, then never again.
- As any user, I can replay the tour from `/settings` at any time.
- As any user, I can dismiss the tour with "Skip tour" or by stepping through and pressing the final CTA.

## Out of scope

- Multi-version tour bumping (`welcomed_version: 2`, etc.) — single one-shot for now.
- An onboarding wizard for setup tasks (timezone, 2FA, password change). The tour is purely educational.
- Screenshots, illustrations, or custom raccoon-mascot art per step. Text + emoji only.
- Localization scaffolding (single-user app, one language).
- Server-side rate-limiting or auditing of welcome dismissals.

## Architecture

### Storage

New nullable column on the `users` table: `welcomed_at DATETIME NULL`. `NULL` means "has not been welcomed yet"; a timestamp means "welcomed at that moment."

Matches the existing pattern for time-stamp flags on `User` (`disabled_at`, `last_ritual_date`). Added via additive `ALTER TABLE` inside `init_db()`, wrapped in the same try/except `OperationalError` so re-runs are idempotent.

**No backfill.** Existing rows get `NULL` by default, which is the desired behavior — everyone sees the tour exactly once on their next login.

### Trigger

In `frontend/src/routes/+layout.svelte`'s existing `onMount`, after `user.set(await auth.me())` succeeds:

- If `user.welcomed_at` is null AND the current route does not start with `/login`, set `showWelcome = true`.
- The `WelcomeModal` component itself owns the `auth.welcome()` API call (so the same component can be reused for replay, which must skip the call). The layout's `on:close` handler only optimistically updates the local user store so the modal does not re-trigger during the session. Navigation to `/morning` happens inside the modal as part of the final-step CTA, before `close` is dispatched.

### Replay

A small "Replay welcome tour" button in `/settings` sets a local `showReplay = true` flag and mounts the same `WelcomeModal` component with a `replay` prop. When `replay` is true, the close handler skips the `auth.welcome()` API call (the user is already stamped). Final CTA still navigates to `/morning`.

## Backend changes

### Schema migration

`backend/app/db.py`, inside `init_db()`'s additive `ALTER TABLE` block:

```sql
ALTER TABLE users ADD COLUMN welcomed_at DATETIME NULL;
```

Wrapped in the existing try/except `OperationalError` to keep re-runs safe.

### Model

`backend/app/models.py`, on the `User` class:

```python
welcomed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

### User response payload

`GET /api/auth/me`, `POST /api/auth/login`, and `POST /api/auth/setup` all return a user payload built by the `user_dict()` helper in `backend/app/auth.py` (a plain dict, not a Pydantic schema). Add a new key to that helper:

```python
"welcomed_at": user.welcomed_at.isoformat() if user.welcomed_at else None,
```

Adding it in `user_dict()` updates all three entry points at once — the user store stays consistent regardless of how the frontend obtained the user.

### New endpoint

`POST /api/auth/welcome` in `backend/app/routers/auth.py`:

- Auth required (uses the existing `current_user()` dependency).
- Sets `user.welcomed_at = datetime.utcnow()` and commits.
- Idempotent: calling again just overwrites with a newer timestamp — behavior unchanged.
- Returns `204 No Content`.

No request body. No CSRF concern (cookie is SameSite=Lax, action is per-user idempotent).

## Frontend changes

### New API client method

`frontend/src/lib/api.js`, alongside the existing `auth.*` helpers:

```js
welcome: () => req('/auth/welcome', { method: 'POST' })
```

### New component: `WelcomeModal.svelte`

Location: `frontend/src/lib/WelcomeModal.svelte`. Self-contained, ~150 LOC.

**Props:**
- `open` (bool, two-way bindable).
- `replay` (bool, default false). When true, the close handler does **not** call `auth.welcome()`.

**Events:**
- `close` — dispatched when the modal closes for any reason (skip, final CTA, Esc, backdrop click).

**Internal state:**
- `step` (number, 0–3).

**Styling:**
Mirror the existing capture modal at `frontend/src/routes/+layout.svelte` lines 146–171 exactly:
- Wrapper: `fixed inset-0 bg-ink-950/85 backdrop-blur-sm flex items-start justify-center pt-32 z-50` and a backdrop-click handler that closes.
- Card: `surface rounded-lg p-5 w-full max-w-lg mx-4` with `on:click|stopPropagation` to prevent backdrop dismissal from inside the card.

**Layout per step:**
- A large emoji at the top (text-5xl or similar).
- Heading (h2, font-display, text-ink-100).
- Body paragraph (text-sm text-ink-300).
- Footer row: `Skip tour` (small ghost link, leftmost), `Back` button (disabled on step 0), step indicator (e.g., `1 / 4`, dim mono), `Next →` / final-step CTA.

**Keyboard:**
- `Esc` closes (matches capture modal).
- `Enter` advances to the next step or fires the final CTA.

**Final-step CTA:**
- Label: "Start your morning ritual."
- Action: call `auth.welcome()` (unless `replay`), dispatch `close`, then `goto('/morning')`.

**Skip-tour link:**
- Same action as the final CTA but without the `goto('/morning')` — just dismisses on the current page.

### Step content (canonical copy)

| # | Emoji | Heading | Body |
|---|---|---|---|
| 1 | 🌅 | Start with the morning ritual | Each morning, the Ritual screen helps you set the day. Pick up to 5 tasks and mark one "do first." For anything you didn't finish yesterday, you decide what to pull forward, drop, or mark done — and you can pull items in from the backlog too. |
| 2 | 📋 | The Plan screen keeps your day small | Plan shows today's 5 tasks with the "do first" one called out. Anything beyond 5 lives in the backlog until you graduate it forward. |
| 3 | 🍅 | Focus runs a 25-minute timer | The Focus screen starts a 25-minute timer on whichever task you choose — and you can switch tasks or take a break whenever you want. You can also dictate notes by voice while you work. |
| 4 | 💡 | Capture catches stray thoughts | Hit **⌘ .** (or the **+** button on mobile) anywhere in the app to drop a thought into your inbox. Triage it later — don't break flow now. |

Copy must remain in plain English per the project's copy style — no productivity-nerd idioms like "eat the frog," "deep work," etc. The internal "frog" metaphor stays in the data layer (`is_frog` column), but user-facing copy says "do first."

### Layout integration

`frontend/src/routes/+layout.svelte`:

1. Import `WelcomeModal` from `$lib/WelcomeModal.svelte`.
2. Add `let showWelcome = false;`.
3. In the existing `onMount`, after `user.set(await auth.me())` succeeds:

   ```js
   const u = await auth.me();
   user.set(u);
   if (!u.welcomed_at && !$page.url.pathname.startsWith('/login')) {
     showWelcome = true;
   }
   ```

4. Render the modal alongside the existing capture modal:

   ```svelte
   {#if showWelcome && $user}
     <WelcomeModal bind:open={showWelcome} on:close={handleWelcomeClose} />
   {/if}
   ```

5. `handleWelcomeClose`:

   ```js
   function handleWelcomeClose() {
     user.update(u => u ? { ...u, welcomed_at: new Date().toISOString() } : u);
   }
   ```

   (The actual `auth.welcome()` call happens inside the modal so the same component can be reused for replay.)

### Settings page integration

`frontend/src/routes/settings/+page.svelte`:

- Add a small "Replay welcome tour" button near the bottom of the page (under existing security/2FA controls).
- Clicking sets a local `let showReplay = false;` to true.
- Render `<WelcomeModal bind:open={showReplay} replay={true} on:close={() => showReplay = false} />`.

## Error handling

- **`POST /api/auth/welcome` fails (network drop, 500, etc.):** The frontend has already optimistically updated the local user store, so the modal will not reappear in the current session. On the next page load, the DB row is still `NULL`, so the user will see the modal once more. This is acceptable — not destructive, and the modal is short.
- **`auth.me()` fails entirely:** Already handled by the existing layout — it redirects to `/login`. Welcome logic never runs because the user is not authenticated.
- **User navigates away mid-tour:** No persistence of step state. Next mount restarts at step 0 if not yet welcomed. Acceptable for a 4-step tour.
- **User has `welcomed_at` set but visits `/settings` and clicks replay:** The replay branch skips `auth.welcome()`, so the DB stays consistent.

## Edge cases

- **First-run admin via `/api/auth/setup`:** The setup endpoint creates the user without setting `welcomed_at`, so the column defaults to `NULL`. The first authenticated page load after setup triggers the modal. No special-casing needed.
- **Admin-created users:** Same — `welcomed_at` defaults to `NULL` on insert. Modal appears on their first login.
- **Existing maintainer account on chemex:** The migration runs `ALTER TABLE` with no backfill, so `welcomed_at` is `NULL` for every existing row. Maintainer sees the modal once on next login, dismisses it, done.
- **User logs out and back in without dismissing:** The modal re-triggers, because `welcomed_at` is still `NULL`. Expected behavior — the modal is "shown until dismissed," not "shown once and forgotten."

## Testing

The project has no automated test suite (per `CLAUDE.md`). Manual verification before declaring done:

- [ ] Fresh DB: setup admin, log in, modal appears.
- [ ] Step through all 4 steps with Next, then click the final CTA — verify navigation to `/morning` and the modal does not reappear on subsequent navigations.
- [ ] Fresh user (admin-created), log in, click "Skip tour" — verify the modal disappears, user lands on the current page (not `/morning`), and the modal does not reappear.
- [ ] Verify Esc and backdrop-click both dismiss and call `auth.welcome()`.
- [ ] After dismissal, navigate to `/settings`, click "Replay welcome tour" — verify the modal appears again, step through, and verify no second `POST /api/auth/welcome` call is made (check Network tab).
- [ ] On mobile breakpoint (`<sm`), verify the modal is readable and doesn't overflow.
- [ ] Verify `GET /api/auth/me` response includes `welcomed_at`.
- [ ] Verify `POST /api/auth/welcome` returns 204 and stamps the DB row (check via `sqlite3 data/focus.db` or `/admin`).

## File touch list

**New:**
- `frontend/src/lib/WelcomeModal.svelte`
- `docs/superpowers/specs/2026-05-11-welcome-modal-design.md` (this doc)

**Modified:**
- `backend/app/db.py` — add `ALTER TABLE users ADD COLUMN welcomed_at DATETIME NULL` to `init_db()`.
- `backend/app/models.py` — add `welcomed_at` to `User`.
- `backend/app/auth.py` — add `welcomed_at` key to `user_dict()`.
- `backend/app/routers/auth.py` — add `POST /api/auth/welcome` endpoint.
- `frontend/src/lib/api.js` — add `auth.welcome()`.
- `frontend/src/routes/+layout.svelte` — mount welcome modal conditionally on first auth load.
- `frontend/src/routes/settings/+page.svelte` — add "Replay welcome tour" button.
