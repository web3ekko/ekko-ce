import { test, expect } from '@playwright/test';

test.describe('Dashboard Alert Creation', () => {
    test.beforeEach(async ({ page }) => {
        // Mock authenticated state
        const authState = {
            state: {
                isAuthenticated: true,
                user: { id: 'test-user', email: 'test@example.com' },
                tokens: { access: 'mock-token', refresh: 'mock-refresh' }
            },
            version: 0
        };

        await page.goto('/');
        await page.evaluate((state) => {
            localStorage.setItem('ekko-auth-storage', JSON.stringify(state));
        }, authState);

        // Reload to apply auth state
        await page.reload();
    });

    test('should open create alert modal when clicking the input box', async ({ page }) => {
        // Navigate to dashboard
        await page.goto('/dashboard');

        // Wait for the dashboard to load
        await expect(page.getByText('Welcome back')).toBeVisible();

        // Find the Natural Language Alert Input
        // It has a placeholder like "Alert me when..."
        const alertInput = page.getByPlaceholder(/Alert me when|Notify when|Alert on/);
        await expect(alertInput).toBeVisible();

        // Click the input
        await alertInput.click();

        // Verify the modal opens
        // The modal title is "Create New Alert"
        const modalTitle = page.getByRole('heading', { name: 'Create New Alert' });
        await expect(modalTitle).toBeVisible();

        // Verify the optimized create alert form is present
        await expect(page.getByText('Advanced Options')).toBeVisible();
    });

    test('should open create alert modal when clicking the header button', async ({ page }) => {
        await page.goto('/dashboard');

        // Wait for animations
        await page.waitForTimeout(1000);

        // Find the Create alert button in the header
        // Use a more specific selector if possible, or relax it
        const headerButton = page.getByRole('button', { name: /Create alert/i }).first();
        await expect(headerButton).toBeVisible({ timeout: 10000 });
        await headerButton.click();

        // Verify modal opens
        await expect(page.getByRole('heading', { name: 'Create New Alert' })).toBeVisible();
    });

    test('should open create alert modal when clicking the quick action', async ({ page }) => {
        await page.goto('/dashboard');

        // Wait for animations
        await page.waitForTimeout(1000);

        // Find the Quick Action card for Create alert
        // The card contains the text "Create alert"
        const quickAction = page.locator('.mantine-Card-root').filter({ hasText: 'Create alert' }).first();
        await expect(quickAction).toBeVisible({ timeout: 10000 });
        await quickAction.click();

        // Verify modal opens
        await expect(page.getByRole('heading', { name: 'Create New Alert' })).toBeVisible();
    });
});
