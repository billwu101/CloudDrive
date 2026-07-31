import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, FolderOpen, Loader2 } from 'lucide-react'
import { useCallback, useMemo, useRef, useState } from 'react'

import { isApiError } from '@/api/client'
import {
  createSharedFolder,
  downloadSharedItem,
  downloadSharedSelection,
  moveSharedItem,
  renameSharedItem,
  trashSharedItem,
} from '@/api/publicShareApi'
import type { PublicItem } from '@/api/types'
import { ConfirmTrashDialog } from '@/components/drive/ConfirmTrashDialog'
import { CreateFolderDialog } from '@/components/drive/CreateFolderDialog'
import { DriveToolbar } from '@/components/drive/DriveToolbar'
import { FileGrid } from '@/components/drive/FileGrid'
import { FileTable } from '@/components/drive/FileTable'
import { MoveDialog } from '@/components/drive/MoveDialog'
import { MultiFileContextMenu } from '@/components/drive/MultiFileContextMenu'
import { RenameDialog } from '@/components/drive/RenameDialog'
import { PreviewDialog } from '@/components/preview/PreviewDialog'
import { UploadDropzone } from '@/components/upload/UploadDropzone'
import { UploadMenu } from '@/components/upload/UploadMenu'
import { UploadQueue } from '@/components/upload/UploadQueue'
import { useDragMove } from '@/hooks/useDragMove'
import { useDragSelect } from '@/hooks/useDragSelect'
import {
  publicKeys,
  useGuestChildren,
  useGuestFolderSource,
  useGuestPreviewSource,
  useGuestUploadFiles,
  useGuestUploadFolders,
} from '@/hooks/usePublicDrive'
import { useUIStore } from '@/stores/uiStore'

import { PublicContextMenu } from './PublicContextMenu'

/**
 * The guest file browser (proposal §34).
 *
 * Deliberately built from My Drive's own components rather than a simpler
 * bespoke list: someone handed an editor link is doing the same work as a
 * signed-in user, and should not have to learn a second set of gestures.
 *
 * What is *not* here is as deliberate — no star, no re-sharing, no share
 * badges, no assistant skills (proposal §34.3). Each needs either an account
 * or the owner's private state, and a guest has neither.
 */

interface PublicFolderBrowserProps {
  /** Folder currently being shown — the share root, or one of its descendants. */
  folder: PublicItem
  /** Path from the share root down to `folder`, root first. */
  trail: PublicItem[]
  canDownload: boolean
  canEdit: boolean
  onOpenFolder: (item: PublicItem) => void
  onNavigateTo: (depth: number) => void
}

type ContextMenuState =
  | { kind: 'single'; item: PublicItem; x: number; y: number }
  | { kind: 'multi'; x: number; y: number }
  | null

export function PublicFolderBrowser({
  folder,
  trail,
  canDownload,
  canEdit,
  onOpenFolder,
  onNavigateTo,
}: PublicFolderBrowserProps) {
  const qc = useQueryClient()
  const { data, isLoading, isError } = useGuestChildren(folder.id)
  const items = useMemo(() => data?.items ?? [], [data?.items])

  // View mode is a display preference and can be shared with My Drive.
  // Selection cannot: it is a single global set, so a guest tab and a My Drive
  // tab open at once would each act on the other's picks (design §5.9.6).
  const viewMode = useUIStore((s) => s.viewMode)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const [showCreateFolder, setShowCreateFolder] = useState(false)
  const [renameTarget, setRenameTarget] = useState<PublicItem | null>(null)
  const [moveTarget, setMoveTarget] = useState<PublicItem | null>(null)
  const [trashTargets, setTrashTargets] = useState<PublicItem[]>([])
  const [previewItemId, setPreviewItemId] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const fileListRef = useRef<HTMLDivElement>(null)

  const shareRoot = trail[0] ?? folder
  const previewSource = useGuestPreviewSource(items)
  const folderSource = useGuestFolderSource(shareRoot.id, shareRoot.name)
  const { upload } = useGuestUploadFiles(folder.id)
  const { uploadFolders } = useGuestUploadFolders(folder.id)

  const invalidate = useCallback(
    () => qc.invalidateQueries({ queryKey: publicKeys.allChildren }),
    [qc],
  )
  const fail = useCallback(
    (err: unknown) => setActionError(isApiError(err) ? err.message : 'Something went wrong.'),
    [],
  )

  const createFolder = useMutation({
    mutationFn: (name: string) => createSharedFolder(folder.id, name),
    onSuccess: () => {
      setShowCreateFolder(false)
      setActionError(null)
      void invalidate()
    },
    onError: fail,
  })

  const rename = useMutation({
    mutationFn: (input: { id: string; name: string }) => renameSharedItem(input.id, input.name),
    onSuccess: () => {
      setRenameTarget(null)
      setActionError(null)
      void invalidate()
    },
    onError: fail,
  })

  const move = useMutation({
    mutationFn: (input: { id: string; parentId: string }) =>
      moveSharedItem(input.id, input.parentId),
    onSuccess: () => {
      setMoveTarget(null)
      setActionError(null)
      void invalidate()
    },
    onError: fail,
  })

  const trash = useMutation({ mutationFn: (id: string) => trashSharedItem(id) })

  // Only ever act on what is actually listed, so a stale id from a folder the
  // guest has since left can never be trashed or downloaded.
  const visibleSelected = useMemo(
    () => items.filter((i) => selectedIds.has(i.id)),
    [items, selectedIds],
  )

  const selectItem = useCallback((id: string, multi = false) => {
    setSelectedIds((prev) => {
      if (!multi) return new Set([id])
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])
  const clearSelection = useCallback(() => setSelectedIds(new Set()), [])
  const selectAll = useCallback((ids: string[]) => setSelectedIds(new Set(ids)), [])

  const handleSelectAll = useCallback(() => {
    if (items.length > 0 && items.every((i) => selectedIds.has(i.id))) clearSelection()
    else selectAll(items.map((i) => i.id))
  }, [items, selectedIds, selectAll, clearSelection])

  const drag = useDragMove({
    selectedIds,
    items,
    moveItem: (id, parentId) => moveSharedItem(id, parentId).then(invalidate),
  })
  useDragSelect(fileListRef, selectAll, clearSelection)

  const handleContextMenu = useCallback(
    (item: PublicItem, e: React.MouseEvent) => {
      e.preventDefault()
      if (selectedIds.size > 1 && selectedIds.has(item.id)) {
        setContextMenu({ kind: 'multi', x: e.clientX, y: e.clientY })
      } else {
        if (!selectedIds.has(item.id)) selectItem(item.id)
        setContextMenu({ kind: 'single', item, x: e.clientX, y: e.clientY })
      }
    },
    [selectedIds, selectItem],
  )

  const handleDownloadSelected = useCallback(async () => {
    const ids = visibleSelected.map((i) => i.id)
    if (ids.length === 0) return
    try {
      await downloadSharedSelection(ids)
    } catch (err) {
      fail(err)
    }
  }, [visibleSelected, fail])

  const listProps = {
    items,
    selectedIds,
    onItemClick: (item: PublicItem, e: React.MouseEvent) => {
      e.stopPropagation()
      selectItem(item.id, e.metaKey || e.ctrlKey)
    },
    onItemDoubleClick: (item: PublicItem) =>
      item.item_type === 'FOLDER' ? onOpenFolder(item) : setPreviewItemId(item.id),
    onItemContextMenu: handleContextMenu,
    onCheckboxClick: (item: PublicItem, e: React.MouseEvent) => {
      e.stopPropagation()
      selectItem(item.id, true)
    },
    drag,
    // onStarClick deliberately absent — see the note at the top of this file.
  }

  const body = (
    <div className="flex h-full flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* At the share root the only crumb equals the page title, so the whole
            bar is dropped rather than printing the same name twice. */}
        {trail.length > 1 ? (
          <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1 text-sm">
            {trail.map((crumb, i) => (
              <span key={crumb.id} className="flex items-center gap-1">
                {i > 0 && (
                  <ChevronRight className="size-3 text-muted-foreground" aria-hidden="true" />
                )}
                <button
                  type="button"
                  onClick={() => onNavigateTo(i)}
                  disabled={i === trail.length - 1}
                  className="rounded px-1 hover:bg-accent disabled:font-medium disabled:hover:bg-transparent"
                  {...(i < trail.length - 1 && canEdit
                    ? {
                        onDragOver: (e: React.DragEvent) => drag.onItemDragOver(crumb, e),
                        onDragLeave: () => drag.onItemDragLeave(crumb),
                        onDrop: (e: React.DragEvent) => drag.onItemDrop(crumb, e),
                      }
                    : {})}
                >
                  {crumb.name}
                </button>
              </span>
            ))}
          </nav>
        ) : (
          <span />
        )}

        {canEdit && (
          <div className="flex items-center gap-2">
            <UploadMenu onFiles={upload} onFolders={uploadFolders} />
            <DriveToolbar
              selectedCount={visibleSelected.length}
              onNewFolder={() => setShowCreateFolder(true)}
              onDownloadSelected={handleDownloadSelected}
              onTrashSelected={() => setTrashTargets(visibleSelected)}
            />
          </div>
        )}
        {!canEdit && canDownload && visibleSelected.length > 0 && (
          <button
            onClick={handleDownloadSelected}
            className="rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent"
          >
            Download ({visibleSelected.length})
          </button>
        )}
      </div>

      {actionError && (
        <p role="alert" className="text-sm text-destructive">
          {actionError}
        </p>
      )}

      {drag.moveError && (
        <div
          role="alert"
          className="flex items-start justify-between gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          <span>Could not move: {drag.moveError}</span>
          <button type="button" aria-label="Dismiss" onClick={drag.clearMoveError}>
            ×
          </button>
        </div>
      )}

      {isLoading && (
        <div className="flex justify-center py-10">
          <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Loading" />
        </div>
      )}

      {isError && (
        <p className="py-10 text-center text-sm text-destructive">Could not load this folder.</p>
      )}

      {!isLoading && !isError && items.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <FolderOpen className="size-12" aria-hidden="true" />
          <p className="text-sm">This folder is empty</p>
        </div>
      )}

      {items.length > 0 && (
        <div ref={fileListRef} data-testid="file-list" className="relative flex-1 overflow-auto">
          {viewMode === 'list' ? (
            <FileTable {...listProps} onSelectAll={handleSelectAll} />
          ) : (
            <FileGrid {...listProps} />
          )}
        </div>
      )}

      {contextMenu?.kind === 'single' && (
        <PublicContextMenu
          item={contextMenu.item}
          position={{ x: contextMenu.x, y: contextMenu.y }}
          canEdit={canEdit}
          canDownload={canDownload}
          onClose={() => setContextMenu(null)}
          onPreview={(item) => setPreviewItemId(item.id)}
          onRename={setRenameTarget}
          onMove={setMoveTarget}
          onCopyName={(item) => void navigator.clipboard?.writeText(item.name)}
          onTrash={(item) => setTrashTargets([item])}
          onDownload={(item) => void downloadSharedItem(item.id, item.name)}
        />
      )}

      {contextMenu?.kind === 'multi' && (
        <MultiFileContextMenu
          count={selectedIds.size}
          position={{ x: contextMenu.x, y: contextMenu.y }}
          onClose={() => setContextMenu(null)}
          onTrash={() => setTrashTargets(visibleSelected)}
        />
      )}

      <CreateFolderDialog
        open={showCreateFolder}
        loading={createFolder.isPending}
        onConfirm={(name) => createFolder.mutate(name)}
        onClose={() => setShowCreateFolder(false)}
      />

      <RenameDialog
        open={!!renameTarget}
        initialName={renameTarget?.name ?? ''}
        loading={rename.isPending}
        onConfirm={(name) => renameTarget && rename.mutate({ id: renameTarget.id, name })}
        onClose={() => setRenameTarget(null)}
      />

      <MoveDialog
        open={!!moveTarget}
        itemId={moveTarget?.id ?? ''}
        loading={move.isPending}
        source={folderSource}
        onConfirm={(parentId) =>
          moveTarget && parentId && move.mutate({ id: moveTarget.id, parentId })
        }
        onClose={() => setMoveTarget(null)}
      />

      <ConfirmTrashDialog
        open={trashTargets.length > 0}
        itemNames={trashTargets.map((i) => i.name)}
        loading={trash.isPending}
        onConfirm={async () => {
          const failures: string[] = []
          for (const item of trashTargets) {
            try {
              await trash.mutateAsync(item.id)
            } catch (err) {
              failures.push(`${item.name} — ${isApiError(err) ? err.message : 'failed'}`)
            }
          }
          setTrashTargets([])
          clearSelection()
          setActionError(failures.length > 0 ? failures.join('; ') : null)
          void invalidate()
        }}
        onClose={() => setTrashTargets([])}
      />

      <UploadQueue onRetry={(task) => task.file && void upload([task.file])} />

      <PreviewDialog
        itemId={previewItemId}
        source={previewSource}
        onClose={() => setPreviewItemId(null)}
      />
    </div>
  )

  // Dropping desktop files only makes sense when the guest may write. The
  // custom drag MIME keeps this from firing on an internal item drag.
  return canEdit ? (
    <UploadDropzone onFiles={upload} onFolders={uploadFolders}>
      {body}
    </UploadDropzone>
  ) : (
    body
  )
}
