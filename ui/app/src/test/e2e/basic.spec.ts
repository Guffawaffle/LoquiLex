import { test, expect } from '@playwright/test';

test('loads model selection page', async ({ page }) => {
  await page.goto('/');
  
  // Check that we're on the model selection page
  await expect(page.locator('h1')).toContainText('LoquiLex');
  await expect(page.locator('text=Live captioning and translation')).toBeVisible();
});

test('has accessibility basics', async ({ page }) => {
  await page.goto('/');
  
  // Check for main landmarks
  await expect(page.locator('button:has-text("Start Session")')).toBeVisible();
  
  // Verify keyboard navigation works
  await page.keyboard.press('Tab');
  await expect(page.locator(':focus')).toBeVisible();
});

test('displays error when API is unavailable', async ({ page }) => {
  // Mock API failure
  await page.route('/models/asr', route => route.abort());
  await page.route('/models/mt', route => route.abort());
  
  await page.goto('/');
  
  // Should show error message
  await expect(page.locator('text=Failed to load models')).toBeVisible();
});

test('health endpoint responds', async ({ page }) => {
  const response = await page.request.get('/healthz');
  expect(response.ok()).toBeTruthy();
  
  const data = await response.json();
  expect(data).toHaveProperty('status', 'ok');
  expect(data).toHaveProperty('timestamp');
});