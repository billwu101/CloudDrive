/**
 * E2E tests for the sharing feature.
 *
 * Covers:
 *   - Share a file with another registered user
 *   - Shared item appears in the recipient's "Shared with me"
 *   - Remove share stops recipient access
 *   - Create a public share link (link copied to clipboard / shown in dialog)
 *
 * Requires both the Vite dev server and FastAPI backend running.
 * Run: npm run test:e2e
 */
import { expect, test } from '@playwright/test'

const TIMESTAMP = Date.now()

const OWNER_EMAIL = `owner_share_${TIMESTAMP}@example.com`
const OWNER_USERNAME = `ownershare${TIMESTAMP}`
const OWNER_PASSWORD = 'ShareTest123!'

const TARGET_EMAIL = `target_share_${TIMESTAMP}@example.com`
const TARGET_USERNAME = `targetshare${TIMESTAMP}`
const TARGET_PASSWORD = 'ShareTest123!'

// ── Setup ─────────────────────────────────────────────────────────────────────

test.beforeAll(async ({ request }) => {
  await request
    .post('/api/v1/auth/register', {
      data: { email: OWNER_EMAIL, username: OWNER_USERNAME, password: OWNER_PASSWORD },
    })
    .catch(() => {})
  await request
    .post('/api/v1/auth/register', {
      data: { email: TARGET_EMAIL, username: TARGET_USERNAME, password: TARGET_PASSWORD },
    })
    .catch(() => {})
})

async function loginAs(page: import('@playwright/test').Page, email: string, password: string) {
  await page.goto('/login')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill(password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL('**/drive', { timeout: 10_000 })
}

async function createFolder(
  page: import('@playwright/test').Page,
  name: string,
): Promise<void> {
  await page.getByRole('button', { name: /new folder/i }).click()
  await page.getByRole('textbox', { name: /folder name/i }).fill(name)
  await page.getByRole('button', { name: /^create$/i }).click()
  await expect(page.getByText(name)).toBeVisible({ timeout: 5_000 })
}

// ── 分享給指定使用者 ──────────────────────────────────────────────────────────

test.describe('Share with a specific user', () => {
  test('shared item appears in target user shared-with-me page', async ({ browser }) => {
    const ownerCtx = await browser.newContext()
    const ownerPage = await ownerCtx.newPage()
    await loginAs(ownerPage, OWNER_EMAIL, OWNER_PASSWORD)

    const folderName = `Shared Folder ${TIMESTAMP}`
    await createFolder(ownerPage, folderName)

    // Open share dialog via right-click context menu
    await ownerPage.getByText(folderName).click({ button: 'right' })
    await ownerPage.getByRole('menuitem', { name: /share/i }).click()

    // Enter target email
    await ownerPage.getByPlaceholder(/email/i).fill(TARGET_EMAIL)
    await ownerPage.getByRole('button', { name: /^share$/i }).click()

    // Confirm share was added (no error shown)
    await expect(
      ownerPage.getByText(TARGET_EMAIL),
    ).toBeVisible({ timeout: 5_000 })

    await ownerCtx.close()

    // Target user checks shared-with-me
    const targetCtx = await browser.newContext()
    const targetPage = await targetCtx.newPage()
    await loginAs(targetPage, TARGET_EMAIL, TARGET_PASSWORD)

    await targetPage.getByRole('link', { name: /shared with me/i }).click()
    await expect(targetPage.getByText(folderName)).toBeVisible({ timeout: 8_000 })

    await targetCtx.close()
  })

  test('removing share stops recipient from seeing the item', async ({ browser }) => {
    const ownerCtx = await browser.newContext()
    const ownerPage = await ownerCtx.newPage()
    await loginAs(ownerPage, OWNER_EMAIL, OWNER_PASSWORD)

    const folderName = `Remove Share ${TIMESTAMP}`
    await createFolder(ownerPage, folderName)

    // Share the folder
    await ownerPage.getByText(folderName).click({ button: 'right' })
    await ownerPage.getByRole('menuitem', { name: /share/i }).click()
    await ownerPage.getByPlaceholder(/email/i).fill(TARGET_EMAIL)
    await ownerPage.getByRole('button', { name: /^share$/i }).click()
    await expect(ownerPage.getByText(TARGET_EMAIL)).toBeVisible({ timeout: 5_000 })

    // Now remove the share
    const removeBtn = ownerPage.getByRole('button', { name: /remove/i }).first()
    if (await removeBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await removeBtn.click()
    }
    // Close dialog
    const closeBtn = ownerPage.getByRole('button', { name: /close|cancel/i }).first()
    if (await closeBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
      await closeBtn.click()
    }

    await ownerCtx.close()

    // Target should NOT see the folder anymore
    const targetCtx = await browser.newContext()
    const targetPage = await targetCtx.newPage()
    await loginAs(targetPage, TARGET_EMAIL, TARGET_PASSWORD)
    await targetPage.getByRole('link', { name: /shared with me/i }).click()
    await expect(targetPage.getByText(folderName)).not.toBeVisible({ timeout: 5_000 })

    await targetCtx.close()
  })
})

// ── 公開分享連結 ──────────────────────────────────────────────────────────────

test.describe('Public share link', () => {
  test('can create a public share link and it is displayed in the dialog', async ({ page }) => {
    await loginAs(page, OWNER_EMAIL, OWNER_PASSWORD)
    const folderName = `Public Link ${TIMESTAMP}`
    await createFolder(page, folderName)

    // Open share dialog
    await page.getByText(folderName).click({ button: 'right' })
    await page.getByRole('menuitem', { name: /share/i }).click()

    // Switch to link tab if needed
    const linkTab = page.getByRole('tab', { name: /link/i })
    if (await linkTab.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await linkTab.click()
    }

    // Create the link
    const createLinkBtn = page.getByRole('button', { name: /create link|generate link/i })
    await expect(createLinkBtn).toBeVisible({ timeout: 5_000 })
    await createLinkBtn.click()

    // A share link should appear (URL or token visible somewhere in dialog)
    const linkText = page.getByText(/\/s\//i)
    const copyBtn = page.getByRole('button', { name: /copy/i })
    const linkVisible =
      (await linkText.isVisible({ timeout: 5_000 }).catch(() => false)) ||
      (await copyBtn.isVisible({ timeout: 1_000 }).catch(() => false))

    expect(linkVisible).toBe(true)
  })
})
