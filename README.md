# Task Panda

A quiet, ADHD-aware focus tool. Self-hosted, single-user.

Each morning you pick one boring-important task, up to four supporting tasks, and run a 25-minute focus session. The aim is a calm interface that gets out of your way — no streaks-as-shame, no notification noise.

## Stack

- **Frontend:** SvelteKit PWA + Tailwind, `@sveltejs/adapter-node`
- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Auth:** bcrypt password + optional TOTP, JWT in HttpOnly cookie
- **LLM + STT:** Groq (OpenAI-compatible chat completions, Whisper) — provider-swappable
- **Reverse proxy:** host nginx with your own TLS cert (Cloudflare Origin, Let's Encrypt, etc.)

## Repo layout

```
.
├── focus/                 # the app — start here
│   ├── backend/           # FastAPI service
│   ├── frontend/          # SvelteKit app
│   ├── deploy/            # nginx vhost template
│   ├── docker-compose.yml
│   └── README.md          # full setup + ops guide
├── CLAUDE.md              # repo guidance for AI coding assistants
├── CONTRIBUTING.md        # how to propose changes
├── LICENSE                # AGPL-3.0
└── README.md              # you are here
```

Treat `focus/` as the project root for almost all work.

## Get started

See [`focus/README.md`](focus/README.md) for first-time setup, secrets generation, deploy steps, local dev, and the runbook for password rotation, LLM provider swap, and backups.

## Scope

Single-user, self-hosted. There's no signup flow, no multi-tenant model, no email — one owner per instance. Auth is a bcrypt password plus optional 2FA. The backend's only outbound calls are to your configured LLM provider.

## Contributing

PRs welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). The goal is to improve Task Panda for everyone who uses it.

## License

[AGPL-3.0](LICENSE).

In plain language: you're free to use, modify, and self-host Task Panda for any purpose. If you modify it and run it as a public-facing service, you must publish your modifications under the same license. Improvements flow back to the community.
