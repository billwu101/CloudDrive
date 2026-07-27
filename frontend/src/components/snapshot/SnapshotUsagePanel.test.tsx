import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { SnapshotResponse, SnapshotSettingsResponse } from '@/api/types'

import { SnapshotUsagePanel } from './SnapshotUsagePanel'

afterEach(() => cleanup())

const GB = 1024 ** 3

function settings(usedGb: number, capGb = 7.5): SnapshotSettingsResponse {
  return {
    retention_n: 50,
    schedule_enabled: true,
    schedule_interval_minutes: 60,
    quota_bytes: null,
    effective_quota_bytes: capGb * GB,
    used_bytes: usedGb * GB,
  }
}

function snapshot(id: string, label: string, bytes: number): SnapshotResponse {
  return {
    id,
    trigger: 'scheduled',
    label,
    item_count: 1,
    total_bytes: bytes,
    pinned: false,
    created_at: '2026-07-01T00:00:00Z',
  }
}

describe('SnapshotUsagePanel', () => {
  it('shows what snapshots cost against their own cap', () => {
    render(<SnapshotUsagePanel settings={settings(4.3)} snapshots={[]} />)

    expect(screen.getByText(/4\.3 GB/)).toBeInTheDocument()
    expect(screen.getByText(/of 7\.5 GB/)).toBeInTheDocument()
    // The cap is separate from the file quota — saying so is the whole point,
    // since a 34 MB drive can carry gigabytes of history.
    expect(screen.getByText(/Separate from your file storage/)).toBeInTheDocument()
  })

  it('stays quiet below the warning threshold', () => {
    render(<SnapshotUsagePanel settings={settings(4.3)} snapshots={[]} />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('warns before old snapshots start disappearing', () => {
    // 6.2 / 7.5 GB = 83%, past the 80% threshold.
    render(<SnapshotUsagePanel settings={settings(6.2)} snapshots={[]} />)

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent(/oldest snapshots are deleted automatically/)
  })

  it('lists the heaviest snapshots first', () => {
    render(
      <SnapshotUsagePanel
        settings={settings(1)}
        snapshots={[
          snapshot('s1', 'Small one', 1024),
          snapshot('s2', 'Huge one', 900 * 1024 * 1024),
          snapshot('s3', 'Middling', 5 * 1024 * 1024),
        ]}
      />,
    )

    const rows = screen.getAllByRole('listitem').map((li) => li.textContent)
    // Dated, because every scheduled snapshot is labelled "Scheduled" —
    // five identical rows would be useless for deciding what to delete.
    expect(rows[0]).toMatch(/Jul \d+.*Huge one/)
    expect(rows[0]).toContain('Huge one')
    expect(rows[1]).toContain('Middling')
    expect(rows[2]).toContain('Small one')
  })

  it('explains why the per-snapshot sizes overshoot the total', () => {
    render(
      <SnapshotUsagePanel settings={settings(1)} snapshots={[snapshot('s1', 'One', 1024)]} />,
    )
    // Without this, the list looks like it contradicts the total.
    expect(screen.getByText(/snapshots share unchanged files/)).toBeInTheDocument()
  })

  it('renders nothing until settings arrive', () => {
    const { container } = render(<SnapshotUsagePanel settings={undefined} snapshots={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
