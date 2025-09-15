import { test, expect } from '@playwright/test'

const API_BASE_URL = process.env.API_BASE_URL || 'http://127.0.0.1:8000'

test('dual panels render and backend health responds', async ({ page }) => {
	await page.goto('/')
	await expect(page.getByTestId('panel-source')).toBeVisible()
	await expect(page.getByTestId('panel-target')).toBeVisible()

	// Timestamp toggle
	const tsToggle = page.getByRole('switch', { name: /timestamps/i })
	await tsToggle.click()

	// Minimal API sanity (adjust endpoint/route as appropriate)
	const resp = await page.request.get(`${API_BASE_URL}/health`)
	expect(resp.ok()).toBeTruthy()
})
