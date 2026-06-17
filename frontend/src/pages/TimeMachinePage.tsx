import { AlertTriangle, Camera, File, Folder, History, Loader2, Pin, RotateCcw } from 'lucide-react'
import { useState } from 'react'

import { isApiError } from '@/api/client'
import type { RestoreRequest, SnapshotResponse } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  useCreateSnapshot,
  useRestoreSnapshot,
  useSnapshotItems,
  useSnapshots,
} from '@/hooks/useSnapshots'

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(1)} GB`
}

const TRIGGER_LABEL: Record<string, string> = {
  scheduled: 'Scheduled',
  manual: 'Manual',
  assistant: 'Before assistant action',
  pre_restore: 'Before restore',
}

function SnapshotRow({
  snapshot,
  selected,
  onSelect,
}: {
  snapshot: SnapshotResponse
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-left transition-colors ${
        selected ? 'border-primary bg-accent' : 'border-border hover:bg-accent/50'
      }`}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-sm font-medium">
          {snapshot.pinned && <Pin className="size-3 text-amber-600" aria-hidden="true" />}
          {new Date(snapshot.created_at).toLocaleString()}
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          {TRIGGER_LABEL[snapshot.trigger] ?? snapshot.trigger} · {snapshot.item_count} items ·{' '}
          {formatBytes(snapshot.total_bytes)}
        </div>
      </div>
    </button>
  )
}

export function TimeMachinePage() {
  const { data: snapshots, isLoading } = useSnapshots()
  const createSnapshot = useCreateSnapshot()
  const restore = useRestoreSnapshot()

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [mode, setMode] = useState<'keep_new' | 'exact_mirror'>('keep_new')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<string | null>(null)

  const { data: items, isLoading: itemsLoading } = useSnapshotItems(selectedId)

  const handleRestore = async () => {
    if (!selectedId) return
    setError(null)
    const body: RestoreRequest = { scope: 'whole', subtree_mode: mode }
    try {
      const res = await restore.mutateAsync({ snapshotId: selectedId, body })
      setConfirming(false)
      setResult(`Restored ${res.restored} item(s)` + (res.trashed ? `, trashed ${res.trashed}` : ''))
    } catch (err) {
      setError(isApiError(err) ? err.message : 'Restore failed.')
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-1 py-4 sm:px-4 sm:py-8">
      <header className="mb-6 flex items-start justify-between gap-3">
        <div>
          <div className="mb-3 flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <History className="size-6" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Time Machine</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Browse past snapshots of your drive and restore to any point in time.
          </p>
        </div>
        <Button
          type="button"
          onClick={() => void createSnapshot.mutateAsync(undefined)}
          disabled={createSnapshot.isPending}
        >
          {createSnapshot.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Camera className="size-4" aria-hidden="true" />
          )}
          Create snapshot
        </Button>
      </header>

      {result && (
        <p role="status" className="mb-4 rounded-md bg-emerald-600/10 px-3 py-2 text-sm text-emerald-700">
          {result}
        </p>
      )}

      <div className="grid gap-6 md:grid-cols-[20rem_1fr]">
        {/* Timeline */}
        <section aria-label="Snapshot timeline" className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground">Timeline</h2>
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {!isLoading && (snapshots?.length ?? 0) === 0 && (
            <p className="text-sm text-muted-foreground">
              No snapshots yet. Create one to start.
            </p>
          )}
          {snapshots?.map((s) => (
            <SnapshotRow
              key={s.id}
              snapshot={s}
              selected={s.id === selectedId}
              onSelect={() => {
                setSelectedId(s.id)
                setResult(null)
              }}
            />
          ))}
        </section>

        {/* Browser + restore */}
        <section aria-label="Snapshot contents" className="min-w-0">
          {selectedId === null ? (
            <div className="flex h-48 items-center justify-center rounded-xl border border-dashed text-sm text-muted-foreground">
              Select a snapshot to browse its contents
            </div>
          ) : (
            <>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-medium text-muted-foreground">Snapshot contents (read-only)</h2>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    setError(null)
                    setConfirming(true)
                  }}
                >
                  <RotateCcw className="size-3.5" aria-hidden="true" />
                  Restore whole snapshot
                </Button>
              </div>
              {itemsLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
              <ul className="divide-y rounded-lg border">
                {items?.map((e) => (
                  <li key={e.item_id} className="flex items-center gap-2 px-3 py-2 text-sm">
                    {e.item_type === 'FOLDER' ? (
                      <Folder className="size-4 text-primary" aria-hidden="true" />
                    ) : (
                      <File className="size-4 text-muted-foreground" aria-hidden="true" />
                    )}
                    <span className="truncate">{e.name}</span>
                    {e.item_type === 'FILE' && (
                      <span className="ml-auto text-xs text-muted-foreground">
                        {formatBytes(e.size_bytes)}
                      </span>
                    )}
                  </li>
                ))}
                {!itemsLoading && (items?.length ?? 0) === 0 && (
                  <li className="px-3 py-2 text-sm text-muted-foreground">(empty at root)</li>
                )}
              </ul>
            </>
          )}
        </section>
      </div>

      {confirming && selectedId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setConfirming(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="restore-title"
            className="w-full max-w-md rounded-lg border bg-popover p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-start gap-3">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-destructive/10">
                <AlertTriangle className="size-5 text-destructive" aria-hidden="true" />
              </div>
              <div>
                <h2 id="restore-title" className="text-sm font-semibold">
                  Restore whole snapshot?
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  This overwrites your current drive. A safety snapshot is taken first, so you can
                  undo it.
                </p>
              </div>
            </div>

            <fieldset className="mb-4 space-y-2 text-sm">
              <label className="flex items-start gap-2">
                <input
                  type="radio"
                  name="mode"
                  checked={mode === 'keep_new'}
                  onChange={() => setMode('keep_new')}
                  className="mt-1"
                />
                <span>
                  <span className="font-medium">Keep new files</span> — items added since the
                  snapshot are left untouched.
                </span>
              </label>
              <label className="flex items-start gap-2">
                <input
                  type="radio"
                  name="mode"
                  checked={mode === 'exact_mirror'}
                  onChange={() => setMode('exact_mirror')}
                  className="mt-1"
                />
                <span>
                  <span className="font-medium">Exact mirror</span> — items added since the
                  snapshot are moved to trash.
                </span>
              </label>
            </fieldset>

            {error && (
              <p role="alert" className="mb-3 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
                {error}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() => void handleRestore()}
                disabled={restore.isPending}
              >
                {restore.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <RotateCcw className="size-3.5" aria-hidden="true" />
                )}
                Restore
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
