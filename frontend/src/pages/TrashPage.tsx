import { Trash2 } from 'lucide-react'
import { useState } from 'react'

import type { DriveItemResponse } from '@/api/types'
import { FileIcon } from '@/components/drive/FileIcon'
import { EmptyTrashConfirmDialog } from '@/components/trash/EmptyTrashConfirmDialog'
import { PermanentDeleteConfirmDialog } from '@/components/trash/PermanentDeleteConfirmDialog'
import { RestoreConfirmDialog } from '@/components/trash/RestoreConfirmDialog'
import { TrashToolbar } from '@/components/trash/TrashToolbar'
import { useEmptyTrash, usePermanentDelete, useRestoreItem, useTrashItems } from '@/hooks/useTrash'
import { useUIStore } from '@/stores/uiStore'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function TrashPage() {
  const selectedIds = useUIStore((s) => s.selectedItemIds)
  const selectItem = useUIStore((s) => s.selectItem)
  const clearSelection = useUIStore((s) => s.clearSelection)

  const { data, isLoading, isError } = useTrashItems()
  const restore = useRestoreItem()
  const permanentDelete = usePermanentDelete()
  const emptyTrash = useEmptyTrash()

  const [restoreTargets, setRestoreTargets] = useState<DriveItemResponse[]>([])
  const [deleteTargets, setDeleteTargets] = useState<DriveItemResponse[]>([])
  const [showEmptyConfirm, setShowEmptyConfirm] = useState(false)

  const items = data?.items ?? []
  const selectedItems = items.filter((i) => selectedIds.has(i.id))

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Trash</h1>
        <TrashToolbar
          selectedCount={selectedIds.size}
          totalItems={items.length}
          onRestoreSelected={() => setRestoreTargets(selectedItems)}
          onDeleteSelected={() => setDeleteTargets(selectedItems)}
          onEmptyTrash={() => setShowEmptyConfirm(true)}
        />
      </div>

      {isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">Loading…</div>
      )}

      {isError && (
        <div className="flex flex-1 items-center justify-center text-sm text-destructive">Failed to load trash.</div>
      )}

      {!isLoading && !isError && items.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Trash2 className="size-12" aria-hidden="true" />
          <p className="text-sm">Trash is empty</p>
        </div>
      )}

      {!isLoading && !isError && items.length > 0 && (
        <div onClick={() => clearSelection()} className="flex-1 overflow-auto">
          <table className="w-full table-fixed border-collapse text-left">
            <thead>
              <tr className="border-b text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <th className="w-8 py-2 pl-3" />
                <th className="py-2 pr-3">Name</th>
                <th className="w-36 py-2 pr-3">Deleted</th>
                <th className="w-24 py-2 pr-3">Type</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  aria-selected={selectedIds.has(item.id)}
                  onClick={(e) => { e.stopPropagation(); selectItem(item.id, e.metaKey || e.ctrlKey) }}
                  className={`group cursor-pointer select-none border-b transition-colors last:border-b-0 hover:bg-accent/50 ${selectedIds.has(item.id) ? 'bg-accent' : ''}`}
                >
                  <td className="py-2 pl-3 pr-2 w-8">
                    <FileIcon mimeType={item.mime_type} isFolder={item.item_type === 'FOLDER'} />
                  </td>
                  <td className="py-2 pr-3 text-sm font-medium truncate">{item.name}</td>
                  <td className="py-2 pr-3 text-sm text-muted-foreground whitespace-nowrap">
                    {item.deleted_at ? formatDate(item.deleted_at) : '—'}
                  </td>
                  <td className="py-2 pr-3 text-sm text-muted-foreground">
                    {item.item_type === 'FOLDER' ? 'Folder' : (item.mime_type ?? 'File')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <RestoreConfirmDialog
        open={restoreTargets.length > 0}
        itemNames={restoreTargets.map((i) => i.name)}
        loading={restore.isPending}
        onConfirm={async () => {
          for (const item of restoreTargets) await restore.mutateAsync(item.id)
          setRestoreTargets([])
          clearSelection()
        }}
        onClose={() => setRestoreTargets([])}
      />

      <PermanentDeleteConfirmDialog
        open={deleteTargets.length > 0}
        itemNames={deleteTargets.map((i) => i.name)}
        loading={permanentDelete.isPending}
        onConfirm={async () => {
          for (const item of deleteTargets) await permanentDelete.mutateAsync(item.id)
          setDeleteTargets([])
          clearSelection()
        }}
        onClose={() => setDeleteTargets([])}
      />

      <EmptyTrashConfirmDialog
        open={showEmptyConfirm}
        loading={emptyTrash.isPending}
        onConfirm={async () => {
          await emptyTrash.mutateAsync()
          setShowEmptyConfirm(false)
          clearSelection()
        }}
        onClose={() => setShowEmptyConfirm(false)}
      />
    </div>
  )
}
