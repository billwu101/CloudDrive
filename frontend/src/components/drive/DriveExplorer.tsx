import { FolderOpen } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { isApiError } from '@/api/client'
import type { BrowsableItem } from '@/api/types'
import { ConfirmTrashDialog } from '@/components/drive/ConfirmTrashDialog'
import { CreateFolderDialog } from '@/components/drive/CreateFolderDialog'
import { DriveToolbar } from '@/components/drive/DriveToolbar'
import {
  FileContextMenu,
  type AssistantContextMenuAction,
} from '@/components/drive/FileContextMenu'
import { FileGrid } from '@/components/drive/FileGrid'
import { FileTable } from '@/components/drive/FileTable'
import { MoveDialog, type FolderSource } from '@/components/drive/MoveDialog'
import { MultiFileContextMenu } from '@/components/drive/MultiFileContextMenu'
import { RenameDialog } from '@/components/drive/RenameDialog'
import { PreviewDialog, type PreviewSource } from '@/components/preview/PreviewDialog'
import { UploadDropzone } from '@/components/upload/UploadDropzone'
import { UploadMenu } from '@/components/upload/UploadMenu'
import { UploadQueue } from '@/components/upload/UploadQueue'
import { useDragMove } from '@/hooks/useDragMove'
import { useDragSelect } from '@/hooks/useDragSelect'
import { useUIStore } from '@/stores/uiStore'

/**
 * The drive page's whole file area, shared verbatim between My Drive and the
 * public share guest page (proposal §34, user decision 2026-07-31: the guest
 * gets the *same* frontend with capabilities removed, not a look-alike).
 *
 * Every action is optional, and an absent action hides its affordance —
 * toolbar button, menu entry, drag handle, dropzone. There is deliberately no
 * "guest mode" flag: what a caller cannot do is expressed by what it does not
 * wire, so a capability can never leak in through a forgotten flag check.
 */

export interface ExplorerSelection {
  selectedIds: Set<string>
  /** `multi` toggles without clearing (checkbox / ctrl-click semantics). */
  selectItem: (id: string, multi?: boolean) => void
  selectAll: (ids: string[]) => void
  clearSelection: () => void
}

export interface ExplorerActions<T extends BrowsableItem> {
  createFolder?: (name: string) => Promise<unknown>
  renameItem?: (id: string, name: string) => Promise<unknown>
  /** `null` means the browsing root of `folderSource`. */
  moveItem?: (id: string, targetParentId: string | null) => Promise<unknown>
  trashItem?: (id: string) => Promise<unknown>
  uploadFiles?: (files: File[]) => void
  uploadFolders?: (files: File[]) => void
  downloadItem?: (item: T) => void
  downloadSelection?: (items: T[]) => Promise<void>
  toggleStar?: (item: T) => void
  share?: (item: T) => void
}

interface DriveExplorerProps<T extends BrowsableItem> {
  items: T[]
  isLoading: boolean
  /**
   * Identifies the folder on screen. Changing it drops the selection, because
   * a selection belongs to one folder's listing: a double-click both selects
   * and navigates, so entering a folder would otherwise leave that folder
   * selected while you stand inside it — and the toolbar would offer to trash
   * something that isn't even on screen.
   */
  folderKey: string
  selection: ExplorerSelection
  /** Rendered on the left of the toolbar row — router breadcrumbs for My
   *  Drive, the trail nav for a guest. Navigation is the caller's business. */
  breadcrumb?: React.ReactNode
  onOpenFolder: (item: T) => void
  actions: ExplorerActions<T>
  folderSource?: FolderSource
  previewSource?: PreviewSource
  assistantActions?: (item: T) => AssistantContextMenuAction[]
  onAssistantAction?: (action: AssistantContextMenuAction, item: T) => void
}

type ContextMenuState<T> =
  | { kind: 'single'; item: T; x: number; y: number }
  | { kind: 'multi'; x: number; y: number }
  | null

export function DriveExplorer<T extends BrowsableItem>({
  items,
  isLoading,
  folderKey,
  selection,
  breadcrumb,
  onOpenFolder,
  actions,
  folderSource,
  previewSource,
  assistantActions,
  onAssistantAction,
}: DriveExplorerProps<T>) {
  const viewMode = useUIStore((s) => s.viewMode)
  const { selectedIds, selectItem, selectAll, clearSelection } = selection

  // See the note on `folderKey` — this is why both callers get it for free
  // instead of each remembering to wire its own effect.
  useEffect(() => {
    clearSelection()
  }, [folderKey, clearSelection])

  const fileListRef = useRef<HTMLDivElement>(null)
  const [showCreateFolder, setShowCreateFolder] = useState(false)
  const [renameTarget, setRenameTarget] = useState<T | null>(null)
  const [moveTarget, setMoveTarget] = useState<T | null>(null)
  const [trashTargets, setTrashTargets] = useState<T[]>([])
  const [previewItemId, setPreviewItemId] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState<T>>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const fail = useCallback(
    (err: unknown) => setActionError(isApiError(err) ? err.message : 'Something went wrong.'),
    [],
  )

  /** Run one dialog action; keep the dialog open on failure so the user can fix. */
  const run = useCallback(
    async (op: () => Promise<unknown>, close: () => void) => {
      setPending(true)
      try {
        await op()
        setActionError(null)
        close()
      } catch (err) {
        fail(err)
      } finally {
        setPending(false)
      }
    },
    [fail],
  )

  // Actions and counts derive from what is actually listed, so an id left over
  // from another folder's listing can never be acted on.
  const visibleSelected = useMemo(
    () => items.filter((i) => selectedIds.has(i.id)),
    [items, selectedIds],
  )

  const handleDoubleClick = useCallback(
    (item: T) => {
      if (item.item_type === 'FOLDER') onOpenFolder(item)
      else setPreviewItemId(item.id)
    },
    [onOpenFolder],
  )

  const handleContextMenu = useCallback(
    (item: T, e: React.MouseEvent) => {
      e.preventDefault()
      // The multi menu only offers trash, so without that capability a
      // multi-selection right-click falls through to the single menu.
      if (selectedIds.size > 1 && selectedIds.has(item.id) && actions.trashItem) {
        setContextMenu({ kind: 'multi', x: e.clientX, y: e.clientY })
      } else {
        if (!selectedIds.has(item.id)) selectItem(item.id)
        setContextMenu({ kind: 'single', item, x: e.clientX, y: e.clientY })
      }
    },
    [selectedIds, selectItem, actions.trashItem],
  )

  const handleSelectAll = useCallback(() => {
    if (items.length > 0 && items.every((i) => selectedIds.has(i.id))) clearSelection()
    else selectAll(items.map((i) => i.id))
  }, [items, selectedIds, selectAll, clearSelection])

  const handleDownloadSelected = useCallback(async () => {
    if (visibleSelected.length === 0 || !actions.downloadSelection) return
    try {
      await actions.downloadSelection(visibleSelected)
    } catch (err) {
      fail(err)
    }
  }, [visibleSelected, actions, fail])

  const drag = useDragMove({
    selectedIds,
    items,
    moveItem: actions.moveItem
      ? (id, targetParentId) => actions.moveItem!(id, targetParentId)
      : // Never reached: `drag` is only handed to the lists when moveItem exists.
        () => Promise.reject(new Error('moving is not available here')),
  })
  const handleDragSelect = useCallback((ids: string[]) => selectAll(ids), [selectAll])
  const { dragRect } = useDragSelect(fileListRef, handleDragSelect, clearSelection)

  const sharedProps = {
    items,
    selectedIds,
    onItemClick: (item: T, e: React.MouseEvent) => {
      e.stopPropagation()
      selectItem(item.id, e.metaKey || e.ctrlKey)
    },
    onItemDoubleClick: handleDoubleClick,
    onItemContextMenu: handleContextMenu,
    onStarClick: actions.toggleStar
      ? (item: T, e: React.MouseEvent) => {
          e.stopPropagation()
          actions.toggleStar!(item)
        }
      : undefined,
    onCheckboxClick: (item: T, e: React.MouseEvent) => {
      e.stopPropagation()
      selectItem(item.id, true)
    },
    drag: actions.moveItem ? drag : undefined,
  }

  const body = (
    <div className="flex h-full flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">{breadcrumb}</div>
        <div className="flex items-center gap-2">
          {actions.uploadFiles && (
            <UploadMenu
              onFiles={actions.uploadFiles}
              onFolders={actions.uploadFolders ?? actions.uploadFiles}
            />
          )}
          <DriveToolbar
            selectedCount={visibleSelected.length}
            onNewFolder={actions.createFolder ? () => setShowCreateFolder(true) : undefined}
            onDownloadSelected={actions.downloadSelection ? handleDownloadSelected : undefined}
            onTrashSelected={
              actions.trashItem ? () => setTrashTargets(visibleSelected) : undefined
            }
          />
        </div>
      </div>

      {actionError && (
        <div
          role="alert"
          className="flex items-start justify-between gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          <span>{actionError}</span>
          <button
            type="button"
            aria-label="Dismiss"
            onClick={() => setActionError(null)}
            className="shrink-0 rounded px-1 hover:bg-destructive/10"
          >
            ×
          </button>
        </div>
      )}

      {drag.moveError && (
        <div
          role="alert"
          className="flex items-start justify-between gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          <span>Could not move: {drag.moveError}</span>
          <button
            type="button"
            aria-label="Dismiss"
            onClick={drag.clearMoveError}
            className="shrink-0 rounded px-1 hover:bg-destructive/10"
          >
            ×
          </button>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      )}

      {!isLoading && items.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <FolderOpen className="size-12" aria-hidden="true" />
          <p className="text-sm">This folder is empty</p>
        </div>
      )}

      {!isLoading && items.length > 0 && (
        <div ref={fileListRef} data-testid="file-list" className="relative flex-1 overflow-auto">
          {viewMode === 'list' ? (
            <FileTable {...sharedProps} onSelectAll={handleSelectAll} />
          ) : (
            <FileGrid {...sharedProps} />
          )}
          {dragRect && (
            <div
              data-testid="drag-overlay"
              aria-hidden="true"
              className="pointer-events-none fixed z-30 rounded-sm border border-primary/60 bg-primary/10"
              style={{
                top: dragRect.y,
                left: dragRect.x,
                width: dragRect.width,
                height: dragRect.height,
              }}
            />
          )}
        </div>
      )}

      {contextMenu?.kind === 'single' && (
        <FileContextMenu
          item={contextMenu.item}
          position={{ x: contextMenu.x, y: contextMenu.y }}
          assistantActions={assistantActions?.(contextMenu.item) ?? []}
          onClose={() => setContextMenu(null)}
          onPreview={(item) => setPreviewItemId(item.id)}
          onDownload={actions.downloadItem}
          onRename={actions.renameItem ? setRenameTarget : undefined}
          onMove={actions.moveItem ? setMoveTarget : undefined}
          onShare={actions.share}
          onCopyName={(item) => void navigator.clipboard?.writeText(item.name)}
          onToggleStar={actions.toggleStar}
          onTrash={actions.trashItem ? (item) => setTrashTargets([item]) : undefined}
          onAssistantAction={onAssistantAction}
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

      {actions.createFolder && (
        <CreateFolderDialog
          open={showCreateFolder}
          loading={pending}
          onConfirm={(name) =>
            void run(() => actions.createFolder!(name), () => setShowCreateFolder(false))
          }
          onClose={() => setShowCreateFolder(false)}
        />
      )}

      {actions.renameItem && (
        <RenameDialog
          open={!!renameTarget}
          initialName={renameTarget?.name ?? ''}
          loading={pending}
          onConfirm={(name) =>
            renameTarget &&
            void run(() => actions.renameItem!(renameTarget.id, name), () => setRenameTarget(null))
          }
          onClose={() => setRenameTarget(null)}
        />
      )}

      {actions.moveItem && (
        <MoveDialog
          open={!!moveTarget}
          itemId={moveTarget?.id ?? ''}
          loading={pending}
          // Undefined falls back to the dialog's signed-in drive source.
          source={folderSource}
          onConfirm={(targetParentId) =>
            moveTarget &&
            void run(() => actions.moveItem!(moveTarget.id, targetParentId), () =>
              setMoveTarget(null),
            )
          }
          onClose={() => setMoveTarget(null)}
        />
      )}

      {actions.trashItem && (
        <ConfirmTrashDialog
          open={trashTargets.length > 0}
          itemNames={trashTargets.map((i) => i.name)}
          loading={pending}
          onConfirm={async () => {
            setPending(true)
            const failures: string[] = []
            for (const item of trashTargets) {
              try {
                await actions.trashItem!(item.id)
              } catch (err) {
                failures.push(`${item.name} — ${isApiError(err) ? err.message : 'failed'}`)
              }
            }
            setPending(false)
            setTrashTargets([])
            clearSelection()
            setActionError(failures.length > 0 ? failures.join('; ') : null)
          }}
          onClose={() => setTrashTargets([])}
        />
      )}

      {actions.uploadFiles && (
        <UploadQueue onRetry={(task) => task.file && actions.uploadFiles!([task.file])} />
      )}

      <PreviewDialog
        itemId={previewItemId}
        source={previewSource}
        onClose={() => setPreviewItemId(null)}
      />
    </div>
  )

  return actions.uploadFiles ? (
    <UploadDropzone onFiles={actions.uploadFiles} onFolders={actions.uploadFolders}>
      {body}
    </UploadDropzone>
  ) : (
    body
  )
}
