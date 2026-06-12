import { expect, test } from '@playwright/test'

test('loads the initial application page', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Cloud Drive' })).toBeVisible()
  await expect(page.getByText('Frontend online')).toBeVisible()
})
