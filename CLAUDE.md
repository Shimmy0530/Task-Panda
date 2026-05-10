# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo shape

The repository wraps the actual app at `focus/` plus deployment artifacts:

- `focus/` — the SvelteKit + FastAPI app (single-user, self-hosted)
- `focus.tar.gz` — original scaffold tarball (kept for reference; do not edit)
- `.env` — **local staging only**, holds the Groq API key for one-time provisioning. Not used at runtime; `focus/.env` is the actual runtime config.

Treat `focus/` as the project root for almost all work.

## Maintainer-private notes

If `CLAUDE.local.md` exists alongside this file, read it for deployment-specific details (hostnames, SSH aliases, server paths) that don't belong in the public repo. It's gitignored — each maintainer keeps their own.

## Naming: code vs. user-facing

User-facing product name is **Task Panda**. Code identifiers, container names (`focus-frontend`/`focus-backend`), DB columns (`is_frog`), and cookie names stay unchanged — a deliberate rename pass is deferred. New UI strings, page titles, READMEs, and brand copy say "Task Panda." Don't refactor existing identifiers unless explicitly asked.

## Copy style (user-facing strings)

Plain, accessible framing only. Avoid productivity-nerd idioms in UI copy: "eat the frog," "MVP," "OKR," "kanban," "deep work," etc. The data layer keeps internal metaphors (`is_frog` column, 🐸 emoji) but user-facing strings should read in plain English: "the boring important one," "do first," etc.

## Deployment shape (deviates from `focus/README.md`)

The README references Caddy and Let's Encrypt — that path was abandoned. Production runs behind host nginx with a TLS cert you supply (Cloudflare Origin, Let's Encrypt, or whatever fits). When editing deployment, update both files together.

- **Container ports:** backend at `127.0.0.1:17840` (→ container `:8000`), frontend at `127.0.0.1:17841` (→ container `:3000`). nginx splits `/api/*` to backend, everything else to frontend.
- **nginx vhost:** `focus/deploy/nginx.example.conf` is a template — copy it, replace `server_name`, TLS paths, and Cloudflare origin allowlist (if any), then drop into `/etc/nginx/sites-available/...`. Use `listen 443 ssl http2;` syntax for nginx <1.25, or the `http2 on;` directive on newer versions.
- **Compose stack** (`focus/docker-compose.yml`): just `backend` and `frontend`, no proxy. They share an `internal` docker network plus host loopback ports. SQLite DB lives in `./data/focus.db` (bind-mounted volume).

### Redeploy

The runtime `.env` is **not** in git — it lives only on the deploy host (perms 600). The SQLite DB is at `<clone-path>/focus/data/focus.db` (also untracked).

```bash
# local
git push

# server (substitute your SSH alias and clone path)
ssh <host> 'cd <clone-path> && git pull && cd focus && docker compose up -d --build'
```

For backend-only changes, append `backend` to the compose command to skip the slow svelte build:

```bash
ssh <host> 'cd <clone-path> && git pull && cd focus && docker compose up -d --build backend'
```

**Container-owned host paths:** anything the containers write (notably `focus/data/`) is owned by root on the host. Host-side `mv`/`rm`/`chown` needs `sudo`.

### Merging PRs

Default to `gh pr merge <N> --squash --delete-branch`. Squash keeps `main`'s log one-commit-per-feature, matching existing style. Avoid merge commits.

## Local dev

```bash
# Backend
cd focus/backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi 'uvicorn[standard]' sqlalchemy pydantic pydantic-settings \
    'python-jose[cryptography]' httpx python-multipart bcrypt pyotp
uvicorn app.main:app --reload   # binds :8000

# Frontend
cd focus/frontend
npm install
npm run dev                      # binds :5173
```

The backend cookie is set with `secure=True`, so the login flow does **not** work on plain HTTP (no localhost override). Local dev requires either a TLS-terminating proxy or a temporary code change — proxy through your deployed instance and iterate against prod, or run `docker compose up` locally and front it with self-signed TLS.

There are no tests.

## Helper scripts (`focus/bin/`)

`focus/.venv/` already has `bcrypt` and `pyotp` installed for these:

- `bin/hash-password.py` — interactive prompt; prints `AUTH_PASSWORD_HASH='...'` line for `.env`. Single-quoting preserves `$` in the bcrypt hash.
- `bin/setup-2fa.py` — prints `AUTH_TOTP_SECRET=...` plus an `otpauth://` URI for authenticator apps. **Run interactively** so the secret never enters the conversation transcript.

## Architecture

### Single-owner model

There is exactly one user (`OWNER_ID = 1`, hardcoded in `backend/app/db.py`). `init_db()` runs on FastAPI lifespan startup and idempotently creates the schema, runs additive `ALTER TABLE` migrations (errors swallowed via `OperationalError`), and bootstraps the owner row. Alembic is staged (`alembic.ini`, empty `versions/`) but unused — **add new schema with `ALTER TABLE` in `init_db()`** until the project graduates to alembic.

There is no signup, no email, no password reset endpoint. To rotate the password: regenerate `AUTH_PASSWORD_HASH` via `bin/hash-password.py`, edit `.env`, `docker compose restart backend`. Sessions stay valid for 30 days unless `JWT_SECRET` is also rotated.

### Auth

`backend/app/auth.py`:
- bcrypt password verify + optional TOTP (`pyotp`, 6 digits, `valid_window=1`).
- JWT in HttpOnly+Secure+SameSite=Lax cookie. Cookie name from `SESSION_COOKIE_NAME` env (default `focus_session`).
- Failed auth attempts call `slow_fail()` — a fixed `asyncio.sleep(1.2)` before raising 401, to slow brute force.
- `current_user()` is the FastAPI dependency every protected route uses.
- Public endpoint `GET /api/auth/config` returns `{totp_required: bool}` so the login UI can decide whether to render the TOTP field.

### Routing layout

All backend routes are under `/api/*` (every router sets a `/api/...` prefix). nginx exploits this to cleanly split traffic: `location /api/` → backend, `location /` → frontend. **Do not introduce non-`/api` backend routes** without updating the nginx vhost.

Routers (`backend/app/routers/`):
- `auth.py` — login/logout/me/config
- `tasks.py` — CRUD plus `POST /api/tasks/{id}/dictation` (atomic dictation append), `POST /api/tasks/{id}/copy` (duplicate to today, subtasks reset to undone), `GET /api/tasks/backlog` (rows with `day_date IS NULL`)
- `sessions.py` — pomodoro start/end + today/week dashboards
- `morning.py` — `GET /state` and `POST /complete`/`/skip` for the ritual. State now also returns `stuck_yesterday`, `stale_backlog`, `backlog_top`, `stuck_threshold_days`. Complete accepts `pull_from_backlog`, `dropped_stale_ids`, `kept_stale_ids` and prunes done subtasks + bumps `carried_count` on carry.
- `capture.py` — intrusive-thoughts inbox + `POST /api/llm/first-action`, `POST /api/llm/subtasks` (AI breakdown — staged, not persisted), `POST /api/llm/weekly-review?today=YYYY-MM-DD` (cached server-side per (user, client-local day) — `today` required, comes from `localToday()`)
- `settings.py` — `GET/PATCH /api/settings`; currently exposes `stuck_threshold_days` (default 5)
- `transcribe.py` — `POST /api/transcribe` (audio → text) and `POST /api/outline` (text → cleaned outline)

The voice flow is **two endpoints, not one**: the frontend uploads audio to `/api/transcribe`, then sends the transcript to `/api/outline` (with optional `task_id` for context), then writes the result via `/api/tasks/{id}/dictation`. An earlier scaffold had a duplicate combined endpoint at `/api/llm/transcribe`; that was removed because it had broken imports (`polish_dictation`, `..stt`).

### Frontend

`focus/frontend` is SvelteKit + Tailwind, built with `@sveltejs/adapter-node` (runs as `node build`). Routes mirror the URL structure 1:1 — pages live under `src/routes/<page>/+page.svelte`. All HTTP goes through `src/lib/api.js`, which always sends `credentials: 'include'` so the auth cookie travels. Same-origin via the nginx split, so CORS is a non-issue in production.

#### Timezone discipline

Server runs UTC. The frontend's "today" must always be browser-local. Any frontend call that filters by day passes `localToday()` from `src/lib/api.js` (defined as `new Date().toLocaleDateString('en-CA')`). Never let the backend fall back to its own `Date.today()` for user-facing date filters — they will diverge across midnight UTC and silently hide tasks.

### Domain invariants (enforced server-side)

- **Max 5 tasks per `day_date`**, **max 1 frog (`is_frog=true`) per day**. `tasks.py` raises 400 on violation.
- `Task.day_date` is **nullable**; null = backlog. Backlog rows don't count toward the day cap. Frogs can never live in the backlog.
- `POST /api/tasks` with `day_date` omitted/null and `is_frog=false` creates a backlog row. `PATCH /api/tasks/{id}` with `day_date=<date>` graduates a backlog row to that day (cap re-checked, `carried_count` reset).
- Morning ritual `complete` payload is the canonical way to plant a frog + supporting cast; it also processes yesterday's open tasks (`carry`/`drop`/`done`) and stamps `User.last_ritual_date`. "Carrying forward" demotes frog status — frogs must be re-chosen each day. Carry also prunes any done subtasks and increments `Task.carried_count` (used for stuck detection in next day's ritual).
- Subtasks live as a JSON list `[{id, title, done}]` on `Task.subtasks` (cap 25 server-side). PATCH replaces the full list. Copying a task deep-copies subtasks with all `done=false`.
- Dictation appends are atomic: `POST /api/tasks/{id}/dictation` reads `task.notes`, appends a `🎙 dictation · <UTC stamp>` block, commits once.

### LLM + STT

`backend/app/llm.py` is a thin client over an OpenAI-compatible chat-completions API (Groq default). Functions:
- `first_action(title, notes)` — returns a single ≤5-min concrete action
- `outline_from_transcript(transcript, task_title?, task_notes?)` — returns Markdown outline
- `subtasks_from_task(title, notes)` — returns a list of 0–7 short action steps (JSON-mode, defensive parse)
- `weekly_review(events)` — returns a ≤200-word Markdown summary over a week's session/completion data

`backend/app/transcribe.py` is the Whisper client (`transcribe_audio` → dict with `text`/`duration`/`language`).

To swap providers, edit `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` in `.env`. Whisper requires the same provider unless `transcribe.py` is forked.
