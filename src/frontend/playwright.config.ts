import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '../../tests/browser',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.CELLXP_WEB_URL ?? 'http://localhost:3000',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: process.env.CELLXP_WEB_URL
    ? undefined
    : {
        command: 'corepack pnpm dev',
        url: 'http://localhost:3000/chat',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
