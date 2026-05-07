# Focusly

A quiet, ADHD-aware focus tool. Single-user, self-hosted.

Pick one frog, four supporting tasks, and a 25-minute pomodoro. The goal is a calm interface that gets out of your way — no streaks-as-shame, no notification noise.

Live deployment: `https://focus.baltito.com` (private — owner only).

## Stack

- **Frontend:** SvelteKit PWA + Tailwind, `@sveltejs/adapter-node`
- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Auth:** bcrypt password + optional TOTP, JWT in HttpOnly cookie
- **LLM + STT:** Groq (OpenAI-compatible chat completions, Whisper)
- **Reverse proxy:** host nginx + Cloudflare wildcard origin cert

## Repo layout

```
focusly/
├── focus/                 # the app — start here
│   ├── backend/           # FastAPI service
│   ├── frontend/          # SvelteKit app
│   ├── deploy/            # nginx vhost
│   ├── docker-compose.yml
│   └── README.md          # full setup + ops guide
├── CLAUDE.md              # deployment-specific notes (Claude Code aid)
└── README.md              # you are here
```

The app lives in `focus/`; the repo root holds deployment glue and meta-docs.

## Get started

See [`focus/README.md`](focus/README.md) for first-time setup, secrets generation, deploy steps, local dev, and the runbook for password rotation, LLM provider swap, and backups.

## Status

Active and used daily by the owner. Not packaged for outside deployment — secrets layout, hostname, and certificate plumbing are hard-coded for `focus.baltito.com` on `chemex`. Forks are welcome but expect to rewrite `focus/deploy/` and the README's deploy section.

## License

No public license. Source is shared for transparency, not redistribution.
