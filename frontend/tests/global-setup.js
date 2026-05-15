import { execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

// Mints a session JWT for the existing 'owner' user via the backend's own
// auth.issue_jwt() helper, and resets welcomed_at = NULL so the welcome
// modal flow can be exercised.
//
// We deliberately bypass the /api/auth/login endpoint to avoid needing the
// password — this is verification automation, not the user-flow test.

const USERNAME = 'owner';
const COOKIE_NAME = 'focus_session';
const STATE_PATH = 'tests/.auth/owner.json';
const BASE_URL = process.env.PW_BASE_URL || 'https://task-panda.localhost:17842';

function shell(cmd) {
  return execSync(cmd, { encoding: 'utf8' }).trim();
}

export default async function globalSetup() {
  const jwt = shell(
    `docker compose exec -T backend python -c "from app.auth import issue_jwt; from app.db import SessionLocal; from app.models import User; db=SessionLocal(); u=db.query(User).filter(User.username=='${USERNAME}').first(); db.query(User).update({User.welcomed_at: None}); db.commit(); db.refresh(u); print(issue_jwt(u))"`
  );

  if (!jwt) throw new Error('globalSetup: empty JWT from backend');

  const { hostname } = new URL(BASE_URL);

  const state = {
    cookies: [
      {
        name: COOKIE_NAME,
        value: jwt,
        domain: hostname,
        path: '/',
        expires: -1,
        httpOnly: true,
        secure: true,
        sameSite: 'Lax'
      }
    ],
    origins: []
  };

  mkdirSync(dirname(STATE_PATH), { recursive: true });
  writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
  console.log(`globalSetup: wrote auth state to ${STATE_PATH} for user '${USERNAME}'`);
}
