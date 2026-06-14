import { test } from '@playwright/test'

const BASE = 'http://localhost:5174'
const rand = () => Math.random().toString(36).slice(2, 8)

test('debug settings flow', async ({ page }) => {
  page.on('console', msg => {
    if (msg.type() === 'error') console.log('BROWSER ERR:', msg.text())
  })
  page.on('response', resp => {
    if (resp.url().includes('/api/')) {
      console.log(`API ${resp.request().method()} ${resp.url()} → ${resp.status()}`)
    }
  })

  const email = `test_${rand()}@example.com`
  console.log('Registering:', email)

  await page.goto(`${BASE}/register`)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Username').fill('testuser')
  await page.getByLabel('Password', { exact: true }).fill('Password123!')
  await page.getByLabel('Confirm password').fill('Password123!')
  await page.getByRole('button', { name: /create account/i }).click()

  // Wait for navigation
  await page.waitForURL(`${BASE}/drive`, { timeout: 20000 })
  console.log('Navigated to drive:', page.url())

  // Open user menu
  await page.locator('[aria-haspopup="menu"]').click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: '/tmp/debug2_menu.png' })

  // Click settings
  await page.getByRole('link', { name: /account settings/i }).click()
  await page.waitForURL(`${BASE}/settings`, { timeout: 10000 })
  await page.waitForTimeout(500)
  await page.screenshot({ path: '/tmp/debug2_settings.png' })
  console.log('Settings page loaded, URL:', page.url())

  // Test username change
  await page.getByLabel('Username').fill('new_username')
  await page.getByRole('button', { name: /save username/i }).click()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: '/tmp/debug2_after_save.png' })
  console.log('Done!')
})
