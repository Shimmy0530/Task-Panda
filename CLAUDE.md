# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo shape

The repository is the SvelteKit + FastAPI app, single-user and self-hosted, with deployment artifacts in-tree:

- `backend/`, `frontend/` — the app
- `deploy/` — nginx vhost template
- `bin/` — interactive helper scripts (password hash, 2FA seed)
- `docker-compose.yml` — backend + frontend stack (no proxy)
- `.env` — runtime config (gitignored; lives only on the deploy host at perms 600)
- `data/focus.db` — SQLite database (gitignored; bind-mounted into the backend container as `/data/focus.db`)
- `brand/` — high-res logo source PNGs (gitignored). Re-export to `frontend/static/` if the logo changes; the app loads PNG variants from there, not from `brand/`.

## Maintainer-private notes

This file (`CLAUDE.md`) is committed to the public repo at github.com/Shimmy0530/Task-Panda — anything written here is world-readable. For deployment specifics (hostnames, IPs, SSH aliases, server paths, runtime URLs), use the gitignored `CLAUDE.local.md` instead. Read `CLAUDE.local.md` if it exists.

## Naming: code vs. user-facing

User-facing product name is **Task Panda**. Code identifiers, container names (`focus-frontend`/`focus-backend`), DB columns (`is_frog`), and cookie names stay unchanged — a deliberate rename pass is deferred. New UI strings, page titles, READMEs, and brand copy say "Task Panda." Don't refactor existing identifiers unless explicitly asked.

## Copy style (user-facing strings)

Plain, accessible framing only. Avoid productivity-nerd idioms in UI copy: "eat the frog," "MVP," "OKR," "kanban," "deep work," etc. The data layer keeps internal metaphors (`is_frog` column, 🐸 emoji) but user-facing strings should read in plain English: "the boring important one," "do first," etc.

## Deployment shape

Production runs behind host nginx with a TLS cert you supply (Cloudflare Origin, Let's Encrypt, or whatever fits). Public `README.md` covers the user-facing setup; this file covers the *why* and the gotchas.

- **Container ports:** backend at `127.0.0.1:17840` (→ container `:8000`), frontend at `127.0.0.1:17841` (→ container `:3000`). nginx splits `/api/*` to backend, everything else to frontend.
- **nginx vhost:** `deploy/nginx.example.conf` is a template — copy it, replace `server_name`, TLS paths, and Cloudflare origin allowlist (if any), then drop into `/etc/nginx/sites-available/...`. Use `listen 443 ssl http2;` syntax for nginx <1.25, or the `http2 on;` directive on newer versions.
- **Compose stack** (`docker-compose.yml`): just `backend` and `frontend`, no proxy. They share an `internal` docker network plus host loopback ports. SQLite DB lives in `./data/focus.db` (bind-mounted volume).

### Redeploy

The runtime `.env` is **not** in git — it lives only on the deploy host (perms 600). The SQLite DB is at `<clone-path>/data/focus.db` (also untracked).

```bash
# local
git push

# server (substitute your SSH alias and clone path)
ssh <host> 'cd <clone-path> && git pull && docker compose up -d --build'
```

For backend-only changes, append `backend` to the compose command to skip the slow svelte build:

```bash
ssh <host> 'cd <clone-path> && git pull && docker compose up -d --build backend'
```

**Container-owned host paths:** anything the containers write (notably `data/`) is owned by root on the host. Host-side `mv`/`rm`/`chown` needs `sudo`.

### Merging PRs

Default to `gh pr merge <N> --squash --delete-branch`. Squash keeps `main`'s log one-commit-per-feature, matching existing style. Avoid merge commits.

Commits use DCO sign-off (`git commit -s`) — required by CONTRIBUTING.md, and applies to AI-assisted commits too. Per-repo `user.email` is set to a GitHub no-reply address so the maintainer's real email stays out of public history; don't override it.

## Local dev

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi 'uvicorn[standard]' sqlalchemy pydantic pydantic-settings \
    'python-jose[cryptography]' httpx python-multipart bcrypt pyotp
uvicorn app.main:app --reload   # binds :8000

# Frontend
cd ../frontend
npm install
npm run dev                      # binds :5173
```

The backend cookie is set with `secure=True`, so the login flow does **not** work on plain HTTP (no localhost override). Local dev requires either a TLS-terminating proxy or a temporary code change — proxy through your deployed instance and iterate against prod, or run `docker compose up` locally and front it with self-signed TLS.

### Local TLS overlay (recommended)

The cleanest local-dev path mirrors the chemex nginx vhost in front of the same backend/frontend containers. Add two files (both gitignored, so they never reach the deploy host):

- `docker-compose.override.yml` — adds a `caddy:2-alpine` service on the existing `internal` network, exposed on `127.0.0.1:<port>:443`, with `./Caddyfile.local` mounted at `/etc/caddy/Caddyfile`.
- `Caddyfile.local` — `task-panda.localhost { tls internal }` plus the same `/api/*` → `backend:8000`, `/*` → `frontend:3000` split as `deploy/nginx.example.conf`.

`task-panda.localhost` resolves to 127.0.0.1 in modern browsers (RFC 6761), so no hosts-file edit. Set `APP_BASE_URL=https://task-panda.localhost:<port>` in your local `.env`. First request: accept the browser cert warning once, or import Caddy's local CA from `/data/caddy/pki/authorities/local/root.crt` inside the container.

There are no tests.

### Validating compose YAML locally

`docker compose config` errors out if `.env` doesn't exist, even though it's not needed to validate the schema. To check `docker-compose.yml` without running anything: `cp .env.example .env && docker compose config && rm .env`.

## Helper scripts (`bin/`)

`backend/.venv/` already has `bcrypt` and `pyotp` installed for these:

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

`frontend/` is SvelteKit + Tailwind, built with `@sveltejs/adapter-node` (runs as `node build`). Routes mirror the URL structure 1:1 — pages live under `src/routes/<page>/+page.svelte`. All HTTP goes through `src/lib/api.js`, which always sends `credentials: 'include'` so the auth cookie travels. Same-origin via the nginx split, so CORS is a non-issue in production.

#### Brand assets

`frontend/static/`:
- `logo.png` — full lockup (raccoon + "Task Panda"), used as the login hero
- `logo-mark.png` — raccoon mark only, used in the header (next to a "task panda" wordmark that hides on `<sm` screens)
- `favicon.png`, `icon-192.png`, `icon-512.png` — browser tab + PWA icons (referenced from `manifest.json` and `app.html`)

All transparent-background PNGs derived from `brand/TaskPandaLogoIdea2_*.png`. To regenerate after a logo change, resize the source PNGs into `static/` (any image tool works; the existing files were scaled with `System.Drawing` from PowerShell).

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
