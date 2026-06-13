import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    // E2E tests hit the real FastAPI backend; credentials needed for cookies
    extraHTTPHeaders: {
      Origin: 'http://127.0.0.1:5173',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1',
    url: 'http://127.0.0.1:5173',
    // Allow reusing an already-running dev server to speed up repeated runs
    reuseExistingServer: !process.env.CI,
  },
})
