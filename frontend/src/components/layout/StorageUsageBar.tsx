import type { QuotaResponse } from '@/api/types'
import { useSnapshotSettings } from '@/hooks/useSnapshots'

interface StorageUsageBarProps {
  quota: QuotaResponse | undefined
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function Meter({
  label,
  used,
  total,
  nearFullAt,
}: {
  label: string
  used: number
  total: number
  nearFullAt: number
}) {
  const percent = total > 0 ? Math.min((used / total) * 100, 100) : 0
  const nearFull = percent >= nearFullAt

  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span>
          {formatBytes(used)} / {formatBytes(total)}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all ${nearFull ? 'bg-destructive' : 'bg-primary'}`}
          style={{ width: `${percent}%` }}
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${percent.toFixed(0)}% ${label.toLowerCase()} used`}
        />
      </div>
    </div>
  )
}

export function StorageUsageBar({ quota }: StorageUsageBarProps) {
  const { data: snapshotSettings } = useSnapshotSettings()

  if (!quota) return null

  return (
    <div className="space-y-2 px-3 py-2">
      <Meter label="Storage" used={quota.used_bytes} total={quota.quota_bytes} nearFullAt={90} />
      {/* A second meter rather than a segment of the first: snapshots have
          their own cap (half the file quota by default), so painting them into
          the same bar would make a nearly-empty drive look nearly full. */}
      {snapshotSettings && snapshotSettings.effective_quota_bytes > 0 && (
        <Meter
          label="Snapshots"
          used={snapshotSettings.used_bytes}
          total={snapshotSettings.effective_quota_bytes}
          nearFullAt={80}
        />
      )}
    </div>
  )
}
