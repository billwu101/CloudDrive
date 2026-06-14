import { expect, test } from '@playwright/test'

const BASE = 'http://localhost:5173'

async function registerAndLogin(page: import('@playwright/test').Page) {
  const email = `drag-${Date.now()}@example.com`
  const password = 'Password123!'
  await page.goto(`${BASE}/register`)
  await page.getByLabel('Username').fill('draguser')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: /create account/i }).click()
  await page.waitForURL('**/drive', { timeout: 10_000 })
}

async function createFolders(page: import('@playwright/test').Page, names: string[]) {
  for (const name of names) {
    await page.getByRole('button', { name: /new folder/i }).click()
    await page.getByRole('dialog').getByRole('textbox').fill(name)
    await page.getByRole('button', { name: /^create$/i }).click()
    await page.waitForSelector(`text=${name}`)
  }
  await expect(page.locator('[data-item-id]')).toHaveCount(names.length)
}

/**
 * Drag-select all visible items.
 *
 * Grid view: items don't fill the full container width. We start from the empty
 * space immediately to the RIGHT of the last item, then sweep left+up to cover
 * everything.
 *
 * List view: items are full-width table rows. We start from the table HEADER
 * row (which is inside the container but has no [data-item-id] and no inputs),
 * then sweep right+down to cover all data rows.
 */
async function dragSelectAll(page: import('@playwright/test').Page) {
  const items = page.locator('[data-item-id]')
  expect(await items.count()).toBeGreaterThan(0)

  const firstBox = (await items.first().boundingBox())!
  const lastBox  = (await items.last().boundingBox())!
  const cBox     = (await page.locator('[data-testid="file-list"]').boundingBox())!
  const isListView = await page.locator('[data-testid="file-list"] thead').isVisible()

  let startX: number, startY: number, endX: number, endY: number

  if (isListView) {
    // Header row lives above the first data row (no data-item-id → safe to start drag)
    const headerMidY = cBox.y + (firstBox.y - cBox.y) / 2
    startX = cBox.x + cBox.width / 2
    startY = headerMidY
    endX   = cBox.x + cBox.width - 5
    endY   = cBox.y + cBox.height - 5
  } else {
    // Grid: start in empty space just right of the last item, sweep up-left
    startX = Math.min(lastBox.x + lastBox.width + 20, cBox.x + cBox.width - 5)
    startY = cBox.y + cBox.height - 5
    endX   = cBox.x + 2
    endY   = Math.max(firstBox.y - 2, cBox.y + 1)
  }

  console.log(`  [${isListView ? 'list' : 'grid'}] drag (${startX.toFixed(0)},${startY.toFixed(0)}) → (${endX.toFixed(0)},${endY.toFixed(0)})`)

  await page.mouse.move(startX, startY)
  await page.mouse.down()
  // Initial small moves to exit the 5-px dead-zone
  await page.mouse.move(startX - 3, startY - 3, { steps: 2 })
  await page.mouse.move(startX - 10, startY - 10, { steps: 5 })
  // Main sweep
  await page.mouse.move(endX, endY, { steps: 30 })
  await page.mouse.up()
}

test.describe('Drag-to-select', () => {
  test('grid view: drag sweep selects multiple cards', async ({ page }) => {
    await registerAndLogin(page)
    await createFolders(page, ['Alpha', 'Beta', 'Gamma', 'Delta'])
    await dragSelectAll(page)

    const count = await page.locator('[data-item-id][aria-selected="true"]').count()
    expect(count).toBeGreaterThanOrEqual(2)
    console.log(`✓ Grid: ${count}/4 items selected`)
  })

  test('list view: drag sweep selects multiple rows', async ({ page }) => {
    await registerAndLogin(page)
    await page.getByLabel('List view').click()

    await createFolders(page, ['One', 'Two', 'Three'])
    await dragSelectAll(page)

    const count = await page.locator('[data-item-id][aria-selected="true"]').count()
    expect(count).toBeGreaterThanOrEqual(2)
    console.log(`✓ List: ${count}/3 rows selected`)
  })

  test('rubber-band overlay is visible during drag and gone after release', async ({ page }) => {
    await registerAndLogin(page)
    await createFolders(page, ['P', 'Q', 'R'])

    const lastBox = (await page.locator('[data-item-id]').last().boundingBox())!
    const cBox    = (await page.locator('[data-testid="file-list"]').boundingBox())!
    const startX  = Math.min(lastBox.x + lastBox.width + 20, cBox.x + cBox.width - 5)
    const startY  = cBox.y + cBox.height - 5

    await page.mouse.move(startX, startY)
    await page.mouse.down()
    await page.mouse.move(startX - 3, startY - 3, { steps: 2 })
    await page.mouse.move(startX - 30, startY - 30, { steps: 10 })

    await expect(page.locator('[data-testid="drag-overlay"]')).toBeAttached({ timeout: 2000 })

    await page.mouse.up()
    await expect(page.locator('[data-testid="drag-overlay"]')).not.toBeAttached({ timeout: 2000 })
    console.log('✓ Overlay appears during drag and disappears on release')
  })

  test('click on empty space clears selection', async ({ page }) => {
    await registerAndLogin(page)
    await createFolders(page, ['Solo'])

    const card   = page.locator('[data-item-id]').first()
    await card.click()
    await expect(card).toHaveAttribute('aria-selected', 'true')

    const cardBox = (await card.boundingBox())!
    const cBox    = (await page.locator('[data-testid="file-list"]').boundingBox())!
    // Click to the right of the card (in the same row, but after the card ends)
    const emptyX = cardBox.x + cardBox.width + 20
    if (emptyX < cBox.x + cBox.width) {
      await page.mouse.click(emptyX, cardBox.y + cardBox.height / 2)
      await expect(card).toHaveAttribute('aria-selected', 'false')
      console.log('✓ Click on empty space cleared selection')
    } else {
      console.log('ℹ Skipped: card fills container width')
    }
  })

  test('clicking a card does not trigger drag overlay', async ({ page }) => {
    await registerAndLogin(page)
    await createFolders(page, ['NoDrag'])

    await page.locator('[data-item-id]').first().click()

    await expect(page.locator('[data-testid="drag-overlay"]')).not.toBeAttached()
    await expect(page.locator('[data-item-id]').first()).toHaveAttribute('aria-selected', 'true')
    console.log('✓ Card click selects without triggering drag overlay')
  })

  test('drag-select then bulk trash removes selected items', async ({ page }) => {
    await registerAndLogin(page)
    await createFolders(page, ['Del1', 'Del2', 'Del3'])
    await dragSelectAll(page)

    const n = await page.locator('[data-item-id][aria-selected="true"]').count()
    expect(n).toBeGreaterThanOrEqual(2)

    await page.getByRole('button', { name: /^trash \(/i }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.getByRole('dialog').getByRole('button', { name: /move to trash/i }).click()

    await expect(page.locator('[data-item-id]')).toHaveCount(3 - n, { timeout: 5000 })
    console.log(`✓ Bulk trash removed ${n} items, ${3 - n} remain`)
  })

  test('header select-all checkbox selects and deselects all rows', async ({ page }) => {
    await registerAndLogin(page)
    await page.getByLabel('List view').click()
    await createFolders(page, ['A', 'B', 'C'])

    await page.getByLabel('Select all').click()
    await expect(page.locator('[data-item-id][aria-selected="true"]')).toHaveCount(3)
    console.log('✓ Select-all: 3 rows selected')

    await page.getByLabel('Select all').click()
    await expect(page.locator('[data-item-id][aria-selected="true"]')).toHaveCount(0)
    console.log('✓ Second click: all deselected')
  })
})
