import { defineConfig, devices } from '@playwright/test';
// Note: This config is for LOCAL a11y checks only. It is NOT part of CI gating.
// It spins up a Vite preview server and runs a focused accessibility suite.
// Avoid adding this to Make/CI paths unless explicitly intended.
// Allow using Node's process without pulling in @types/node for this TS file only.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const process: any;

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
    baseURL: 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
    headless: true,
  },
  webServer: {
    // Build the UI and start a local preview server Playwright connects to
    command: 'npm run build && npm run preview',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    timeout: 120000,
  },
  projects: [
    {
      name: 'chromium-a11y',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});