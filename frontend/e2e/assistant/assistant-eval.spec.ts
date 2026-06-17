/**
 * Assistant eval — Browser runner (E2 + execution).
 *
 * Reads the same eval cases as the API/mock runners (handed in as JSON via
 * EVAL_CASES_FILE by backend/eval/runner_browser.py) and drives the real UI.
 *
 * Two case kinds:
 *  - chat cases: log in → open panel → send prompt → capture `/assistant/chat`
 *    → assert UI → optionally confirm a pending plan.
 *  - execution cases (`execute` block): additionally seed a fixture file into the
 *    drive (via the API), approve the generated skill, right-click the fixture and
 *    run the skill, capture the `/skills/{id}/execute` response, and download the
 *    produced files' text — so the Python `verify_execution` can assert the
 *    skill's real output (content included).
 *
 * Launched with playwright.eval.config.ts against an already-running frontend.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

interface ExecuteMeta {
  fixture: string
  context_menu_label: string | null
}
interface BrowserCase {
  id: string
  prompt: string
  auto_confirm: boolean
  execute?: ExecuteMeta
}

const CASES_FILE = process.env.EVAL_CASES_FILE
const RESULTS_FILE = process.env.EVAL_RESULTS_FILE
const API_BASE = process.env.EVAL_API_BASE_URL ?? 'http://localhost:8001/api/v1'
const FIXTURES_DIR = process.env.EVAL_FIXTURES_DIR ?? ''
const STAMP = process.env.EVAL_STAMP ?? String(Date.now())
const EMAIL = process.env.EVAL_EMAIL ?? `eval_${STAMP}@example.com`
const USERNAME = process.env.EVAL_USERNAME ?? `eval${STAMP}`
const PASSWORD = process.env.EVAL_PASSWORD ?? 'E2ePassword123!'
const CHAT_TIMEOUT = Number(process.env.EVAL_CHAT_TIMEOUT ?? 300_000)

const cases: BrowserCase[] = CASES_FILE
  ? (JSON.parse(readFileSync(CASES_FILE, 'utf8')) as BrowserCase[])
  : []

const results: Record<string, unknown> = {}
let token = ''

function mimeFor(name: string): string {
  if (name.endsWith('.png')) return 'image/png'
  if (name.endsWith('.pdf')) return 'application/pdf'
  if (name.endsWith('.tar')) return 'application/x-tar'
  return 'text/plain'
}

function authHeaders(): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

async function login(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL('**/drive', { timeout: 30_000 })
}

async function openAssistant(page: Page): Promise<void> {
  const toggle = page.getByRole('button', { name: 'Open assistant' })
  await expect(toggle).toBeVisible({ timeout: 30_000 })
  await toggle.click()
  await expect(page.getByLabel('Assistant message')).toBeVisible({ timeout: 10_000 })
}

async function sendPrompt(page: Page, prompt: string): Promise<Record<string, unknown>> {
  const chat = page.waitForResponse(
    (r) => r.url().includes('/assistant/chat') && r.request().method() === 'POST',
    { timeout: CHAT_TIMEOUT },
  )
  await page.getByLabel('Assistant message').fill(prompt)
  await page.getByRole('button', { name: /send message/i }).click()
  return (await (await chat).json()) as Record<string, unknown>
}

// List the output folder a skill created (named "<stem> (extracted)") and
// download each produced file's text so the verifier can check content.
async function fetchProduced(
  request: APIRequestContext,
  uploadName: string,
): Promise<{ produced: string[]; outputs: Record<string, string | null> }> {
  const stem = uploadName.replace(/\.[^.]+$/, '')
  const rootRes = await request.get(`${API_BASE}/drive/items?page_size=200`, {
    headers: authHeaders(),
  })
  const root = (await rootRes.json()) as { items: { id: string; name: string; item_type: string }[] }
  const folder = root.items.find(
    (i) => i.item_type === 'FOLDER' && i.name.startsWith(`${stem} (extracted)`),
  )
  const produced: string[] = []
  const outputs: Record<string, string | null> = {}
  if (!folder) return { produced, outputs }
  const stack = [folder.id]
  while (stack.length) {
    const pid = stack.pop() as string
    const listRes = await request.get(`${API_BASE}/drive/items?parent_id=${pid}&page_size=200`, {
      headers: authHeaders(),
    })
    const list = (await listRes.json()) as {
      items: { id: string; name: string; item_type: string }[]
    }
    for (const it of list.items) {
      if (it.item_type === 'FOLDER') {
        stack.push(it.id)
        continue
      }
      produced.push(it.name)
      const dl = await request.get(`${API_BASE}/download/${it.id}`, { headers: authHeaders() })
      try {
        outputs[it.name] = await dl.text()
      } catch {
        outputs[it.name] = null
      }
    }
  }
  return { produced, outputs }
}

test.describe('assistant eval (browser)', () => {
  test.beforeAll(async ({ request }) => {
    const reg = await request
      .post(`${API_BASE}/auth/register`, {
        data: { email: EMAIL, username: USERNAME, password: PASSWORD },
      })
      .catch(() => null)
    if (reg && reg.ok()) {
      token = ((await reg.json()) as { access_token: string }).access_token
    } else {
      const login = await request.post(`${API_BASE}/auth/login`, {
        data: { email: EMAIL, password: PASSWORD },
      })
      token = ((await login.json()) as { access_token: string }).access_token
    }
  })

  test.afterAll(() => {
    if (RESULTS_FILE) {
      writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2))
    }
  })

  if (cases.length === 0) {
    test('no eval cases supplied', () => {
      test.skip(true, 'EVAL_CASES_FILE not set or empty')
    })
  }

  for (const evalCase of cases) {
    test(`case: ${evalCase.id}`, async ({ page, request }) => {
      if (evalCase.execute) {
        await runExecutionCase(page, request, evalCase, evalCase.execute)
      } else {
        await runChatCase(page, evalCase)
      }
    })
  }
})

async function runChatCase(page: Page, evalCase: BrowserCase): Promise<void> {
  await login(page)
  await openAssistant(page)
  const body = await sendPrompt(page, evalCase.prompt)
  results[evalCase.id] = body

  const message = typeof body.message === 'string' ? body.message : ''
  if (message) {
    await expect(page.getByText(message.slice(0, 24), { exact: false }).first()).toBeVisible({
      timeout: 15_000,
    })
  }
  const plan = (body.plan ?? null) as { status?: string } | null
  const proposal = (body.skill_proposal ?? null) as { name?: string } | null
  if (proposal?.name) {
    await expect(page.getByText(/skill proposal/i).first()).toBeVisible({ timeout: 15_000 })
  } else if (plan?.status === 'pending_approval') {
    await expect(page.getByLabel('Workflow plan')).toBeVisible({ timeout: 15_000 })
    if (evalCase.auto_confirm) {
      const confirmed = page.waitForResponse((r) => /\/workflows\/[^/]+\/confirm/.test(r.url()), {
        timeout: CHAT_TIMEOUT,
      })
      await page.getByRole('button', { name: /confirm & run/i }).click()
      await confirmed
    }
  }
}

async function runExecutionCase(
  page: Page,
  request: APIRequestContext,
  evalCase: BrowserCase,
  exec: ExecuteMeta,
): Promise<void> {
  // 1. Seed the fixture into the drive under a per-case unique name (so output
  //    folders don't collide between cases).
  const uploadName = `${evalCase.id.replace(/[^a-z0-9]+/gi, '_')}_${exec.fixture}`
  const buffer = readFileSync(join(FIXTURES_DIR, exec.fixture))
  await request.post(`${API_BASE}/upload/simple`, {
    headers: authHeaders(),
    multipart: {
      file: { name: uploadName, mimeType: mimeFor(exec.fixture), buffer },
    },
  })

  await login(page)
  await openAssistant(page)

  // 2. Generate the skill.
  const body = await sendPrompt(page, evalCase.prompt)
  const proposal = (body.skill_proposal ?? null) as {
    name?: string
    manifest?: { ui?: { context_menu?: { label?: string }[] } }
  } | null
  if (!proposal?.name) {
    results[evalCase.id] = { ok: false, error: 'no skill proposal generated', produced_files: [], outputs: {} }
    return
  }
  // The right-click label is whatever the model named it — read it from the
  // generated manifest rather than assuming a fixed string.
  const generatedLabel = proposal.manifest?.ui?.context_menu?.[0]?.label

  // 3. Approve → install.
  const approved = page.waitForResponse((r) => /\/skills\/[^/]+\/approve/.test(r.url()), {
    timeout: CHAT_TIMEOUT,
  })
  await page.getByRole('button', { name: /^approve/i }).first().click()
  await approved

  // 4. Close the panel and run the skill on the fixture via its right-click action.
  await page.getByRole('button', { name: 'Close assistant' }).click()
  const fileCard = page.getByText(uploadName, { exact: false }).first()
  await expect(fileCard).toBeVisible({ timeout: 15_000 })
  await fileCard.click({ button: 'right' })

  const label = generatedLabel ?? exec.context_menu_label ?? proposal.name
  const execResp = page.waitForResponse(
    (r) => /\/skills\/[^/]+\/execute/.test(r.url()) && r.request().method() === 'POST',
    { timeout: 90_000 },
  )
  await page.getByText(label, { exact: false }).first().click()
  const execBody = (await (await execResp).json()) as {
    message?: string
    output?: { produced_files?: string[]; summary?: unknown }
  }

  // 5. Download what the skill actually produced (names + text content).
  const { produced, outputs } = await fetchProduced(request, uploadName)
  const producedFiles = produced.length
    ? produced
    : (execBody.output?.produced_files ?? [])
  results[evalCase.id] = {
    ok: Boolean(execBody.message) && producedFiles.length > 0,
    error: null,
    produced_files: producedFiles,
    outputs,
    summary: execBody.output?.summary,
  }
}
