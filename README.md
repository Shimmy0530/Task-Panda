# Task Panda

A quiet, ADHD-aware focus tool. Self-hosted, single-user.

Each morning you pick one boring-important task, up to four supporting tasks, and run a 25-minute focus session. The aim is a calm interface that gets out of your way — no streaks-as-shame, no notification noise.

## Architecture

- **Frontend:** SvelteKit PWA + Tailwind, `@sveltejs/adapter-node`, dark warm aesthetic
- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Auth:** bcrypt password + optional TOTP 2FA, JWT in HttpOnly cookie
- **LLM + STT:** Groq (OpenAI-compatible chat completions, Whisper) — provider-swappable
- **Reverse proxy:** runs in front of the compose stack and terminates TLS. This README shows a Caddy setup for PC use; the repo also ships an nginx vhost template at `deploy/nginx.example.conf` for a public VM.

No SMTP, no external auth dependencies. The only outbound calls the backend code makes are to the configured `LLM_BASE_URL` (Groq by default).

## Quick start — Docker on your PC

This is the recommended path if you just want to run Task Panda for yourself on your laptop or desktop.

### What you'll need

- **Docker Desktop** (Mac / Windows) or **Docker Engine + Compose v2** (Linux)
- **Git**
- **Python 3.10+** — only used once, to generate your password hash and 2FA seed (a Docker-based alternative is shown below if you'd rather not install Python)
- A **Groq API key** — free signup at https://console.groq.com/keys

### 1. Clone and configure secrets

```bash
git clone https://github.com/Shimmy0530/Task-Panda.git
cd Task-Panda
cp .env.example .env
```

Generate the secret values, then paste them into `.env`:

```bash
# Mac / Linux
python3 -m venv .venv
.venv/bin/pip install bcrypt pyotp

# Session-signing key
JWT=$(openssl rand -hex 64) && perl -i -pe "s|^JWT_SECRET=.*|JWT_SECRET=$JWT|" .env && unset JWT

# Password hash — interactive prompt; copy the printed AUTH_PASSWORD_HASH= line into .env
.venv/bin/python bin/hash-password.py

# Optional 2FA — interactive; copy the AUTH_TOTP_SECRET= line into .env, then
# scan the printed otpauth:// URL with your authenticator app
.venv/bin/python bin/setup-2fa.py
```

Then open `.env` in an editor and set:
- `LLM_API_KEY=<your-groq-key>`
- `APP_BASE_URL=https://localhost`

> **Windows:** replace `python3 -m venv .venv && .venv/bin/...` with `python -m venv .venv && .venv\Scripts\...`.
>
> **No Python at all?** Run the helper scripts in a one-off container instead:
> ```
> docker run --rm -it -v "${PWD}:/work" -w /work python:3.12-slim \
>   bash -c "pip install -q bcrypt pyotp && python bin/hash-password.py"
> ```

### 2. Add a local TLS proxy

The compose stack only ships the backend and frontend — they expect an external reverse proxy to route `/api/*` to the backend, route everything else to the frontend, and terminate TLS. (The auth cookie has `Secure` set, so the login flow needs HTTPS, even on `localhost`.)

For PC use, the simplest setup is Caddy with a self-signed cert. Create two new files in the repo root:

**`docker-compose.override.yml`** (Compose auto-loads files with this name on top of `docker-compose.yml`):

```yaml
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
    networks:
      - internal
    depends_on:
      - backend
      - frontend

volumes:
  caddy_data:
```

**`caddy/Caddyfile`:**

```caddyfile
localhost {
  tls internal

  handle /api/* {
    reverse_proxy backend:8000
  }

  handle {
    reverse_proxy frontend:3000
  }
}
```

`tls internal` makes Caddy generate and trust a self-signed cert for `localhost` automatically.

### 3. Start it up

```bash
docker compose up -d --build
```

First build takes a couple minutes (svelte compile). Subsequent starts are seconds.

Open **https://localhost** in your browser. You'll see a one-time cert warning — accept it. Log in with the password you generated in step 1.

### 4. Day-to-day commands

```bash
docker compose stop          # stop containers (data persists)
docker compose start         # start them again
docker compose logs -f       # follow logs
docker compose restart       # restart everything
docker compose down          # stop + remove containers (DB still persists in ./data/)
```

The SQLite database is bind-mounted at `./data/focus.db` and survives container removal. To wipe it and start clean, delete the file while the stack is down.

### Updating

```bash
git pull
docker compose up -d --build
```

For backend-only changes, append `backend` to the compose command to skip the slow svelte build.

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

## Self-hosting on a public VM

For exposing Task Panda on a real domain (e.g. on a small cloud VM, accessible from anywhere), you'd typically replace the local Caddy override with a host-level reverse proxy that handles a registered TLS cert. The repo ships an nginx vhost template at `deploy/nginx.example.conf` for this path.

### Server prerequisites

- A Linux VM (Ubuntu / Debian assumed below) with **Docker Engine + Compose v2**
- **nginx** installed on the host
- A **TLS certificate** for your domain (Cloudflare Origin, Let's Encrypt, or whatever fits)
- A DNS A/AAAA record pointing your domain at the VM's public IP

### Initial setup on the server

```bash
git clone https://github.com/Shimmy0530/Task-Panda.git ~/task-panda
cd ~/task-panda
cp .env.example .env
nano .env       # paste runtime secrets — see "Quick start" step 1 for how to generate them
chmod 600 .env

# Set APP_BASE_URL=https://your-domain
docker compose up -d --build
```

The compose stack binds backend at `127.0.0.1:17840` and frontend at `127.0.0.1:17841` on the host loopback.

### nginx vhost

Copy the template, edit, drop into `sites-enabled`:

```bash
cp deploy/nginx.example.conf /tmp/task-panda.nginx
nano /tmp/task-panda.nginx   # set server_name + ssl_certificate paths
sudo mv /tmp/task-panda.nginx /etc/nginx/sites-available/task-panda
sudo ln -sf /etc/nginx/sites-available/task-panda /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

The template includes Cloudflare-only IP allowlist blocks — delete them if you're not behind Cloudflare. See the comment at the top of the file.

### Updates

```bash
# local
git push

# server
ssh <server> 'cd ~/task-panda && git pull && docker compose up -d --build'
```

Backend-only edits: append `backend` to the compose command to skip the svelte build.

## Hacking on the code

For active development against the source directly (no Docker, hot-reload):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi 'uvicorn[standard]' sqlalchemy pydantic pydantic-settings \
    'python-jose[cryptography]' httpx python-multipart bcrypt pyotp
uvicorn app.main:app --reload     # :8000

cd ../frontend
npm install
npm run dev                       # :5173
```

**Login won't work over plain HTTP this way.** The auth cookie is set with `Secure`, so the browser drops it on `http://`. To exercise the auth flow, either run the full `docker compose` stack with the Caddy override above, iterate against your deployed instance, or temporarily flip `secure=False` in `backend/app/routers/auth.py` (don't commit that).

## Backups

```bash
# crontab on the server (db is bind-mounted at ./data/focus.db, mounted as /data inside the container)
0 3 * * * docker exec focus-backend sqlite3 /data/focus.db ".backup /data/focus-$(date +\%F).db"
```

For local PC use the same command works pointing at your local `./data/`.

## Changing your password

```bash
python bin/hash-password.py
# update AUTH_PASSWORD_HASH in .env, then:
docker compose restart backend
# All existing sessions stay valid until JWT expiry (30d). To force logout
# everywhere, also rotate JWT_SECRET.
```

## Switching LLM providers

```env
# Example: OpenRouter for chat (keep WHISPER_MODEL on Groq, since OpenRouter doesn't ship Whisper)
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-3.5-sonnet
LLM_API_KEY=sk-or-...
```

If you want LLM and STT on different vendors with separate keys, fork `backend/app/llm.py` and `backend/app/transcribe.py`.

## Scope

Single-user, self-hosted. There's no signup flow, no multi-tenant model, no email — one owner per instance. Auth is a bcrypt password plus optional 2FA. The backend's only outbound calls are to your configured LLM provider.

## Roadmap

- [ ] Push notifications for body-double check-ins
- [ ] Streak with weekly forgiveness
- [ ] Optional CLI for personal Mac
- [ ] Per-month avoidance heatmap

## Contributing

PRs welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). The goal is to improve Task Panda for everyone who uses it.

## Acknowledgements

Task Panda is built with:

- **Frontend:** [SvelteKit](https://kit.svelte.dev/), [Tailwind CSS](https://tailwindcss.com/), [Vite](https://vitejs.dev/)
- **Backend:** [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy](https://www.sqlalchemy.org/), [Pydantic](https://pydantic.dev/)
- **Auth:** [bcrypt](https://github.com/pyca/bcrypt/), [pyotp](https://github.com/pyauth/pyotp), [python-jose](https://github.com/mpdavis/python-jose)
- **LLM + voice:** [Groq](https://groq.com/) (OpenAI-compatible chat completions and Whisper)

Each upstream project is licensed independently — see the dependency manifests for full attribution.

## License

[AGPL-3.0](LICENSE).

In plain language: you're free to use, modify, and self-host Task Panda for any purpose. If you modify it and run it as a public-facing service, you must publish your modifications under the same license. Improvements flow back to the community.
