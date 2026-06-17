/**
 * Assistant eval — Browser runner (E2).
 *
 * Reads the same eval cases as the API/mock runners (handed in as JSON via
 * EVAL_CASES_FILE by backend/eval/runner_browser.py), then for each case drives
 * the real UI: log in → open the assistant panel → type the prompt → capture the
 * `/assistant/chat` response → assert the UI reacted → (optionally) confirm a
 * pending workflow. The captured chat response per case id is written to
 * EVAL_RESULTS_FILE so the Python harness can run the same deterministic
 * verifier/scoring it uses for the API and in-process runners.
 *
 * This file is not part of the default `npm run test:e2e` suite; it is launched
 * with playwright.eval.config.ts against an already-running frontend.
 */
import { readFileSync, writeFileSync } from 'node:fs'

import { expect, test, type Page } from '@playwright/test'

interface BrowserCase {
  id: string
  prompt: string
  auto_confirm: boolean
}

const CASES_FILE = process.env.EVAL_CASES_FILE
const RESULTS_FILE = process.env.EVAL_RESULTS_FILE
const API_BASE = process.env.EVAL_API_BASE_URL ?? 'http://localhost:8001/api/v1'
const STAMP = process.env.EVAL_STAMP ?? String(Date.now())
const EMAIL = process.env.EVAL_EMAIL ?? `eval_${STAMP}@example.com`
const USERNAME = process.env.EVAL_USERNAME ?? `eval${STAMP}`
const PASSWORD = process.env.EVAL_PASSWORD ?? 'E2ePassword123!'
const CHAT_TIMEOUT = Number(process.env.EVAL_CHAT_TIMEOUT ?? 300_000)

const cases: BrowserCase[] = CASES_FILE
  ? (JSON.parse(readFileSync(CASES_FILE, 'utf8')) as BrowserCase[])
  : []

// Captured `/assistant/chat` response bodies, keyed by case id. Populated as the
// tests run (single worker, sequential) and flushed in afterAll so the Python
// bridge always gets whatever was captured — even if a later UI assertion fails.
const results: Record<string, unknown> = {}

async function login(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL('**/drive', { timeout: 30_000 })
}

async function openAssistant(page: Page): Promise<void> {
  // Wait for the floating toggle to mount (auto-waiting; a bare count() races
  // React and may skip the click, leaving the panel closed).
  const toggle = page.getByRole('button', { name: 'Open assistant' })
  await expect(toggle).toBeVisible({ timeout: 30_000 })
  await toggle.click()
  await expect(page.getByLabel('Assistant message')).toBeVisible({ timeout: 10_000 })
}

test.describe('assistant eval (browser)', () => {
  test.beforeAll(async ({ request }) => {
    // Seed the test user via the backend API (cross-origin from node — no CORS).
    // A 409 (already registered) is fine; ignore any failure here.
    await request
      .post(`${API_BASE}/auth/register`, {
        data: { email: EMAIL, username: USERNAME, password: PASSWORD },
      })
      .catch(() => undefined)
  })

  test.afterAll(() => {
    if (RESULTS_FILE) {
      writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2))
    }
  })

  if (cases.length === 0) {
    test('no eval cases supplied', () => {
      // Nothing to drive — surfaces a clear skip rather than an empty suite error.
      test.skip(true, 'EVAL_CASES_FILE not set or empty')
    })
  }

  for (const evalCase of cases) {
    test(`case: ${evalCase.id}`, async ({ page }) => {
      await login(page)
      await openAssistant(page)

      const chatResponse = page.waitForResponse(
        (response) =>
          response.url().includes('/assistant/chat') && response.request().method() === 'POST',
        { timeout: CHAT_TIMEOUT },
      )

      await page.getByLabel('Assistant message').fill(evalCase.prompt)
      await page.getByRole('button', { name: /send message/i }).click()

      const response = await chatResponse
      const body = (await response.json()) as Record<string, unknown>
      // Record before asserting so the Python verifier sees the backend response
      // regardless of whether the UI assertions below hold.
      results[evalCase.id] = body

      // ── UI assertions ───────────────────────────────────────────────────────
      // The assistant replied: its message renders as a bubble.
      const message = typeof body.message === 'string' ? body.message : ''
      if (message) {
        await expect(page.getByText(message.slice(0, 24), { exact: false }).first()).toBeVisible({
          timeout: 15_000,
        })
      }

      const plan = (body.plan ?? null) as { status?: string } | null
      const proposal = (body.skill_proposal ?? null) as { name?: string } | null

      if (proposal?.name) {
        // A generated skill stops at a pending proposal card (never auto-installs).
        await expect(page.getByText(/skill proposal/i).first()).toBeVisible({ timeout: 15_000 })
      } else if (plan?.status === 'pending_approval') {
        // A write/destructive plan surfaces a confirmation card.
        const planCard = page.getByLabel('Workflow plan')
        await expect(planCard).toBeVisible({ timeout: 15_000 })
        if (evalCase.auto_confirm) {
          const confirmed = page.waitForResponse(
            (response) => /\/workflows\/[^/]+\/confirm/.test(response.url()),
            { timeout: CHAT_TIMEOUT },
          )
          await page.getByRole('button', { name: /confirm & run/i }).click()
          await confirmed
        }
      }
    })
  }
})
