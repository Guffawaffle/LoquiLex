# Testing Documentation

## Overview
This directory contains comprehensive tests for the LoquiLex UI application.

## Test Structure
- **Unit Tests**: Located in `__tests__` directories alongside components
- **E2E Tests**: Located in `e2e/` directory for end-to-end testing
- **Test Setup**: Configuration in `setup.ts`

## Running Tests

### Unit Tests
```bash
# Run all unit tests
npm test

# Run tests in watch mode
npm run test:ui:watch

# Run specific test file
npm test src/components/__tests__/SettingsView.test.tsx
```

### E2E Tests
```bash
# Install browsers first (required)
npx playwright install

# Run all E2E tests
npm run e2e

# Run only accessibility tests
npm run e2e:a11y
```

## Settings Component Tests

### Unit Tests Coverage (24 tests)
- **Schema Rendering**: Validates all form elements and structure
- **Form Gating**: Tests loading states and validation behavior
- **Tooltips/Descriptions**: Ensures all form fields have proper descriptions
- **Restart Badges**: Tests download needed indicators for unavailable models
- **Form Interactions**: Model selection, device selection, slider, checkbox
- **State Management**: Success/error states, settings persistence, reset functionality

### Accessibility Tests Coverage
- **Form Labels**: Proper association between labels and form controls
- **Heading Hierarchy**: Correct use of heading elements (h1, etc.)
- **Keyboard Navigation**: Tab order and keyboard operability
- **ARIA Attributes**: Proper ARIA labeling for complex controls
- **Screen Reader Support**: State announcements and error messages
- **Focus Management**: Visible focus indicators and logical tab order

### E2E Accessibility Tests
- **Keyboard-Only Navigation**: Complete form navigation without mouse
- **Form Control Operability**: All controls work with keyboard
- **Automated Accessibility Scans**: Uses axe-core for WCAG compliance
- **State-Specific Testing**: Loading, error, and success states
- **Real Browser Testing**: Tests actual user experience

## Test Patterns

### Unit Test Structure
```typescript
describe('ComponentName', () => {
  beforeEach(() => {
    // Setup mocks and initial state
  });

  it('should describe expected behavior', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Expected Text')).toBeInTheDocument();
    });
  });
});
```

### Accessibility Test Patterns
```typescript
// Label association
expect(screen.getByLabelText('Field Name')).toBeInTheDocument();

// Keyboard navigation
await page.keyboard.press('Tab');
await expect(page.locator(':focus')).toBeVisible();

// ARIA attributes
expect(slider).toHaveAttribute('min', '1');
expect(slider).toHaveAttribute('max', '8');

// Automated accessibility scan
const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
expect(accessibilityScanResults.violations).toEqual([]);
```

## Mock Patterns
- **API Responses**: Mock fetch for model loading
- **Settings Module**: Mock localStorage operations
- **Router Navigation**: Mock React Router for component testing

## CI/CD Integration
- Unit tests run on every commit
- E2E tests require browser installation: `npx playwright install`
- All tests must pass for PR approval
- Accessibility violations fail the build

## Troubleshooting

### Common Issues
1. **Playwright Browser Install Fails**: Network issues in CI environments
   - Solution: Use `npx playwright install --force` or skip E2E in CI
2. **React Act Warnings**: Async state updates not wrapped in act()
   - Expected behavior: These warnings don't fail tests but indicate timing issues
3. **Mock Issues**: Global fetch or module mocks not working
   - Solution: Check mock setup in beforeEach blocks

### Debug Tips
- Use `screen.debug()` to see rendered component structure
- Use `--ui` flag with Vitest for interactive debugging
- Use Playwright's trace viewer for E2E test debugging