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

function snapshot(
  id: string,
  label: string,
  bytes: number,
  reclaimable = 0,
): SnapshotResponse {
  return {
    id,
    trigger: 'scheduled',
    label,
    item_count: 1,
    total_bytes: bytes,
    reclaimable_bytes: reclaimable,
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

  it('ranks by space reclaimed, not by size covered', () => {
    // The 3 GB snapshot that shares everything must not outrank the small one
    // that is the sole holder of its blobs — sorting by coverage would send
    // the user to delete the wrong snapshot and reclaim nothing.
    render(
      <SnapshotUsagePanel
        settings={settings(1)}
        snapshots={[
          snapshot('big', 'Covers everything', 3 * GB, 0),
          snapshot('small', 'Sole holder', 10 * 1024 * 1024, 8 * 1024 * 1024),
          snapshot('mid', 'Partly shared', 2 * GB, 500 * 1024 * 1024),
        ]}
      />,
    )

    const rows = screen.getAllByRole('listitem').map((li) => li.textContent)
    expect(rows[0]).toContain('Partly shared')
    expect(rows[0]).toContain('frees 500 MB')
    expect(rows[1]).toContain('Sole holder')
    // Both numbers on every row: coverage alone reads as cost, and
    // "frees nothing" alone reads as "this snapshot is empty".
    expect(rows[0]).toContain('covers 2.0 GB')
  })

  it('keeps the zero-reclaim snapshots visible for comparison', () => {
    // One number alone says nothing; "2.6 GB" next to several "nothing"s is
    // what lets the user see which snapshot is actually worth deleting.
    render(
      <SnapshotUsagePanel
        settings={settings(3.5)}
        snapshots={[
          snapshot('a', 'Scheduled', 1358 * 1024 * 1024, 0),
          snapshot('b', 'Scheduled', 1358 * 1024 * 1024, 0),
          snapshot('c', 'Scheduled', 3063 * 1024 * 1024, 2.6 * GB),
        ]}
      />,
    )

    const rows = screen.getAllByRole('listitem').map((li) => li.textContent)
    expect(rows).toHaveLength(3)
    expect(rows[0]).toContain('frees 2.6 GB')
    // The zero rows still show what they hold — that is the answer to
    // "surely it takes up space?".
    expect(rows[1]).toContain('covers 1.3 GB')
    expect(rows[1]).toContain('frees nothing')
    expect(rows[2]).toContain('frees nothing')
  })

  it('shows at most five', () => {
    render(
      <SnapshotUsagePanel
        settings={settings(1)}
        snapshots={Array.from({ length: 9 }, (_, i) =>
          snapshot(`s${i}`, 'Scheduled', 1024, (9 - i) * 1024),
        )}
      />,
    )
    expect(screen.getAllByRole('listitem')).toHaveLength(5)
  })

  it('renders nothing until settings arrive', () => {
    const { container } = render(<SnapshotUsagePanel settings={undefined} snapshots={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
