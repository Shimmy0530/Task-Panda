import { test } from '@playwright/test';
import { execSync } from 'node:child_process';

function resetWelcomedAt() {
  execSync(
    `docker compose exec -T backend python -c "from app.db import SessionLocal; from app.models import User; db=SessionLocal(); db.query(User).update({User.welcomed_at: None}); db.commit()"`,
    { encoding: 'utf8' }
  );
}

test.beforeEach(async () => {
  resetWelcomedAt();
});

test('capture: step 1', async ({ page }) => {
  await page.goto('/plan');
  await page.getByRole('dialog').waitFor();
  await page.screenshot({ path: `test-results/screenshots/step1-${test.info().project.name}.png`, fullPage: false });
});

test('capture: step 4 (final CTA)', async ({ page }) => {
  await page.goto('/plan');
  await page.getByRole('dialog').waitFor();
  await page.getByRole('button', { name: 'next' }).click();
  await page.getByRole('button', { name: 'next' }).click();
  await page.getByRole('button', { name: 'next' }).click();
  await page.screenshot({ path: `test-results/screenshots/step4-${test.info().project.name}.png`, fullPage: false });
});
