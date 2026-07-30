import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { StorageUsageBar } from './StorageUsageBar'

const BASE = 'http://localhost:8000/api/v1'
const GB = 1024 ** 3

const QUOTA = {
  quota_bytes: 15 * GB,
  used_bytes: 34 * 1024 * 1024,
  available_bytes: 15 * GB - 34 * 1024 * 1024,
  used_percent: 0.22,
}

const server = setupServer(
  http.get(`${BASE}/snapshots/settings`, () =>
    HttpResponse.json({
      retention_n: 50,
      schedule_enabled: true,
      schedule_interval_minutes: 60,
      quota_bytes: null,
      effective_quota_bytes: 7.5 * GB,
      used_bytes: 4.3 * GB,
    }),
  ),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterEach(() => {
  server.resetHandlers()
  cleanup()
})
afterAll(() => server.close())

function renderBar() {
  useAuthStore.setState({ accessToken: 'tok' })
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <StorageUsageBar quota={QUOTA} />
    </QueryClientProvider>,
  )
}

describe('StorageUsageBar', () => {
  it('keeps files and snapshots on separate meters', async () => {
    renderBar()

    // Two budgets, two bars. Merging them would make a 34 MB drive read as
    // nearly full once snapshots grow.
    expect(screen.getByText('Storage')).toBeInTheDocument()
    expect(await screen.findByText('Snapshots')).toBeInTheDocument()
    expect(screen.getByText('34.0 MB / 15.0 GB')).toBeInTheDocument()
    expect(screen.getByText('4.3 GB / 7.5 GB')).toBeInTheDocument()
  })

  it('measures each meter against its own cap', async () => {
    renderBar()
    await screen.findByText('Snapshots')

    const bars = screen.getAllByRole('progressbar')
    // Files: 34 MB of 15 GB is a rounding error; snapshots: 4.3 of 7.5 GB.
    expect(Number(bars[0]!.getAttribute('aria-valuenow'))).toBeLessThan(1)
    expect(Number(bars[1]!.getAttribute('aria-valuenow'))).toBeCloseTo(57.3, 0)
  })

  it('shows only the file meter before snapshot settings load', () => {
    server.use(
      http.get(`${BASE}/snapshots/settings`, () => HttpResponse.json({}, { status: 500 })),
    )
    renderBar()
    expect(screen.getByText('Storage')).toBeInTheDocument()
    expect(screen.queryByText('Snapshots')).not.toBeInTheDocument()
  })
})
