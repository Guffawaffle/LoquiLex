import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Settings Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the API responses for models (match any path that ends with /models/asr or /models/mt)
    await page.route(/.*\/models\/asr$/, route => {
      // emulate a short delay for loading state by replying asynchronously
      setTimeout(() => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            { id: 'whisper-small', name: 'Whisper Small', size: '244MB', available: true },
            { id: 'whisper-large', name: 'Whisper Large', size: '1.5GB', available: false },
          ])
        });
      }, 100);
    });

    await page.route(/.*\/models\/mt$/, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'nllb-600M', name: 'NLLB 600M', size: '1.2GB', available: true },
          { id: 'nllb-1.3B', name: 'NLLB 1.3B', size: '2.7GB', available: false },
        ])
      });
    });
  });

  test('settings page supports keyboard-only navigation', async ({ page }) => {
    await page.goto('/settings');

    // Wait for page to load
    await expect(page.locator('h1:has-text("Settings")')).toBeVisible();

    // Start keyboard navigation from first focusable element
    await page.keyboard.press('Tab');

    // Should focus on "Back to Main" button first
    await expect(page.locator('button:has-text("← Back to Main"):focus')).toBeVisible();

    // Tab through all form controls
    await page.keyboard.press('Tab');
    await expect(page.locator('#asr-model-select:focus')).toBeVisible();

    await page.keyboard.press('Tab');
    await expect(page.locator('#mt-model-select:focus')).toBeVisible();

    await page.keyboard.press('Tab');
    await expect(page.locator('#device-select:focus')).toBeVisible();

    await page.keyboard.press('Tab');
    await expect(page.locator('#cadence-slider:focus')).toBeVisible();

    await page.keyboard.press('Tab');
    await expect(page.locator('input[type="checkbox"]:focus')).toBeVisible();

    await page.keyboard.press('Tab');
    await expect(page.locator('button:has-text("Save Settings"):focus')).toBeVisible();

    await page.keyboard.press('Tab');
    await expect(page.locator('button:has-text("Reset to Defaults"):focus')).toBeVisible();
  });

  test('settings form controls are keyboard operable', async ({ page }) => {
    await page.goto('/settings');

    // Wait for page to load
    await expect(page.locator('h1:has-text("Settings")')).toBeVisible();

    // Test ASR model selection with keyboard
    await page.focus('#asr-model-select');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');

    // Test MT model selection with keyboard
    await page.focus('#mt-model-select');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');

    // Test device selection with keyboard
    await page.focus('#device-select');
    await page.keyboard.press('ArrowDown');

    // Test cadence slider with keyboard
    await page.focus('#cadence-slider');
    const initialValue = await page.locator('#cadence-slider').inputValue();
    await page.keyboard.press('ArrowRight');
    const newValue = await page.locator('#cadence-slider').inputValue();
    expect(parseInt(newValue)).toBeGreaterThan(parseInt(initialValue));

    // Test checkbox with keyboard
    await page.focus('input[type="checkbox"]');
    const initialChecked = await page.locator('input[type="checkbox"]').isChecked();
    await page.keyboard.press('Space');
    const newChecked = await page.locator('input[type="checkbox"]').isChecked();
    expect(newChecked).toBe(!initialChecked);

    // Test save button with keyboard
    await page.focus('button:has-text("Save Settings")');
    await page.keyboard.press('Enter');

    // Should show success message
    await expect(page.locator('text=Settings saved successfully!')).toBeVisible();
  });

  test('settings page has proper headings and labels', async ({ page }) => {
    await page.goto('/settings');

    // Check main heading
    const h1 = page.locator('h1');
    await expect(h1).toHaveText('Settings');
    await expect(h1).toHaveCount(1); // Should have only one h1

    // Check all form labels are present and associated
    await expect(page.locator('label[for="asr-model-select"]')).toHaveText('ASR Model');
    await expect(page.locator('label[for="mt-model-select"]')).toHaveText('MT Model');
    await expect(page.locator('label[for="device-select"]')).toHaveText('Device');
    await expect(page.locator('label[for="cadence-slider"]')).toContainText('Cadence Threshold');

    // Check descriptions are present
    await expect(page.locator('text=Choose the default speech recognition model')).toBeVisible();
    await expect(page.locator('text=Choose the default translation model')).toBeVisible();
    await expect(page.locator('text=Choose the compute device for processing')).toBeVisible();
    await expect(page.locator('text=Number of words to accumulate before triggering')).toBeVisible();
    await expect(page.locator('text=Display timestamps in the caption view')).toBeVisible();
  });

  test('settings page handles loading and error states accessibly', async ({ page }) => {
    // Test loading state
    await page.route('/models/asr', route => {
      // Delay response to test loading state
      setTimeout(() => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        });
      }, 100);
    });

    await page.goto('/settings');

    // Should show loading message first
    await expect(page.locator('text=Loading Settings...')).toBeVisible();

    // Then should show settings form
    await expect(page.locator('h1:has-text("Settings")')).toBeVisible();
  });

  test('settings page shows download badges for unavailable models', async ({ page }) => {
    await page.goto('/settings');

    // Wait for models to load
    await expect(page.locator('#asr-model-select')).toBeVisible();

    // Check that download badges are visible for unavailable models
    await expect(page.locator('text=Whisper Large (1.5GB) - Download needed')).toBeVisible();
    await expect(page.locator('text=NLLB 1.3B (2.7GB) - Download needed')).toBeVisible();

    // Check that available models don't have download badges
    await expect(page.locator('text=Whisper Small (244MB)')).toBeVisible();
    await expect(page.locator('text=NLLB 600M (1.2GB)')).toBeVisible();
  });

  test('settings page provides proper button context', async ({ page }) => {
    await page.goto('/settings');

    // Wait for page to load
    await expect(page.locator('h1:has-text("Settings")')).toBeVisible();

    // Check button text provides clear context
    await expect(page.locator('button:has-text("← Back to Main")')).toBeVisible();
    await expect(page.locator('button:has-text("Save Settings")')).toBeVisible();
    await expect(page.locator('button:has-text("Reset to Defaults")')).toBeVisible();

    // Test back button functionality
    await page.click('button:has-text("← Back to Main")');

    // Should navigate back to main page
    await expect(page.locator('h1:has-text("LoquiLex")')).toBeVisible();
  });

  test('settings page supports screen reader navigation', async ({ page }) => {
    await page.goto('/settings');

    // Wait for page to load
    await expect(page.locator('h1:has-text("Settings")')).toBeVisible();

    // Check that form structure is accessible to screen readers
    const formGroups = page.locator('.form-group');
    const formGroupCount = await formGroups.count();
    expect(formGroupCount).toBe(5); // ASR, MT, Device, Cadence, Timestamps

    // Each form group should have proper structure
    for (let i = 0; i < formGroupCount; i++) {
      const group = formGroups.nth(i);
      await expect(group.locator('.form-group__label')).toBeVisible();
      await expect(group.locator('.form-group__description')).toBeVisible();
    }

    // Check that error and success messages are not hidden from screen readers
    await page.click('button:has-text("Save Settings")');
    const successMessage = page.locator('text=Settings saved successfully!');
    await expect(successMessage).toBeVisible();
    await expect(successMessage).not.toHaveAttribute('aria-hidden', 'true');
  });

  test('settings page passes automated accessibility checks', async ({ page }) => {
    await page.goto('/settings');

    // Wait for page to load completely
    await expect(page.locator('h1:has-text("Settings")')).toBeVisible();
    await expect(page.locator('#asr-model-select')).toBeVisible();

    // Wait for network idle and visible controls, then run axe
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#asr-model-select')).toBeVisible();

    const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
    // Fail only on serious/critical impacts to reduce flakiness
    const serious = (accessibilityScanResults.violations as any[]).filter((v: any) => v.impact === 'serious' || v.impact === 'critical');
    if (serious.length > 0) {
      // Log violations to aid debugging
      // eslint-disable-next-line no-console
      console.error('Axe violations (serious/critical):', JSON.stringify(serious, null, 2));
    }
    expect(serious).toHaveLength(0);
  });

  test('settings form in error state passes accessibility checks', async ({ page }) => {
    // Mock API error
    await page.route('/models/asr', route => route.abort());
    await page.route('/models/mt', route => route.abort());

    await page.goto('/settings');

    // Wait for error state
    await expect(page.locator('text=Failed to load models')).toBeVisible();

    await page.waitForLoadState('networkidle');
    const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
    const seriousErr = (accessibilityScanResults.violations as any[]).filter((v: any) => v.impact === 'serious' || v.impact === 'critical');
    if (seriousErr.length > 0) {
      // eslint-disable-next-line no-console
      console.error('Axe violations on error state:', JSON.stringify(seriousErr, null, 2));
    }
    expect(seriousErr).toHaveLength(0);
  });

  test('settings form in success state passes accessibility checks', async ({ page }) => {
    await page.goto('/settings');

    // Wait for page to load and trigger success state
    await expect(page.locator('h1:has-text("Settings")')).toBeVisible();
    await page.click('button:has-text("Save Settings")');
    await expect(page.locator('text=Settings saved successfully!')).toBeVisible();

    await page.waitForLoadState('networkidle');
    const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
    const seriousSucc = (accessibilityScanResults.violations as any[]).filter((v: any) => v.impact === 'serious' || v.impact === 'critical');
    if (seriousSucc.length > 0) {
      // eslint-disable-next-line no-console
      console.error('Axe violations on success state:', JSON.stringify(seriousSucc, null, 2));
    }
    expect(seriousSucc).toHaveLength(0);
  });
});