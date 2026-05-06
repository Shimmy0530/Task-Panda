# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo shape

The `focusly/` directory wraps the actual app at `focus/` plus deployment artifacts:

- `focus/` — the SvelteKit + FastAPI app (single-user, self-hosted)
- `focus.tar.gz` — original scaffold tarball (kept for reference; do not edit)
- `.env` — **local staging only**, holds the Groq API key for one-time provisioning. Not used at runtime; `focus/.env` is the actual runtime config.

Treat `focus/` as the project root for almost all work.

## Deployment (deviates from `focus/README.md`)

The README references Caddy and Let's Encrypt — that path was abandoned. Production uses host nginx on chemex with a Cloudflare Origin wildcard cert. When editing deployment, update both files together.

- **Host:** chemex.baltito.com (35.202.245.176), Ubuntu, user `<deploy-user>`. SSH alias: `chemex`.
- **Public URL:** `https://focus.baltito.com` (Cloudflare proxy ON).
- **Cert:** `/etc/ssl/cloudflare/chemex.baltito.com.{pem,key}` is a `*.baltito.com` wildcard valid until 2041 — **no certbot dance for new subdomains on chemex**.
- **Container ports:** backend at `127.0.0.1:17840` (→ container `:8000`), frontend at `127.0.0.1:17841` (→ container `:3000`). nginx splits `/api/*` to backend, everything else to frontend.
- **nginx vhost source:** `focus/deploy/focus.baltito.com.nginx` is checked into the repo. Deployed at `/etc/nginx/sites-available/focus.baltito.com`. nginx on chemex is 1.22.1 — use `listen 443 ssl http2;` syntax, not the standalone `http2 on;` directive.
- **Compose stack** (`focus/docker-compose.yml`): just `backend` and `frontend`, no proxy. They share an `internal` docker network plus host loopback ports. SQLite DB lives in `./data/focus.db` (bind-mounted volume).

### Redeploy

The repo is cloned at `~/focusly` on chemex (private repo `Shimmy0530/focusly`, gh CLI is the credential helper). The runtime `.env` is **not** in git — it lives only at `~/focusly/focus/.env` on chemex (perms 600). The SQLite DB is at `~/focusly/focus/data/focus.db` (also untracked).

```bash
# local
git push

# chemex
ssh chemex 'cd ~/focusly && git pull && cd focus && docker compose up -d --build'
```

For backend-only changes, append `backend` to the compose command to skip the slow svelte build:

```bash
ssh chemex 'cd ~/focusly && git pull && cd focus && docker compose up -d --build backend'
```

`~/focus.bak` on chemex is the legacy scp-tarball deploy preserved during cutover — safe to `rm -rf` once you trust the new layout.

**Container-owned host paths:** anything the containers write (notably `~/focusly/focus/data/`) is owned by root on the host. Host-side `mv`/`rm`/`chown` needs `sudo`.

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

The backend cookie is set with `secure=True`, so the login flow does **not** work on plain HTTP (no localhost override). Local dev requires either a TLS-terminating proxy or a temporary code change — proxy through `https://focus.baltito.com` and iterate against prod, or run `docker compose up` locally and front it with self-signed TLS.

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
- `tasks.py` — CRUD plus `POST /api/tasks/{id}/dictation` for atomic dictation-block appends
- `sessions.py` — pomodoro start/end + today/week dashboards
- `morning.py` — `GET /state` and `POST /complete`/`/skip` for the 4-step ritual
- `capture.py` — intrusive-thoughts inbox + `POST /api/llm/first-action`
- `transcribe.py` — `POST /api/transcribe` (audio → text) and `POST /api/outline` (text → cleaned outline)

The voice flow is **two endpoints, not one**: the frontend uploads audio to `/api/transcribe`, then sends the transcript to `/api/outline` (with optional `task_id` for context), then writes the result via `/api/tasks/{id}/dictation`. An earlier scaffold had a duplicate combined endpoint at `/api/llm/transcribe`; that was removed because it had broken imports (`polish_dictation`, `..stt`).

### Frontend

`focus/frontend` is SvelteKit + Tailwind, built with `@sveltejs/adapter-node` (runs as `node build`). Routes mirror the URL structure 1:1 — pages live under `src/routes/<page>/+page.svelte`. All HTTP goes through `src/lib/api.js`, which always sends `credentials: 'include'` so the auth cookie travels. Same-origin via the nginx split, so CORS is a non-issue in production.

### Domain invariants (enforced server-side)

- **Max 5 tasks per `day_date`**, **max 1 frog (`is_frog=true`) per day**. `tasks.py` raises 400 on violation.
- Morning ritual `complete` payload is the canonical way to plant a frog + supporting cast; it also processes yesterday's open tasks (`carry`/`drop`/`done`) and stamps `User.last_ritual_date`. "Carrying forward" demotes frog status — frogs must be re-chosen each day.
- Dictation appends are atomic: `POST /api/tasks/{id}/dictation` reads `task.notes`, appends a `🎙 dictation · <UTC stamp>` block, commits once.

### LLM + STT

`backend/app/llm.py` is a thin client over an OpenAI-compatible chat-completions API (Groq default). Two functions:
- `first_action(title, notes)` — returns a single ≤5-min concrete action
- `outline_from_transcript(transcript, task_title?, task_notes?)` — returns Markdown outline

`backend/app/transcribe.py` is the Whisper client (`transcribe_audio` → dict with `text`/`duration`/`language`).

To swap providers, edit `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` in `.env`. Whisper requires the same provider unless `transcribe.py` is forked.

## OPSEC rules (from owner; load-bearing)

The owner is a federal agent. **Never put case data anywhere in this app** — task titles, captures, dictation transcripts. The `SYSTEM_OUTLINE` prompt in `llm.py` actively redacts case-like identifiers (names, locations, dates, case refs) into `[SUBJECT]`/`[LOCATION]`/`[DATE]`/`[CASE_REF]` placeholders. Preserve that behavior when editing the prompt — don't relax it.

The backend container's only outbound network destination is `api.groq.com` (per design, not enforced). Audio leaves the user's infra during transcription; the README's OPSEC notice treats dictation as the highest-risk surface.
