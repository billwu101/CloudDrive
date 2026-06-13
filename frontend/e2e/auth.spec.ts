/**
 * E2E tests for auth flows.
 *
 * Requires both the Vite dev server (started by playwright webServer) and
 * the FastAPI backend at VITE_API_BASE_URL (default: http://localhost:8000/api/v1).
 *
 * Run: npm run test:e2e
 */
import { expect, test } from '@playwright/test'

const TIMESTAMP = Date.now()
const TEST_EMAIL = `e2e_${TIMESTAMP}@example.com`
const TEST_USERNAME = `e2euser${TIMESTAMP}`
const TEST_PASSWORD = 'E2ePassword123!'

test.describe('Registration', () => {
  test('user can register a new account', async ({ page }) => {
    await page.goto('/register')
    await expect(page.getByRole('heading', { name: /create account/i })).toBeVisible()

    await page.getByLabel(/email/i).fill(TEST_EMAIL)
    await page.getByLabel(/username/i).fill(TEST_USERNAME)
    await page.getByLabel(/^password$/i).fill(TEST_PASSWORD)
    await page.getByLabel(/confirm password/i).fill(TEST_PASSWORD)
    await page.getByRole('button', { name: /create account/i }).click()

    // After registration, redirected to drive
    await page.waitForURL('**/drive', { timeout: 10_000 })
    await expect(page.getByText(/my drive/i)).toBeVisible()
  })

  test('shows validation error for mismatched passwords', async ({ page }) => {
    await page.goto('/register')
    await page.getByLabel(/email/i).fill(`other_${TIMESTAMP}@example.com`)
    await page.getByLabel(/username/i).fill(`other${TIMESTAMP}`)
    await page.getByLabel(/^password$/i).fill('Password123!')
    await page.getByLabel(/confirm password/i).fill('Different123!')
    await page.getByRole('button', { name: /create account/i }).click()

    await expect(page.getByText(/passwords do not match/i)).toBeVisible()
  })
})

test.describe('Login', () => {
  test.beforeEach(async ({ request }) => {
    // Ensure the test user exists via API
    await request.post('/api/v1/auth/register', {
      data: { email: TEST_EMAIL, username: TEST_USERNAME, password: TEST_PASSWORD },
    }).catch(() => {
      // Ignore 409 if already registered
    })
  })

  test('user can log in with correct credentials', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(TEST_EMAIL)
    await page.getByLabel(/password/i).fill(TEST_PASSWORD)
    await page.getByRole('button', { name: /sign in/i }).click()

    await page.waitForURL('**/drive', { timeout: 10_000 })
    await expect(page.getByText(/my drive/i)).toBeVisible()
  })

  test('shows error for wrong password', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(TEST_EMAIL)
    await page.getByLabel(/password/i).fill('WrongPassword!')
    await page.getByRole('button', { name: /sign in/i }).click()

    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page.getByRole('alert')).toContainText(/invalid|credentials|incorrect/i)
  })

  test('redirects to login when visiting protected route unauthenticated', async ({ page }) => {
    await page.goto('/drive')
    await page.waitForURL('**/login', { timeout: 5_000 })
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
  })
})

test.describe('Logout', () => {
  test('user can log out and is redirected to login', async ({ page }) => {
    // Log in first
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(TEST_EMAIL)
    await page.getByLabel(/password/i).fill(TEST_PASSWORD)
    await page.getByRole('button', { name: /sign in/i }).click()
    await page.waitForURL('**/drive', { timeout: 10_000 })

    // Log out via sidebar/menu
    await page.getByRole('button', { name: /logout|sign out/i }).click()
    await page.waitForURL('**/login', { timeout: 5_000 })
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()

    // Visiting drive redirects back to login
    await page.goto('/drive')
    await page.waitForURL('**/login', { timeout: 5_000 })
  })
})
