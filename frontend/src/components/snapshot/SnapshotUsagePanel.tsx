import { AlertTriangle } from 'lucide-react'

import type { SnapshotResponse, SnapshotSettingsResponse } from '@/api/types'
import { formatBytes } from '@/lib/uploadLimits'

/** Above this share of the cap, the oldest snapshots start getting dropped soon. */
export const SNAPSHOT_WARN_AT = 0.8

/** How many snapshots to name. */
const TOP_N = 5

/** Scheduled snapshots all share the label "Scheduled", so the timestamp is
 *  the only thing that tells them apart — and this list exists to be acted on. */
function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface SnapshotUsagePanelProps {
  settings: SnapshotSettingsResponse | undefined
  snapshots: SnapshotResponse[] | undefined
}

/**
 * What the snapshots actually cost (proposal §12).
 *
 * Snapshots pin every version they captured, so a drive holding 34 MB of live
 * files can sit on gigabytes of history — and until now nothing in the UI said
 * so. When the cap is reached the oldest snapshots are deleted automatically,
 * which is a bad thing to discover after the fact.
 */
export function SnapshotUsagePanel({ settings, snapshots }: SnapshotUsagePanelProps) {
  if (!settings) return null

  const { used_bytes: used, effective_quota_bytes: cap } = settings
  const ratio = cap > 0 ? used / cap : 0
  const percent = Math.min(ratio * 100, 100)
  const nearFull = ratio >= SNAPSHOT_WARN_AT

  // Ranked by what deleting them would free, not by what they cover.
  // Snapshots share blobs, so the "biggest" snapshot is usually the one that
  // reclaims nothing — sorting by coverage sends the user to delete the wrong
  // thing (and then to wonder why no space came back).
  //
  // The zero rows stay in the list: seeing "2.6 GB" next to four "nothing"s is
  // what makes the trade-off legible. Hiding them just leaves one number with
  // nothing to compare against.
  const ranked = [...(snapshots ?? [])]
    .sort((a, b) => b.reclaimable_bytes - a.reclaimable_bytes)
    .slice(0, TOP_N)

  return (
    <section
      aria-label="Snapshot storage"
      className="mb-6 rounded-lg border p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-medium">Snapshot storage</h2>
        <p className="text-sm text-muted-foreground">
          <span className={nearFull ? 'font-medium text-destructive' : 'font-medium text-foreground'}>
            {formatBytes(used)}
          </span>{' '}
          of {formatBytes(cap)}
        </p>
      </div>

      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          role="progressbar"
          aria-valuenow={Math.round(percent)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${percent.toFixed(0)}% of the snapshot cap used`}
          className={`h-full rounded-full transition-all ${nearFull ? 'bg-destructive' : 'bg-primary'}`}
          style={{ width: `${percent}%` }}
        />
      </div>

      <p className="mt-2 text-xs text-muted-foreground">
        Separate from your file storage. Snapshots keep earlier versions of files, so this
        can be far larger than the drive itself.
      </p>

      {nearFull && (
        <p
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>
            Once this is full, your oldest snapshots are deleted automatically to make room.
            Delete snapshots you no longer need, or raise the cap in Settings.
          </span>
        </p>
      )}

      {ranked.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-1.5 text-xs font-medium text-muted-foreground">
            Space you would reclaim
          </h3>
          <ul className="space-y-1">
            {ranked.map((snap) => {
              const frees = snap.reclaimable_bytes > 0
              return (
                <li key={snap.id} className="flex items-center justify-between gap-3 text-xs">
                  <span className="min-w-0 flex-1 truncate text-muted-foreground">
                    {when(snap.created_at)} · {snap.label}
                  </span>
                  <span
                    className={`shrink-0 tabular-nums ${frees ? 'font-medium text-foreground' : 'text-muted-foreground'}`}
                  >
                    {frees ? `frees ${formatBytes(snap.reclaimable_bytes)}` : 'frees nothing'}
                  </span>
                </li>
              )
            })}
          </ul>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Space actually reclaimed, not the size of the drive each snapshot covers. A
            snapshot frees nothing while another one still holds the same files.
          </p>
        </div>
      )}
    </section>
  )
}
