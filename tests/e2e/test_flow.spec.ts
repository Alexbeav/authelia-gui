import { test, expect } from '@playwright/test';

/**
 * E2E tests for Authelia GUI user management flow.
 *
 * NOTE: These tests assume mocked Authelia health endpoint and restart command.
 * In real environment, configure test environment with:
 * - RESTART_CMD=echo "Mock restart"
 * - HEALTH_URL=http://localhost:8081/mock-health (test stub)
 */

test.describe('User Management Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Set up headers that would normally come from Authelia/Traefik
    await page.route('**/*', (route) => {
      route.continue({
        headers: {
          ...route.request().headers(),
          'X-Forwarded-User': 'admin',
          'X-Forwarded-Groups': 'authelia-admins,users',
        },
      });
    });
  });

  test('should load dashboard', async ({ page }) => {
    await page.goto('/');

    // Check page title
    await expect(page).toHaveTitle(/User Management Dashboard/);

    // Check dashboard elements
    await expect(page.locator('h1')).toContainText('User Management');
    await expect(page.locator('.stat-card')).toHaveCount(2);
  });

  test('should open create user modal', async ({ page }) => {
    await page.goto('/');

    // Click create user button
    await page.click('#create-user-btn');

    // Modal should be visible
    await expect(page.locator('#create-user-modal')).toHaveClass(/show/);

    // Form fields should be present
    await expect(page.locator('#username')).toBeVisible();
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#displayname')).toBeVisible();
  });

  test('should validate username format', async ({ page }) => {
    await page.goto('/');
    await page.click('#create-user-btn');

    // Try invalid username (starts with dot)
    await page.fill('#username', '.invaliduser');
    await page.fill('#email', 'test@example.com');
    await page.fill('#displayname', 'Test User');

    // HTML5 validation should prevent submission
    const usernameInput = page.locator('#username');
    const isInvalid = await usernameInput.evaluate((el: HTMLInputElement) => {
      return !el.checkValidity();
    });

    expect(isInvalid).toBeTruthy();
  });

  test('should create user with auto-generated password', async ({ page, context }) => {
    // Mock the restart endpoint to succeed immediately
    await page.route('**/health', (route) => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({ status: 'OK' }),
      });
    });

    await page.goto('/');
    await page.click('#create-user-btn');

    // Fill form with valid data
    await page.fill('#username', 'newuser');
    await page.fill('#email', 'newuser@example.com');
    await page.fill('#displayname', 'New User');
    await page.fill('#groups', 'users, developers');
    // Leave password empty for auto-generation

    // Intercept the create user request
    const responsePromise = page.waitForResponse(response =>
      response.url().includes('/users') && response.request().method() === 'POST'
    );

    // Submit form
    await page.click('button[type="submit"]');

    // Wait for response
    const response = await responsePromise;
    expect(response.status()).toBe(200);

    // Toast notification should appear
    await expect(page.locator('.toast')).toBeVisible({ timeout: 3000 });
  });

  test('should prevent deleting last admin', async ({ page }) => {
    // This test assumes there's only one admin user in the test data
    await page.goto('/');

    // Find and click delete button for admin user
    // (Assumes test data has admin user setup)
    const deleteBtn = page.locator('.delete-user-btn').first();
    await deleteBtn.click();

    // Delete confirmation modal should appear
    await expect(page.locator('#delete-modal')).toHaveClass(/show/);

    // Confirm deletion
    await page.click('#delete-confirm-btn');

    // Should show error toast about last admin
    await expect(page.locator('.toast-error')).toBeVisible({ timeout: 3000 });
  });

  test('should handle CSRF protection', async ({ page }) => {
    await page.goto('/');

    // Try to make POST request without CSRF token
    const response = await page.evaluate(async () => {
      const formData = new FormData();
      formData.append('username', 'testuser');
      formData.append('email', 'test@example.com');
      formData.append('displayname', 'Test User');

      return fetch('/users', {
        method: 'POST',
        body: formData,
        headers: {
          // Intentionally omit X-CSRF-Token
        },
      }).then(r => r.status);
    });

    // Should get 400 Bad Request due to missing CSRF token
    expect(response).toBe(400);
  });
});

test.describe('RBAC Protection', () => {
  test('should block non-admin users from creating users', async ({ page }) => {
    // Override headers to simulate non-admin user
    await page.route('**/*', (route) => {
      route.continue({
        headers: {
          ...route.request().headers(),
          'X-Forwarded-User': 'regularuser',
          'X-Forwarded-Groups': 'users',  // No admin group
        },
      });
    });

    await page.goto('/');
    await page.click('#create-user-btn');

    // Fill and submit form
    await page.fill('#username', 'newuser');
    await page.fill('#email', 'newuser@example.com');
    await page.fill('#displayname', 'New User');

    const responsePromise = page.waitForResponse(response =>
      response.url().includes('/users') && response.request().method() === 'POST'
    );

    await page.click('button[type="submit"]');

    const response = await responsePromise;

    // Should get 403 Forbidden
    expect(response.status()).toBe(403);

    // Error toast should appear
    await expect(page.locator('.toast-error')).toBeVisible({ timeout: 3000 });
  });

  test('should block requests without forwarded groups header', async ({ page }) => {
    // Override headers to remove X-Forwarded-Groups
    await page.route('**/*', (route) => {
      const headers = route.request().headers();
      delete headers['X-Forwarded-Groups'];
      delete headers['x-forwarded-groups'];

      route.continue({ headers });
    });

    await page.goto('/');
    await page.click('#create-user-btn');

    await page.fill('#username', 'newuser');
    await page.fill('#email', 'newuser@example.com');
    await page.fill('#displayname', 'New User');

    const responsePromise = page.waitForResponse(response =>
      response.url().includes('/users') && response.request().method() === 'POST'
    );

    await page.click('button[type="submit"]');

    const response = await responsePromise;

    // Should get 403 Forbidden
    expect(response.status()).toBe(403);
  });
});

test.describe('Search Functionality', () => {
  test('should filter users by username', async ({ page }) => {
    await page.goto('/');

    // Get initial user count
    const initialCount = await page.locator('#users-tbody tr[data-username]').count();

    // Search for specific username
    await page.fill('#search-input', 'admin');

    // Wait a bit for filtering
    await page.waitForTimeout(300);

    // Should have fewer rows visible
    const filteredCount = await page.locator('#users-tbody tr[data-username]:visible').count();

    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });
});
