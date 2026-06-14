/**
 * Headed demo — drag-select scope restriction.
 * Shows real-time cursor position, a visible cursor dot,
 * and a status banner for each scenario.
 *
 * Run with:
 *   npx playwright test e2e/demo-drag-select.spec.ts --headed --project=chromium
 */
import { expect, test } from '@playwright/test'

const BASE  = 'http://localhost:5173'
const PAUSE = 1400   // ms between steps

/** Inject a floating cursor-dot + coordinate label that track mousemove */
async function injectCursorTracker(page: import('@playwright/test').Page) {
  await page.evaluate(() => {
    // Cursor dot
    const dot = document.createElement('div')
    dot.id = '__cursor_dot'
    dot.style.cssText = `
      position:fixed; width:16px; height:16px; border-radius:50%;
      background:rgba(234,67,53,0.85); border:2px solid #fff;
      pointer-events:none; z-index:99999;
      transform:translate(-50%,-50%); transition:none;`
    document.body.appendChild(dot)

    // Coordinate label
    const label = document.createElement('div')
    label.id = '__cursor_label'
    label.style.cssText = `
      position:fixed; background:rgba(0,0,0,0.72); color:#fff;
      padding:2px 7px; border-radius:4px; font:600 11px/1.6 monospace;
      pointer-events:none; z-index:99999; white-space:nowrap;`
    document.body.appendChild(label)

    document.addEventListener('mousemove', (e) => {
      dot.style.left = e.clientX + 'px'
      dot.style.top  = e.clientY + 'px'
      label.style.left = (e.clientX + 14) + 'px'
      label.style.top  = (e.clientY + 14) + 'px'
      label.textContent = `(${e.clientX}, ${e.clientY})`
    })
  })
}

async function setBanner(page: import('@playwright/test').Page, text: string, color = '#1d4ed8') {
  await page.evaluate(({ text, color }) => {
    let b = document.getElementById('__demo_banner')
    if (!b) {
      b = document.createElement('div')
      b.id = '__demo_banner'
      b.style.cssText = `
        position:fixed; top:12px; left:50%; transform:translateX(-50%);
        padding:8px 22px; border-radius:8px;
        font:600 14px/1.4 sans-serif; z-index:9998; pointer-events:none;
        white-space:nowrap; box-shadow:0 2px 8px rgba(0,0,0,.25);`
      document.body.appendChild(b)
    }
    b.style.background = color
    b.style.color = '#fff'
    b.textContent = text
  }, { text, color })
}

test('Demo: drag-select scope — main only, not sidebar/topbar', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 })

  // ── Register & Login ──────────────────────────────────────────────────────
  const email = `demo-${Date.now()}@example.com`
  await page.goto(`${BASE}/register`)
  await page.getByLabel('Username').fill('demouser')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill('Password123!')
  await page.getByLabel('Confirm password').fill('Password123!')
  await page.getByRole('button', { name: /create account/i }).click()
  await page.waitForURL('**/drive', { timeout: 10_000 })

  // Inject cursor tracker after page load
  await injectCursorTracker(page)

  // ── Create folders ────────────────────────────────────────────────────────
  for (const name of ['Alpha', 'Beta', 'Gamma', 'Delta']) {
    await page.getByRole('button', { name: /new folder/i }).click()
    await page.getByRole('dialog').getByRole('textbox').fill(name)
    await page.getByRole('button', { name: /^create$/i }).click()
    await page.waitForSelector(`text=${name}`)
  }
  await page.waitForTimeout(PAUSE)

  // ── Scene 1: drag inside main content → selects files ────────────────────
  await setBanner(page, '① 從主內容空白處拖移框選')
  await page.waitForTimeout(PAUSE)

  const cBox    = (await page.locator('[data-testid="file-list"]').boundingBox())!
  const lastBox = (await page.locator('[data-item-id]').last().boundingBox())!

  const startX = Math.min(lastBox.x + lastBox.width + 30, cBox.x + cBox.width - 10)
  const startY = cBox.y + cBox.height - 8
  const endX   = cBox.x + 4
  const endY   = cBox.y + 4

  await page.mouse.move(startX, startY)
  await page.waitForTimeout(400)
  await page.mouse.down()
  await page.mouse.move(startX - 8, startY - 8, { steps: 5 })
  await page.mouse.move(endX, endY, { steps: 50 })
  await page.waitForTimeout(PAUSE)
  await page.mouse.up()
  await page.waitForTimeout(PAUSE)

  const selected1 = await page.locator('[data-item-id][aria-selected="true"]').count()
  await setBanner(page, `✓ 成功選取 ${selected1} 個項目`, '#16a34a')
  await page.waitForTimeout(PAUSE * 2)

  // ── Scene 2: drag from SIDEBAR → no overlay ───────────────────────────────
  // Clear selection
  await page.mouse.click(startX, cBox.y + cBox.height / 2)
  await page.waitForTimeout(PAUSE / 2)

  await setBanner(page, '② 從左側 Sidebar 拖移 → 不應出現選框', '#b45309')
  await page.waitForTimeout(PAUSE)

  const sidebarX = 80
  const sidebarY = 320

  await page.mouse.move(sidebarX, sidebarY)
  await page.waitForTimeout(500)
  await page.mouse.down()
  await page.mouse.move(sidebarX + 20, sidebarY + 20, { steps: 5 })
  await page.mouse.move(800, 400, { steps: 50 })
  await page.waitForTimeout(PAUSE)

  const overlayInSidebar = (await page.locator('[data-testid="drag-overlay"]').count()) > 0
  await page.mouse.up()
  await page.waitForTimeout(PAUSE)

  await setBanner(
    page,
    overlayInSidebar ? '✗ 出現了選框（錯誤）' : '✓ Sidebar 拖移：沒有出現選框',
    overlayInSidebar ? '#dc2626' : '#16a34a',
  )
  await page.waitForTimeout(PAUSE * 2)

  // ── Scene 3: drag from TOPBAR → no overlay ───────────────────────────────
  await setBanner(page, '③ 從上方 TopBar 空白處拖移 → 不應出現選框', '#b45309')
  await page.waitForTimeout(PAUSE)

  const topbarX = 580
  const topbarY = 24

  await page.mouse.move(topbarX, topbarY)
  await page.waitForTimeout(500)
  await page.mouse.down()
  await page.mouse.move(topbarX + 20, topbarY + 20, { steps: 5 })
  await page.mouse.move(800, 400, { steps: 50 })
  await page.waitForTimeout(PAUSE)

  const overlayInTopbar = (await page.locator('[data-testid="drag-overlay"]').count()) > 0
  await page.mouse.up()
  await page.waitForTimeout(PAUSE)

  await setBanner(
    page,
    overlayInTopbar ? '✗ 出現了選框（錯誤）' : '✓ TopBar 拖移：沒有出現選框',
    overlayInTopbar ? '#dc2626' : '#16a34a',
  )
  await page.waitForTimeout(PAUSE * 2)

  // ── Done ─────────────────────────────────────────────────────────────────
  await setBanner(page, '🎉 Demo 完成', '#1d4ed8')
  await page.waitForTimeout(PAUSE * 3)

  // Assertions
  expect(selected1).toBeGreaterThanOrEqual(2)
  expect(overlayInSidebar).toBe(false)
  expect(overlayInTopbar).toBe(false)
})
