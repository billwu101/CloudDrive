import type { QuotaResponse } from '@/api/types'

interface StorageUsageBarProps {
  quota: QuotaResponse | undefined
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

export function StorageUsageBar({ quota }: StorageUsageBarProps) {
  if (!quota) return null

  const percent = Math.min(quota.used_percent, 100)
  const isNearFull = percent >= 90

  return (
    <div className="px-3 py-2">
      <div className="mb-1 flex justify-between text-xs text-muted-foreground">
        <span>Storage</span>
        <span>
          {formatBytes(quota.used_bytes)} / {formatBytes(quota.quota_bytes)}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all ${
            isNearFull ? 'bg-destructive' : 'bg-primary'
          }`}
          style={{ width: `${percent}%` }}
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${percent.toFixed(0)}% storage used`}
        />
      </div>
    </div>
  )
}
