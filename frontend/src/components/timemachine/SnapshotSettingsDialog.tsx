import { Loader2, Settings } from 'lucide-react'
import { useState } from 'react'

import { isApiError } from '@/api/client'
import type { SnapshotSettingsResponse } from '@/api/types'
import { Button } from '@/components/ui/button'
import { useSnapshotSettings, useUpdateSnapshotSettings } from '@/hooks/useSnapshots'

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(1)} GB`
}

const MB = 1024 * 1024

function SettingsForm({
  settings,
  onClose,
}: {
  settings: SnapshotSettingsResponse
  onClose: () => void
}) {
  const update = useUpdateSnapshotSettings()
  const [scheduleEnabled, setScheduleEnabled] = useState(settings.schedule_enabled)
  const [intervalMinutes, setIntervalMinutes] = useState(settings.schedule_interval_minutes)
  const [retentionN, setRetentionN] = useState(settings.retention_n)
  const [autoQuota, setAutoQuota] = useState(settings.quota_bytes === null)
  const [quotaMb, setQuotaMb] = useState(
    Math.round((settings.quota_bytes ?? settings.effective_quota_bytes) / MB),
  )
  const [error, setError] = useState<string | null>(null)

  const handleSave = async () => {
    setError(null)
    try {
      await update.mutateAsync({
        retention_n: retentionN,
        schedule_enabled: scheduleEnabled,
        schedule_interval_minutes: intervalMinutes,
        quota_bytes: autoQuota ? null : Math.max(0, Math.round(quotaMb * MB)),
      })
      onClose()
    } catch (err) {
      setError(isApiError(err) ? err.message : 'Could not save settings.')
    }
  }

  return (
    <>
      <div className="space-y-4 text-sm">
        <label className="flex items-center justify-between gap-3">
          <span className="font-medium">Automatic snapshots</span>
          <input
            type="checkbox"
            checked={scheduleEnabled}
            onChange={(e) => setScheduleEnabled(e.target.checked)}
          />
        </label>

        <label className="flex items-center justify-between gap-3">
          <span>
            Every
            <span className="ml-1 text-muted-foreground">(minutes)</span>
          </span>
          <input
            type="number"
            min={1}
            value={intervalMinutes}
            disabled={!scheduleEnabled}
            onChange={(e) => setIntervalMinutes(Number(e.target.value))}
            className="w-24 rounded-md border bg-background px-2 py-1 text-right disabled:opacity-50"
          />
        </label>

        <label className="flex items-center justify-between gap-3">
          <span>Keep most recent</span>
          <input
            type="number"
            min={1}
            value={retentionN}
            onChange={(e) => setRetentionN(Number(e.target.value))}
            className="w-24 rounded-md border bg-background px-2 py-1 text-right"
          />
        </label>

        <div className="space-y-2 border-t pt-3">
          <label className="flex items-center justify-between gap-3">
            <span className="font-medium">Snapshot storage limit</span>
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              Auto
              <input
                type="checkbox"
                checked={autoQuota}
                onChange={(e) => setAutoQuota(e.target.checked)}
              />
            </span>
          </label>
          {!autoQuota && (
            <label className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Limit (MB)</span>
              <input
                type="number"
                min={0}
                value={quotaMb}
                onChange={(e) => setQuotaMb(Number(e.target.value))}
                className="w-24 rounded-md border bg-background px-2 py-1 text-right"
              />
            </label>
          )}
          <p className="text-xs text-muted-foreground">
            Using {formatBytes(settings.used_bytes)} of{' '}
            {formatBytes(settings.effective_quota_bytes)}
            {autoQuota && ' (auto: half of your file quota)'}
          </p>
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive"
          >
            {error}
          </p>
        )}
      </div>

      <div className="mt-5 flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={() => void handleSave()}
          disabled={update.isPending}
        >
          {update.isPending && <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />}
          Save
        </Button>
      </div>
    </>
  )
}

export function SnapshotSettingsDialog({ onClose }: { onClose: () => void }) {
  const { data: settings, isLoading } = useSnapshotSettings()

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tm-settings-title"
        className="w-full max-w-md rounded-lg border bg-popover p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center gap-2">
          <Settings className="size-5 text-primary" aria-hidden="true" />
          <h2 id="tm-settings-title" className="text-sm font-semibold">
            Time Machine settings
          </h2>
        </div>

        {isLoading || !settings ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <SettingsForm settings={settings} onClose={onClose} />
        )}
      </div>
    </div>
  )
}
