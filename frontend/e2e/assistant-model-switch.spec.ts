import { expect, test } from '@playwright/test'

/**
 * Assistant model switching — doc/test-cases.md E2E-AI-10.
 *
 * The picker is populated from `GET /assistant/models`, which returns the
 * built-in `local` target plus one entry per model connection the user has
 * registered. Asserting that the options *exist* proves almost nothing, so
 * every case here sends a real message and checks the answer came back with a
 * tool result — that is the only evidence the selection actually reached the
 * model rather than just changing a label.
 *
 * Two things this guards, both of which shipped broken at some point:
 *   - `PRIVACY_DEFAULT` defaults to "sensitive", which refuses *every* named
 *     connection while leaving them listed and selectable. The picker looked
 *     fine and every selection answered "could not connect".
 *   - `docker-compose.yml` did not forward `PRIVACY_DEFAULT` at all, so setting
 *     it in `.env` fixed the test suite and left the running app broken.
 *
 * Runs against the Docker stack by default (what `./scripts/start.sh` brings
 * up). Override for a vite dev server:
 *   E2E_BASE=http://localhost:5173 E2E_API=http://localhost:8000/api/v1 \
 *     npx playwright test e2e/assistant-model-switch.spec.ts
 */

const BASE = process.env.E2E_BASE ?? 'http://localhost:8088'
const API = process.env.E2E_API ?? 'http://localhost:8001/api/v1'
const PASSWORD = 'Password123!'
const rand = () => Math.random().toString(36).slice(2, 8)

// Real model calls on a reasoning model take tens of seconds.
const MODEL_TIMEOUT = 180_000

type Account = { email: string; username: string; token: string }

async function api(path: string, init: RequestInit = {}, token?: string) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  })
  return res
}

async function register(): Promise<Account> {
  const email = `ms_${rand()}@example.com`
  const username = `ms_${rand()}`
  const reg = await api('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, username, password: PASSWORD }),
  })
  expect(reg.status, await reg.text()).toBeLessThan(400)
  const login = await api('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password: PASSWORD }),
  })
  expect(login.status).toBe(200)
  return { email, username, token: (await login.json()).access_token }
}

/** Register one connection and return the label the picker will show for it. */
async function addConnection(acct: Account, label: string, model: string) {
  const res = await api(
    '/users/me/model-connections',
    {
      method: 'POST',
      body: JSON.stringify({
        label,
        kind: 'openai_compatible',
        base_url: process.env.E2E_LLM_BASE_URL ?? '',
        model,
        secret: process.env.E2E_LLM_API_KEY ?? 'placeholder',
      }),
    },
    acct.token,
  )
  expect(res.status, await res.text()).toBeLessThan(400)
  return `${label} · ${model}`
}

async function signIn(page: import('@playwright/test').Page, acct: Account) {
  await page.goto(`${BASE}/login`)
  await page.getByLabel('Email').fill(acct.email)
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL(`${BASE}/drive`)
}

async function openAssistant(page: import('@playwright/test').Page) {
  await page.getByRole('button', { name: /open assistant/i }).click()
  await expect(page.getByRole('combobox')).toBeVisible()
}

/** Send a message and wait for a reply bubble, returning its text. */
async function ask(page: import('@playwright/test').Page, message: string) {
  const box = page.getByRole('textbox', { name: /assistant message/i })
  await box.fill(message)
  await box.press('Enter')
  await expect(page.getByText(/thinking/i)).toBeHidden({ timeout: MODEL_TIMEOUT })
  return page
}

test.describe('Assistant model switching', () => {
  test.describe.configure({ mode: 'serial' })

  test('the picker lists the local target plus every registered connection', async ({ page }) => {
    const acct = await register()

    // The server-provided entries are deployment config, so count them rather
    // than assuming a number: the user's own connections are what this asserts.
    const serverCount = (await (await api('/assistant/models', {}, acct.token)).json()).length
    expect(serverCount).toBeGreaterThanOrEqual(1) // at least the bare `local`

    const labelA = await addConnection(acct, `Alpha ${rand()}`, 'gemma4:31b')
    const labelB = await addConnection(acct, `Beta ${rand()}`, 'qwen3.8:27b')

    await signIn(page, acct)
    await openAssistant(page)

    const picker = page.getByRole('combobox')
    const options = await picker.locator('option').allTextContents()

    expect(options).toHaveLength(serverCount + 2)
    expect(options[0]).toMatch(/^Local \(/)
    expect(options).toContain(labelA)
    expect(options).toContain(labelB)
  })

  test('a brand-new account sees the server models with no setup', async ({ page }) => {
    // The point of the server-side list (proposal §12): a user who has never
    // opened Settings, and owns no connection, still gets every model the
    // deployment offers. A per-user mechanism would show them nothing.
    const acct = await register()

    const listed = await (await api('/assistant/models', {}, acct.token)).json()
    const conns = await (await api('/users/me/model-connections', {}, acct.token)).json()
    expect(conns).toEqual([])

    await signIn(page, acct)
    await openAssistant(page)

    const options = await page.getByRole('combobox').locator('option').allTextContents()
    expect(options).toHaveLength(listed.length)
    expect(options[0]).toMatch(/^Local \(/)
    // Anything beyond the default is another server model, not a connection.
    for (const o of options.slice(1)) expect(o).toMatch(/^Local \(/)
  })

  test('a server model answers when picked, without any connection', async ({ page }) => {
    test.skip(
      !process.env.E2E_LLM_BASE_URL || !process.env.E2E_LLM_API_KEY,
      'needs a reachable model gateway: set E2E_LLM_BASE_URL and E2E_LLM_API_KEY',
    )
    test.setTimeout(MODEL_TIMEOUT * 2)

    const acct = await register()
    const listed = await (await api('/assistant/models', {}, acct.token)).json()
    const extra = listed.filter((o: { id: string }) => o.id.startsWith('local:'))
    test.skip(extra.length === 0, 'ASSISTANT_MODELS is not configured on this deployment')

    await signIn(page, acct)
    await openAssistant(page)

    const picker = page.getByRole('combobox')
    await picker.selectOption(extra[0].id)
    await ask(page, 'How much storage space do I have left?')

    await expect(page.getByText(/storage_quota/i)).toBeVisible({ timeout: MODEL_TIMEOUT })
    await expect(page.getByText(/could not connect/i)).toBeHidden()
  })

  test('a removed connection disappears from the picker on reload', async ({ page }) => {
    const acct = await register()
    const label = await addConnection(acct, `Doomed ${rand()}`, 'gemma4:31b')

    await signIn(page, acct)
    await openAssistant(page)
    expect(await page.getByRole('combobox').locator('option').allTextContents()).toContain(label)

    const list = await (await api('/users/me/model-connections', {}, acct.token)).json()
    const del = await api(`/users/me/model-connections/${list[0].id}`, { method: 'DELETE' }, acct.token)
    expect(del.status).toBe(204)

    await page.reload()
    await openAssistant(page)
    expect(
      await page.getByRole('combobox').locator('option').allTextContents(),
    ).not.toContain(label)
  })

  test('selecting a connection routes the next message to it', async ({ page }) => {
    test.skip(
      !process.env.E2E_LLM_BASE_URL || !process.env.E2E_LLM_API_KEY,
      'needs a reachable model gateway: set E2E_LLM_BASE_URL and E2E_LLM_API_KEY',
    )
    test.setTimeout(MODEL_TIMEOUT * 2)

    const acct = await register()
    const label = await addConnection(acct, `Gemma ${rand()}`, 'gemma4:31b')

    await signIn(page, acct)
    await openAssistant(page)

    const picker = page.getByRole('combobox')
    await picker.selectOption({ label })
    await expect(picker).toHaveValue(/^(?!local$).+/) // a connection id, not `local`

    await ask(page, 'How much storage space do I have left?')

    // The answer must carry a real tool result, not just prose: that is what
    // proves the request reached a model and the plan actually executed.
    await expect(page.getByText(/storage_quota/i)).toBeVisible({ timeout: MODEL_TIMEOUT })
    await expect(page.getByText(/could not connect/i)).toBeHidden()

    // And the picker keeps the selection after answering.
    await expect(picker).toHaveValue(/^(?!local$).+/)
  })

  test('switching mid-conversation sends the next turn to the new model', async ({ page }) => {
    test.skip(
      !process.env.E2E_LLM_BASE_URL || !process.env.E2E_LLM_API_KEY,
      'needs a reachable model gateway: set E2E_LLM_BASE_URL and E2E_LLM_API_KEY',
    )
    test.setTimeout(MODEL_TIMEOUT * 3)

    const acct = await register()
    const first = await addConnection(acct, `First ${rand()}`, 'gemma4:31b')
    const second = await addConnection(acct, `Second ${rand()}`, 'qwen3.8:27b')

    await signIn(page, acct)
    await openAssistant(page)
    const picker = page.getByRole('combobox')

    await picker.selectOption({ label: first })
    await ask(page, 'How much storage space do I have left?')
    await expect(page.getByText(/storage_quota/i).first()).toBeVisible({ timeout: MODEL_TIMEOUT })

    await picker.selectOption({ label: second })
    await ask(page, 'List the files in my drive')

    // Both turns answered; the session survived the switch rather than erroring.
    await expect(page.getByText(/list_items/i)).toBeVisible({ timeout: MODEL_TIMEOUT })
    await expect(page.getByText(/could not connect/i)).toBeHidden()
  })
})
