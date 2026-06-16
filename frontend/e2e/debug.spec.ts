import { test } from '@playwright/test'

const BASE = 'http://localhost:5174'

test('debug register flow', async ({ page }) => {
  page.on('console', msg => console.log('BROWSER:', msg.type(), msg.text()))
  page.on('requestfailed', req => console.log('FAILED:', req.url(), req.failure()?.errorText))
  page.on('response', resp => {
    if (resp.url().includes('/auth/')) {
      console.log('RESPONSE:', resp.url(), resp.status())
    }
  })

  await page.goto(`${BASE}/register`)
  await page.screenshot({ path: '/tmp/debug_register.png' })

  await page.getByLabel('Email').fill('debug_test@example.com')
  await page.getByLabel('Username').fill('debuguser')
  await page.getByLabel('Password', { exact: true }).fill('Password123!')
  await page.getByLabel('Confirm password').fill('Password123!')

  await page.screenshot({ path: '/tmp/debug_before_submit.png' })
  await page.getByRole('button', { name: /create account/i }).click()

  // wait a bit and take screenshot
  await page.waitForTimeout(3000)
  await page.screenshot({ path: '/tmp/debug_after_submit.png' })

  console.log('Current URL:', page.url())
  console.log('Page title:', await page.title())
})
