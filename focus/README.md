# Task Panda

A quiet, ADHD-aware focus tool. Self-hosted, single-user.

## Architecture

- **Frontend:** SvelteKit PWA + Tailwind, dark warm aesthetic
- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Auth:** Password (bcrypt) + optional TOTP 2FA. JWT cookie session.
- **LLM + STT:** Groq via OpenAI-compatible API
- **Reverse proxy:** host nginx (template in `deploy/`), TLS via your own cert (Cloudflare Origin, Let's Encrypt, etc.)

No SMTP, no external auth dependencies. The only outbound calls the backend code makes are to the configured `LLM_BASE_URL` (Groq by default).

## First-time setup

From a working copy of this directory:

```bash
cp .env.example .env

# Helpers need bcrypt + pyotp. Use a venv to keep system Python clean.
python3 -m venv .venv
.venv/bin/pip install bcrypt pyotp

# 1. Session secret
JWT=$(openssl rand -hex 64)
perl -i -pe "s|^JWT_SECRET=.*|JWT_SECRET=$JWT|" .env && unset JWT

# 2. Password hash — interactive, prints AUTH_PASSWORD_HASH='...' line for .env
.venv/bin/python3 bin/hash-password.py

# 3. 2FA (recommended) — prints AUTH_TOTP_SECRET=... and an otpauth:// URI to
#    scan into 1Password / Bitwarden / Aegis / Authy
.venv/bin/python3 bin/setup-2fa.py

# 4. Groq key — grab at https://console.groq.com/keys, paste into LLM_API_KEY
nano .env
```

## Deploy

The compose stack runs just `backend` and `frontend`. The backend binds `127.0.0.1:17840` and the frontend binds `127.0.0.1:17841` on the host — a host nginx fronts them on `:443`.

DNS: point your chosen hostname at the server's public IP. If you proxy through Cloudflare, Origin certs work without certbot.

### One-time setup

On the server:

```bash
gh auth login   # if cloning a private repo
git clone <your-repo-url> ~/task-panda
cd ~/task-panda/focus
nano .env       # paste runtime secrets — see "First-time setup" above
chmod 600 .env

docker compose up -d --build

# nginx vhost — copy the template, replace the server_name and cert paths,
# then drop it in.
cp deploy/nginx.example.conf /tmp/task-panda.nginx
nano /tmp/task-panda.nginx   # set server_name + ssl_certificate paths
sudo mv /tmp/task-panda.nginx /etc/nginx/sites-available/task-panda
sudo ln -sf /etc/nginx/sites-available/task-panda /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Updates

```bash
# local
git push

# server
ssh <server> 'cd ~/task-panda && git pull && cd focus && docker compose up -d --build'
```

Backend-only edits: append `backend` to the compose command to skip the svelte build.

## Local dev

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi 'uvicorn[standard]' sqlalchemy pydantic pydantic-settings \
    'python-jose[cryptography]' httpx python-multipart bcrypt pyotp
uvicorn app.main:app --reload     # :8000

cd frontend
npm install
npm run dev                       # :5173
```

**Login won't work over plain HTTP locally.** The auth cookie is set with `Secure`, so the browser drops it on `http://`. Either run the stack inside `docker compose` behind a self-signed TLS proxy, iterate against the deployed instance, or temporarily flip `secure=False` in `backend/app/routers/auth.py` (don't commit that).

## Routes

| Route | Purpose |
|---|---|
| `/login` | Password (+ optional 2FA) |
| `/morning` | Guided ritual: handle yesterday's open work, name the boring important one, pick up to two more, optionally pull from backlog, hygiene-prompt 30+ day stale items |
| `/plan` | Today's tasks (max 5, exactly one boring important one). Inline subtasks (manual + AI breakdown), S/M/L effort chip, copy-task, footer link to backlog |
| `/backlog` | Things that aren't for today (`day_date IS NULL`). Doesn't count against the day cap. `→ today` graduates a row (subject to cap) |
| `/focus?session=…&task=…` | Fullscreen pomodoro with wake-lock + context overlay; subtask checklist ticks live |
| `/dictate?task=<id>` | Record → Groq Whisper → LLM outline → save to task |
| `/capture` | Inbox of intrusive thoughts (`⌘.` from anywhere) |
| `/review` | Daily + 7-day ratio + AI weekly summary (cached server-side per day) |
| `/settings` | Stuck-task threshold (default 5 days) |

## Hotkeys

- `⌘ .` / `Ctrl .` — open capture modal
- `⌘ ↵` inside capture — save
- `Esc` — close capture

## Backups

```bash
# crontab on the server (db lives at ~/task-panda/focus/data/focus.db, mounted as /data in the container)
0 3 * * * docker exec focus-backend sqlite3 /data/focus.db ".backup /data/focus-$(date +\%F).db"
```

## Changing your password

```bash
python3 bin/hash-password.py
# update AUTH_PASSWORD_HASH in .env, then:
docker compose restart backend
# All existing sessions stay valid until JWT expiry (30d). To force logout
# everywhere, also rotate JWT_SECRET.
```

## Switching LLM providers

```env
# OpenRouter (chat only — keep WHISPER_MODEL on Groq)
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-3.5-sonnet
LLM_API_KEY=sk-or-...
```

If splitting LLM and STT across vendors with separate keys, fork `backend/app/llm.py` and `backend/app/transcribe.py`.

## Roadmap

- [ ] Push notifications for body-double check-ins
- [ ] Streak with weekly forgiveness
- [ ] Optional CLI for personal Mac
- [ ] Per-month avoidance heatmap
