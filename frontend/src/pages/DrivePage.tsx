import { ArrowLeft, FolderOpen } from 'lucide-react'
import { useCallback, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import type { DriveItemResponse } from '@/api/types'
import { Breadcrumbs, type BreadcrumbItem } from '@/components/drive/Breadcrumbs'
import { ConfirmTrashDialog } from '@/components/drive/ConfirmTrashDialog'
import { CreateFolderDialog } from '@/components/drive/CreateFolderDialog'
import { DriveToolbar } from '@/components/drive/DriveToolbar'
import { FileContextMenu } from '@/components/drive/FileContextMenu'
import { FileGrid } from '@/components/drive/FileGrid'
import { FileTable } from '@/components/drive/FileTable'
import { MoveDialog } from '@/components/drive/MoveDialog'
import { MultiFileContextMenu } from '@/components/drive/MultiFileContextMenu'
import { RenameDialog } from '@/components/drive/RenameDialog'
import { PreviewDialog } from '@/components/preview/PreviewDialog'
import { UploadButton } from '@/components/upload/UploadButton'
import { UploadDropzone } from '@/components/upload/UploadDropzone'
import { UploadQueue } from '@/components/upload/UploadQueue'
import { useCreateFolder, useDriveItems, useFolderAncestors, useFolderItem, useMoveItem, useMoveToTrash, useRenameItem, useSetStarred } from '@/hooks/useDrive'
import { useDragSelect } from '@/hooks/useDragSelect'
import { useUploadFiles } from '@/hooks/useUpload'
import { useUIStore } from '@/stores/uiStore'

interface SingleContextMenuState {
  kind: 'single'
  item: DriveItemResponse
  x: number
  y: number
}

interface MultiContextMenuState {
  kind: 'multi'
  x: number
  y: number
}

type ContextMenuState = SingleContextMenuState | MultiContextMenuState | null

export function DrivePage() {
  const { folderId } = useParams<{ folderId?: string }>()
  const navigate = useNavigate()
  const viewMode = useUIStore((s) => s.viewMode)
  const selectedIds = useUIStore((s) => s.selectedItemIds)
  const selectItem = useUIStore((s) => s.selectItem)
  const selectAll = useUIStore((s) => s.selectAll)
  const clearSelection = useUIStore((s) => s.clearSelection)

  const { data, isLoading } = useDriveItems(folderId)
  const { data: folderItem } = useFolderItem(folderId)
  const { data: ancestorsData } = useFolderAncestors(folderId)
  const createFolder = useCreateFolder(folderId)
  const rename = useRenameItem(folderId)
  const move = useMoveItem()
  const star = useSetStarred(folderId)
  const trash = useMoveToTrash(folderId)

  const { upload } = useUploadFiles(folderId)

  const fileListRef = useRef<HTMLDivElement>(null)
  const [showCreateFolder, setShowCreateFolder] = useState(false)
  const [renameTarget, setRenameTarget] = useState<DriveItemResponse | null>(null)
  const [moveTarget, setMoveTarget] = useState<DriveItemResponse | null>(null)
  const [trashTargets, setTrashTargets] = useState<DriveItemResponse[]>([])
  const [previewItemId, setPreviewItemId] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState>(null)

  const ancestors: BreadcrumbItem[] = (ancestorsData ?? []).map((a) => ({ id: a.id, name: a.name }))
  const currentFolderName = folderItem?.name
  const items = useMemo(() => data?.items ?? [], [data?.items])

  const handleBack = useCallback(() => {
    if (!folderId) return
    const parentId = folderItem?.parent_id
    if (parentId) {
      navigate(`/drive/folder/${parentId}`)
    } else {
      navigate('/drive')
    }
  }, [folderId, folderItem?.parent_id, navigate])

  const handleDoubleClick = useCallback(
    (item: DriveItemResponse) => {
      if (item.item_type === 'FOLDER') {
        navigate(`/drive/folder/${item.id}`)
      } else {
        setPreviewItemId(item.id)
      }
    },
    [navigate],
  )

  const handleContextMenu = useCallback(
    (item: DriveItemResponse, e: React.MouseEvent) => {
      e.preventDefault()
      // If the right-clicked item is part of a multi-selection → show multi-item menu
      if (selectedIds.size > 1 && selectedIds.has(item.id)) {
        setContextMenu({ kind: 'multi', x: e.clientX, y: e.clientY })
      } else {
        // Single item: if not already selected, replace selection
        if (!selectedIds.has(item.id)) {
          selectItem(item.id)
        }
        setContextMenu({ kind: 'single', item, x: e.clientX, y: e.clientY })
      }
    },
    [selectedIds, selectItem],
  )

  const handleCheckboxClick = useCallback(
    (item: DriveItemResponse, e: React.MouseEvent) => {
      e.stopPropagation()
      selectItem(item.id, true) // always multi-select mode
    },
    [selectItem],
  )

  const handleSelectAll = useCallback(() => {
    if (items.every((i) => selectedIds.has(i.id))) {
      clearSelection()
    } else {
      selectAll(items.map((i) => i.id))
    }
  }, [items, selectedIds, selectAll, clearSelection])

  const handleStarClick = useCallback(
    (item: DriveItemResponse, e: React.MouseEvent) => {
      e.stopPropagation()
      star.mutate({ id: item.id, starred: !item.is_starred })
    },
    [star],
  )

  const handleTrashSelected = useCallback(() => {
    const targets = items.filter((i) => selectedIds.has(i.id))
    setTrashTargets(targets)
  }, [items, selectedIds])

  const handleRetryUpload = useCallback(
    (task: { file: File }) => {
      upload([task.file])
    },
    [upload],
  )

  const handleDragSelect = useCallback((ids: string[]) => selectAll(ids), [selectAll])
  const { dragRect } = useDragSelect(fileListRef, handleDragSelect, clearSelection)

  const sharedProps = {
    items,
    selectedIds,
    onItemClick: (item: DriveItemResponse, e: React.MouseEvent) => {
      e.stopPropagation()
      selectItem(item.id, e.metaKey || e.ctrlKey)
    },
    onItemDoubleClick: handleDoubleClick,
    onItemContextMenu: handleContextMenu,
    onStarClick: handleStarClick,
    onCheckboxClick: handleCheckboxClick,
  }

  return (
    <UploadDropzone onFiles={upload}>
      <div className="flex h-full flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            {folderId && (
              <button
                onClick={handleBack}
                aria-label="Go to parent folder"
                className="flex shrink-0 items-center rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <ArrowLeft className="size-4" aria-hidden="true" />
              </button>
            )}
            <Breadcrumbs ancestors={ancestors} current={currentFolderName} />
          </div>
          <div className="flex items-center gap-2">
            <UploadButton onFiles={upload} />
            <DriveToolbar
              selectedCount={selectedIds.size}
              onNewFolder={() => setShowCreateFolder(true)}
              onTrashSelected={handleTrashSelected}
            />
          </div>
        </div>

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
            {/* Rubber-band selection overlay */}
            {dragRect && (
              <div
                data-testid="drag-overlay"
                aria-hidden="true"
                className="pointer-events-none fixed z-30 rounded-sm border border-primary/60 bg-primary/10"
                style={{ top: dragRect.y, left: dragRect.x, width: dragRect.width, height: dragRect.height }}
              />
            )}
          </div>
        )}

        {/* Single-item context menu */}
        {contextMenu?.kind === 'single' && (
          <FileContextMenu
            item={contextMenu.item}
            position={{ x: contextMenu.x, y: contextMenu.y }}
            onClose={() => setContextMenu(null)}
            onPreview={(item) => setPreviewItemId(item.id)}
            onRename={(item) => setRenameTarget(item)}
            onMove={(item) => setMoveTarget(item)}
            onShare={() => {}}
            onCopyLink={() => {}}
            onToggleStar={(item) => star.mutate({ id: item.id, starred: !item.is_starred })}
            onTrash={(item) => setTrashTargets([item])}
          />
        )}

        {/* Multi-item context menu */}
        {contextMenu?.kind === 'multi' && (
          <MultiFileContextMenu
            count={selectedIds.size}
            position={{ x: contextMenu.x, y: contextMenu.y }}
            onClose={() => setContextMenu(null)}
            onTrash={handleTrashSelected}
          />
        )}

        <CreateFolderDialog
          open={showCreateFolder}
          loading={createFolder.isPending}
          onConfirm={(name) =>
            createFolder.mutate(name, { onSuccess: () => setShowCreateFolder(false) })
          }
          onClose={() => setShowCreateFolder(false)}
        />

        <RenameDialog
          open={!!renameTarget}
          initialName={renameTarget?.name ?? ''}
          loading={rename.isPending}
          onConfirm={(name) =>
            renameTarget &&
            rename.mutate({ id: renameTarget.id, name }, { onSuccess: () => setRenameTarget(null) })
          }
          onClose={() => setRenameTarget(null)}
        />

        <MoveDialog
          open={!!moveTarget}
          itemId={moveTarget?.id ?? ''}
          loading={move.isPending}
          onConfirm={(targetParentId) =>
            moveTarget &&
            move.mutate(
              { id: moveTarget.id, targetParentId },
              { onSuccess: () => setMoveTarget(null) },
            )
          }
          onClose={() => setMoveTarget(null)}
        />

        <ConfirmTrashDialog
          open={trashTargets.length > 0}
          itemNames={trashTargets.map((i) => i.name)}
          loading={trash.isPending}
          onConfirm={async () => {
            for (const item of trashTargets) {
              await trash.mutateAsync(item.id)
            }
            setTrashTargets([])
            clearSelection()
          }}
          onClose={() => setTrashTargets([])}
        />

        <UploadQueue onRetry={handleRetryUpload} />

        <PreviewDialog itemId={previewItemId} onClose={() => setPreviewItemId(null)} />
      </div>
    </UploadDropzone>
  )
}
