import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.PW_BASE_URL || 'https://task-panda.localhost:17842';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  globalSetup: './tests/global-setup.js',
  use: {
    baseURL: BASE_URL,
    ignoreHTTPSErrors: true,
    storageState: './tests/.auth/owner.json',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: { ...devices['Desktop Chrome'] }
    },
    {
      name: 'chromium-mobile',
      use: { ...devices['Pixel 7'] }
    }
  ]
});
