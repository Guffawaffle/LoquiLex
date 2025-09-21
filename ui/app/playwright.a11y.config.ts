import { defineConfig, devices } from '@playwright/test';

/**
 * Minimal Playwright configuration for accessibility testing
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './src/test/e2e',
  testMatch: '**/settings-a11y.spec.ts',
  timeout: 30000,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report-a11y' }]],
  use: {
    baseURL: `http://127.0.0.1:${process.env.LX_API_PORT || '8000'}`,
    trace: 'on-first-retry',
    headless: true,
  },
  projects: [
    {
      name: 'chromium-a11y',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});