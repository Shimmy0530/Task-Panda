import { test, expect } from '@playwright/test';
import { execSync } from 'node:child_process';

function resetWelcomedAt() {
  execSync(
    `docker compose exec -T backend python -c "from app.db import SessionLocal; from app.models import User; db=SessionLocal(); db.query(User).update({User.welcomed_at: None}); db.commit()"`,
    { encoding: 'utf8' }
  );
}

function readWelcomedAt(username = 'owner') {
  const out = execSync(
    `docker compose exec -T backend python -c "from app.db import SessionLocal; from app.models import User; db=SessionLocal(); u=db.query(User).filter(User.username=='${username}').first(); print(u.welcomed_at)"`,
    { encoding: 'utf8' }
  ).trim();
  return out === 'None' ? null : out;
}

test.beforeEach(async () => {
  resetWelcomedAt();
});

test('happy path: modal appears, steps advance, final CTA navigates to /morning and stamps welcomed_at', async ({ page }) => {
  const welcomeRequests = [];
  page.on('request', (req) => {
    if (req.url().endsWith('/api/auth/welcome')) welcomeRequests.push(req.url());
  });

  await page.goto('/plan');

  const dialog = page.getByRole('dialog', { name: /start with the morning ritual/i });
  await expect(dialog).toBeVisible();
  await expect(page.getByText('1 / 4')).toBeVisible();

  await page.getByRole('button', { name: 'next' }).click();
  await expect(page.getByText('2 / 4')).toBeVisible();
  await expect(page.getByRole('heading', { name: /the plan screen keeps your day small/i })).toBeVisible();

  await page.getByRole('button', { name: 'next' }).click();
  await expect(page.getByText('3 / 4')).toBeVisible();

  await page.getByRole('button', { name: 'next' }).click();
  await expect(page.getByText('4 / 4')).toBeVisible();
  await expect(page.getByRole('heading', { name: /capture catches stray thoughts/i })).toBeVisible();

  await page.getByRole('button', { name: /start your morning ritual/i }).click();

  await page.waitForURL('**/morning');
  await expect(dialog).toBeHidden();

  // welcomed_at should be stamped via POST /api/auth/welcome
  expect(welcomeRequests.length).toBeGreaterThanOrEqual(1);
  expect(readWelcomedAt()).not.toBeNull();

  await page.reload();
  await expect(page.getByRole('dialog', { name: /start with the morning ritual/i })).toBeHidden();
});

test('back button: disabled on step 0, enabled on step 1+, decrements step', async ({ page }) => {
  await page.goto('/plan');
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(page.getByRole('button', { name: 'back' })).toBeDisabled();

  await page.getByRole('button', { name: 'next' }).click();
  await expect(page.getByText('2 / 4')).toBeVisible();
  await expect(page.getByRole('button', { name: 'back' })).toBeEnabled();

  await page.getByRole('button', { name: 'back' }).click();
  await expect(page.getByText('1 / 4')).toBeVisible();
  await expect(page.getByRole('button', { name: 'back' })).toBeDisabled();
});

test('skip tour: dismisses without navigating, stamps welcomed_at, does not re-appear', async ({ page }) => {
  const welcomeRequests = [];
  page.on('request', (req) => {
    if (req.url().endsWith('/api/auth/welcome')) welcomeRequests.push(req.url());
  });

  await page.goto('/plan');
  await expect(page.getByRole('dialog')).toBeVisible();

  // Advance to step 2 first to confirm skip works mid-tour
  await page.getByRole('button', { name: 'next' }).click();
  await expect(page.getByText('2 / 4')).toBeVisible();

  await page.getByRole('button', { name: /skip tour/i }).click();

  await expect(page.getByRole('dialog')).toBeHidden();
  expect(page.url()).toContain('/plan');
  expect(welcomeRequests.length).toBeGreaterThanOrEqual(1);
  expect(readWelcomedAt()).not.toBeNull();

  await page.reload();
  await expect(page.getByRole('dialog')).toBeHidden();
});

test('Esc key dismisses', async ({ page }) => {
  await page.goto('/plan');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
  expect(readWelcomedAt()).not.toBeNull();
});

test('replay from /settings does NOT re-fire POST /api/auth/welcome', async ({ page }) => {
  // First dismiss the modal normally so welcomed_at is stamped
  await page.goto('/plan');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
  const stampedAt = readWelcomedAt();
  expect(stampedAt).not.toBeNull();

  // Now record any /api/auth/welcome requests from this point on
  const welcomeRequests = [];
  page.on('request', (req) => {
    if (req.url().endsWith('/api/auth/welcome')) welcomeRequests.push(req.url());
  });

  await page.goto('/settings');
  await page.getByRole('button', { name: /replay welcome tour/i }).click();

  const dialog = page.getByRole('dialog', { name: /start with the morning ritual/i });
  await expect(dialog).toBeVisible();

  // Step all the way through and click the final CTA — replay must NOT call /welcome
  await page.getByRole('button', { name: 'next' }).click();
  await page.getByRole('button', { name: 'next' }).click();
  await page.getByRole('button', { name: 'next' }).click();
  await page.getByRole('button', { name: /start your morning ritual/i }).click();

  await page.waitForURL('**/morning');
  await expect(dialog).toBeHidden();

  expect(welcomeRequests).toEqual([]);
  // welcomed_at should be unchanged
  expect(readWelcomedAt()).toBe(stampedAt);
});
