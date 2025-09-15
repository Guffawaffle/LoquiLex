import { defineConfig, devices } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

export default defineConfig({
	testDir: './tests/e2e',
	use: {
		baseURL: BASE_URL,
		trace: 'on-first-retry',
	},
	projects: [
		{ name: 'chromium', use: { ...devices['Desktop Chrome'] } },
	],
})
