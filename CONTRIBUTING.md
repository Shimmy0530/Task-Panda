# Contributing to Task Panda

Thanks for thinking about contributing. Task Panda is a small, opinionated, single-user focus tool — but improvements that make it calmer, faster, or less in-the-way are welcome.

## Project layout

The app lives in [`focus/`](focus/). Treat that as the project root for almost all work:

- `focus/backend/` — FastAPI + SQLAlchemy + SQLite
- `focus/frontend/` — SvelteKit + Tailwind
- `focus/deploy/` — nginx vhost template

## Local dev

See [`focus/README.md`](focus/README.md) for the full setup (secrets, env, Docker compose). Quick version:

```bash
# Backend
cd focus/backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi 'uvicorn[standard]' sqlalchemy pydantic pydantic-settings \
    'python-jose[cryptography]' httpx python-multipart bcrypt pyotp
uvicorn app.main:app --reload   # :8000

# Frontend
cd focus/frontend
npm install
npm run dev                     # :5173
```

Heads up: the auth cookie is `Secure`, so login won't work over plain HTTP. To exercise the auth flow you'll need to run the full Docker Compose stack behind a TLS proxy, or temporarily flip `secure=False` in `backend/app/routers/auth.py` (don't commit that).

There is no test suite yet. Please describe in your PR what you manually verified.

## Submitting a PR

1. Fork the repo and create a topic branch off `main`.
2. Make your change. Keep PRs focused — one logical change per PR.
3. **Sign off your commits** (see DCO below).
4. Open a PR against `main`. Include a short description: what changed, why, and what you tested.

Squash-merge is the default — your individual commit messages don't have to be perfect, but the PR title should read well as a single line in `git log`.

## Copy style

User-facing strings stay plain and accessible. Avoid productivity-nerd jargon ("eat the frog," "MVP," "OKR," "deep work," "kanban"). The data layer keeps internal metaphors (the `is_frog` column, 🐸 emoji), but UI text reads in plain English: "the boring important one," "do first," etc.

The user-facing product name is **Task Panda**. Code identifiers, container names, and DB columns currently still say `focus`/`is_frog` — that's a deferred rename, not a goal. Please don't refactor identifiers in unrelated PRs.

## Developer Certificate of Origin (DCO)

Task Panda uses the [Developer Certificate of Origin](https://developercertificate.org/) instead of a CLA. The DCO is a lightweight statement that you have the right to contribute the code you're submitting — no separate paperwork, just a `Signed-off-by` line on each commit.

To sign off, add `-s` to your commit:

```bash
git commit -s -m "your message"
```

This appends a `Signed-off-by: Your Name <your@email>` line. By including it, you certify the statements at <https://developercertificate.org/>.

PRs without sign-off will be asked to add it before merge.

## Reporting security issues

Please don't open public issues for security problems. Use GitHub's private vulnerability reporting (the repo's **Security** tab → **Report a vulnerability**).

## License

By contributing, you agree your contributions will be licensed under the [AGPL-3.0](LICENSE).
