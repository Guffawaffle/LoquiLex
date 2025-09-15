import { defineConfig, devices } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

export default defineConfig({
	testDir: './tests/e2e',
	webServer: {
		command: 'npx vite --port 5173',
		url: BASE_URL,
		reuseExistingServer: true,
		timeout: 30000,
	},
	use: {
		baseURL: BASE_URL,
		trace: 'on-first-retry',
	},
	projects: [
		{ name: 'chromium', use: { ...devices['Desktop Chrome'] } },
	],
})
