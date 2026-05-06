# Focus

A quiet, ADHD-aware focus tool. Self-hosted, single-user, accessed at `https://focus.baltito.com`.

## Architecture

- **Frontend:** SvelteKit PWA + Tailwind, dark warm aesthetic
- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Auth:** Password (bcrypt) + optional TOTP 2FA. JWT cookie session.
- **LLM + STT:** Groq via OpenAI-compatible API
- **Reverse proxy:** host nginx (see `deploy/focus.baltito.com.nginx`), TLS via Cloudflare Origin wildcard cert

No SMTP, no external auth dependencies. The only outbound calls the backend code makes are to the configured `LLM_BASE_URL` (Groq by default). Network egress is not firewall-restricted at the container level — that's a property of the code, not an enforced sandbox.

## ⚠️ OPSEC — read first

You are a federal employee. This tool is on a personally-owned VM and audio passes through Groq.

- **No case data anywhere.** Not in task titles, capture, or dictation.
- **Abstractions only:** ✅ `"Q3 inspection report"` ❌ `"HM Pharmacy Winnetka writeup"`.
- **Dictation is the highest risk surface.** Audio leaves your infra.
- Treat the tool like a public Trello board.

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

## Deploy (chemex)

```bash
# DNS:  A record focus.baltito.com  →  35.202.245.176  (Cloudflare proxy ON)

# Containers bind 127.0.0.1:17840 (backend) and 127.0.0.1:17841 (frontend).
docker compose up -d --build
docker compose logs -f

# nginx vhost (one-time) — wildcard cert at /etc/ssl/cloudflare/ already covers focus.baltito.com
sudo cp deploy/focus.baltito.com.nginx /etc/nginx/sites-available/focus.baltito.com
sudo ln -sf /etc/nginx/sites-available/focus.baltito.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

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
| `/morning` | Guided 4-step ritual (frog + supporting cast) |
| `/plan` | Today's tasks (max 5, exactly one frog) |
| `/focus?session=…&task=…` | Fullscreen pomodoro with wake-lock + context overlay |
| `/dictate?task=<id>` | Record → Groq Whisper → LLM outline → save to task |
| `/capture` | Inbox of intrusive thoughts (`⌘.` from anywhere) |
| `/review` | Daily + 7-day frog ratio |

## Hotkeys

- `⌘ .` / `Ctrl .` — open capture modal
- `⌘ ↵` inside capture — save
- `Esc` — close capture

## Backups

```bash
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
- [ ] Optional `frog` CLI for personal Mac
- [ ] Per-month avoidance heatmap
