import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright config for the assistant *eval* browser runner (E2).
 *
 * Unlike playwright.config.ts (which boots a Vite dev server for the unit-style
 * e2e suite), this config drives an already-running frontend — by default the
 * Docker stack at http://localhost:8088, whose bundle talks to the backend at
 * :8001. The Python bridge (backend/eval/runner_browser.py) invokes it with
 * EVAL_* env vars; nothing here starts a server.
 */
const BASE_URL = process.env.EVAL_BASE_URL ?? 'http://localhost:8088'

export default defineConfig({
  testDir: './e2e/assistant',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  timeout: 360_000,
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
