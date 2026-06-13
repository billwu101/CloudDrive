/**
 * E2E tests for core drive operations.
 *
 * Requires both the Vite dev server and FastAPI backend running.
 * Run: npm run test:e2e
 */
import { expect, test } from '@playwright/test'

const TIMESTAMP = Date.now()
const EMAIL = `drive_e2e_${TIMESTAMP}@example.com`
const USERNAME = `driveuser${TIMESTAMP}`
const PASSWORD = 'DriveTest123!'

// ── Shared setup ─────────────────────────────────────────────────────────────

test.beforeAll(async ({ request }) => {
  await request.post('/api/v1/auth/register', {
    data: { email: EMAIL, username: USERNAME, password: PASSWORD },
  }).catch(() => {})
})

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL('**/drive', { timeout: 10_000 })
}

// ── Folder operations ─────────────────────────────────────────────────────────

test.describe('Folder management', () => {
  test('can create a folder and see it in the list', async ({ page }) => {
    await login(page)
    const folderName = `E2E Folder ${TIMESTAMP}`

    await page.getByRole('button', { name: /new folder/i }).click()
    await page.getByRole('textbox', { name: /folder name/i }).fill(folderName)
    await page.getByRole('button', { name: /^create$/i }).click()

    await expect(page.getByText(folderName)).toBeVisible({ timeout: 5_000 })
  })

  test('can rename a folder', async ({ page }) => {
    await login(page)
    const original = `Rename Me ${TIMESTAMP}`
    const renamed = `Renamed ${TIMESTAMP}`

    await page.getByRole('button', { name: /new folder/i }).click()
    await page.getByRole('textbox', { name: /folder name/i }).fill(original)
    await page.getByRole('button', { name: /^create$/i }).click()
    await expect(page.getByText(original)).toBeVisible({ timeout: 5_000 })

    // Right-click to open context menu
    await page.getByText(original).click({ button: 'right' })
    await page.getByRole('menuitem', { name: /rename/i }).click()
    await page.getByRole('textbox', { name: /new name/i }).fill(renamed)
    await page.getByRole('button', { name: /^rename$/i }).click()

    await expect(page.getByText(renamed)).toBeVisible({ timeout: 5_000 })
    await expect(page.getByText(original)).not.toBeVisible()
  })
})

// ── File upload ───────────────────────────────────────────────────────────────

test.describe('File upload', () => {
  test('can upload a file and see it in the list', async ({ page }) => {
    await login(page)

    const filename = `e2e_upload_${TIMESTAMP}.txt`
    const fileInput = page.locator('input[type="file"]')

    await fileInput.setInputFiles({
      name: filename,
      mimeType: 'text/plain',
      buffer: Buffer.from('E2E test upload content'),
    })

    await expect(page.getByText(filename)).toBeVisible({ timeout: 10_000 })
  })
})

// ── Search ────────────────────────────────────────────────────────────────────

test.describe('Search', () => {
  test('can search for an uploaded file', async ({ page }) => {
    await login(page)
    const uniqueName = `searchable_${TIMESTAMP}`

    // Create a folder with a unique name
    await page.getByRole('button', { name: /new folder/i }).click()
    await page.getByRole('textbox', { name: /folder name/i }).fill(uniqueName)
    await page.getByRole('button', { name: /^create$/i }).click()
    await expect(page.getByText(uniqueName)).toBeVisible({ timeout: 5_000 })

    // Search for it
    const searchInput = page.getByPlaceholder(/search/i)
    await searchInput.fill(uniqueName)
    await page.waitForURL(/\/search\?q=/, { timeout: 5_000 })

    await expect(page.getByText(uniqueName)).toBeVisible({ timeout: 5_000 })
  })
})

// ── Trash ─────────────────────────────────────────────────────────────────────

test.describe('Trash', () => {
  test('can move item to trash and restore it', async ({ page }) => {
    await login(page)
    const folderName = `Trash Me ${TIMESTAMP}`

    // Create folder
    await page.getByRole('button', { name: /new folder/i }).click()
    await page.getByRole('textbox', { name: /folder name/i }).fill(folderName)
    await page.getByRole('button', { name: /^create$/i }).click()
    await expect(page.getByText(folderName)).toBeVisible({ timeout: 5_000 })

    // Move to trash via context menu
    await page.getByText(folderName).click({ button: 'right' })
    await page.getByRole('menuitem', { name: /move to trash/i }).click()

    // Confirm in dialog if present
    const confirmBtn = page.getByRole('button', { name: /^move to trash$/i })
    if (await confirmBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
      await confirmBtn.click()
    }

    // Item should disappear from drive
    await expect(page.getByText(folderName)).not.toBeVisible({ timeout: 5_000 })

    // Navigate to trash
    await page.getByRole('link', { name: /^trash$/i }).click()
    await expect(page.getByText(folderName)).toBeVisible({ timeout: 5_000 })

    // Restore
    await page.getByText(folderName).click({ button: 'right' })
    await page.getByRole('button', { name: /^restore$/i }).click()

    // Item should be back in drive
    await page.getByRole('link', { name: /my drive/i }).click()
    await expect(page.getByText(folderName)).toBeVisible({ timeout: 5_000 })
  })
})
