import { expect, test } from '@playwright/test'

const BASE = 'http://localhost:5174'
const API = 'http://localhost:8000/api/v1'
const rand = () => Math.random().toString(36).slice(2, 8)

async function registerViaApi(email: string, username: string, password = 'Password123!') {
  const res = await fetch(`${API}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, username, password }),
  })
  if (!res.ok) throw new Error(`Register failed: ${res.status}`)
}

async function registerViaUi(page: import('@playwright/test').Page) {
  const email = `test_${rand()}@example.com`
  const username = `user_${rand()}`
  const password = 'Password123!'

  await page.goto(`${BASE}/register`)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: /create account/i }).click()
  await page.waitForURL(`${BASE}/drive`)
  return { email, username, password }
}

async function goToSettings(page: import('@playwright/test').Page) {
  await page.locator('[aria-haspopup="menu"]').click()
  await page.getByRole('menuitem', { name: /account settings/i }).click()
  await page.waitForURL(`${BASE}/settings`)
  await expect(page.getByRole('heading', { name: /account settings/i })).toBeVisible()
}

test.describe('Account Settings', () => {
  test('change username successfully', async ({ page }) => {
    const { username } = await registerViaUi(page)
    await goToSettings(page)

    const input = page.getByLabel('Username')
    await expect(input).toHaveValue(username)

    await input.fill('new_username')
    await page.getByRole('button', { name: /save username/i }).click()

    await expect(page.getByText(/username updated/i)).toBeVisible()
    await expect(input).toHaveValue('new_username')
  })

  test('change email successfully', async ({ page }) => {
    const { email } = await registerViaUi(page)
    await goToSettings(page)

    const newEmail = `new_${rand()}@example.com`
    const input = page.getByLabel('Email address')
    await expect(input).toHaveValue(email)

    await input.fill(newEmail)
    await page.getByRole('button', { name: /save email/i }).click()

    await expect(page.getByText(/email updated/i)).toBeVisible()
    await expect(input).toHaveValue(newEmail)
  })

  test('email conflict shows error', async ({ page }) => {
    // create the "taken" account via API (no browser login needed)
    const takenEmail = `taken_${rand()}@example.com`
    await registerViaApi(takenEmail, `taken_${rand()}`)

    // register the actual test user via browser
    await registerViaUi(page)
    await goToSettings(page)

    // try to use the already-taken email
    await page.getByLabel('Email address').fill(takenEmail)
    await page.getByRole('button', { name: /save email/i }).click()

    await expect(page.getByRole('alert')).toContainText(/already/i)
  })

  test('invalid email format is rejected', async ({ page }) => {
    await registerViaUi(page)
    await goToSettings(page)

    await page.getByLabel('Email address').fill('not-an-email')
    await page.getByRole('button', { name: /save email/i }).click()

    await expect(page.getByText(/invalid email/i)).toBeVisible()
  })

  test('change password successfully', async ({ page }) => {
    const { password } = await registerViaUi(page)
    await goToSettings(page)

    await page.getByLabel('Current password').fill(password)
    await page.getByLabel('New password', { exact: true }).fill('NewPassword456!')
    await page.getByLabel('Confirm new password').fill('NewPassword456!')
    await page.getByRole('button', { name: /change password/i }).click()

    await expect(page.getByText(/password changed/i)).toBeVisible()
    await expect(page.getByLabel('Current password')).toHaveValue('')
    await expect(page.getByLabel('New password', { exact: true })).toHaveValue('')
  })

  test('wrong current password shows error', async ({ page }) => {
    await registerViaUi(page)
    await goToSettings(page)

    await page.getByLabel('Current password').fill('wrong_password')
    await page.getByLabel('New password', { exact: true }).fill('NewPassword456!')
    await page.getByLabel('Confirm new password').fill('NewPassword456!')
    await page.getByRole('button', { name: /change password/i }).click()

    await expect(page.getByRole('alert')).toContainText(/incorrect/i)
  })

  test('mismatched passwords are rejected', async ({ page }) => {
    await registerViaUi(page)
    await goToSettings(page)

    await page.getByLabel('Current password').fill('Password123!')
    await page.getByLabel('New password', { exact: true }).fill('NewPassword456!')
    await page.getByLabel('Confirm new password').fill('DifferentPassword!')
    await page.getByRole('button', { name: /change password/i }).click()

    await expect(page.getByText(/do not match/i)).toBeVisible()
  })

  test('new password too short is rejected', async ({ page }) => {
    await registerViaUi(page)
    await goToSettings(page)

    await page.getByLabel('Current password').fill('Password123!')
    await page.getByLabel('New password', { exact: true }).fill('short')
    await page.getByLabel('Confirm new password').fill('short')
    await page.getByRole('button', { name: /change password/i }).click()

    await expect(page.locator('.text-destructive', { hasText: /at least 8/i })).toBeVisible()
  })
})
