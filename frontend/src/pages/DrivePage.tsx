import { FolderOpen } from 'lucide-react'
import { useCallback, useRef, useState } from 'react'
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
import { RenameDialog } from '@/components/drive/RenameDialog'
import { useCreateFolder, useDriveItems, useMoveItem, useMoveToTrash, useRenameItem, useSetStarred } from '@/hooks/useDrive'
import { useUIStore } from '@/stores/uiStore'

interface ContextMenuState {
  item: DriveItemResponse
  x: number
  y: number
}

export function DrivePage() {
  const { folderId } = useParams<{ folderId?: string }>()
  const navigate = useNavigate()
  const viewMode = useUIStore((s) => s.viewMode)
  const selectedIds = useUIStore((s) => s.selectedItemIds)
  const selectItem = useUIStore((s) => s.selectItem)
  const clearSelection = useUIStore((s) => s.clearSelection)

  const { data, isLoading } = useDriveItems(folderId)
  const createFolder = useCreateFolder(folderId)
  const rename = useRenameItem(folderId)
  const move = useMoveItem()
  const star = useSetStarred(folderId)
  const trash = useMoveToTrash(folderId)

  const [showCreateFolder, setShowCreateFolder] = useState(false)
  const [renameTarget, setRenameTarget] = useState<DriveItemResponse | null>(null)
  const [moveTarget, setMoveTarget] = useState<DriveItemResponse | null>(null)
  const [trashTargets, setTrashTargets] = useState<DriveItemResponse[]>([])
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)

  const uploadRef = useRef<HTMLInputElement>(null)

  // Build ancestors breadcrumb from flat data (simplified: just show current folder name)
  const ancestors: BreadcrumbItem[] = []
  const currentName = folderId ? data?.items.find((i) => i.id === folderId)?.name : undefined

  const handleDoubleClick = useCallback(
    (item: DriveItemResponse) => {
      if (item.item_type === 'FOLDER') {
        navigate(`/drive/folder/${item.id}`)
      }
    },
    [navigate],
  )

  const handleContextMenu = useCallback((item: DriveItemResponse, e: React.MouseEvent) => {
    e.preventDefault()
    setContextMenu({ item, x: e.clientX, y: e.clientY })
  }, [])

  const handleStarClick = useCallback(
    (item: DriveItemResponse, e: React.MouseEvent) => {
      e.stopPropagation()
      star.mutate({ id: item.id, starred: !item.is_starred })
    },
    [star],
  )

  const handleTrashSelected = () => {
    const targets = data?.items.filter((i) => selectedIds.has(i.id)) ?? []
    setTrashTargets(targets)
  }

  const items = data?.items ?? []

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Breadcrumbs ancestors={ancestors} current={currentName} />
        <DriveToolbar
          selectedCount={selectedIds.size}
          onUpload={() => uploadRef.current?.click()}
          onNewFolder={() => setShowCreateFolder(true)}
          onTrashSelected={handleTrashSelected}
        />
      </div>

      {/* Hidden file input for upload — wired to router in Stage 9 */}
      <input ref={uploadRef} type="file" multiple className="hidden" aria-hidden="true" />

      {isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">Loading…</div>
      )}

      {!isLoading && items.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <FolderOpen className="size-12" aria-hidden="true" />
          <p className="text-sm">This folder is empty</p>
        </div>
      )}

      {!isLoading && items.length > 0 && (
        <div onClick={() => clearSelection()} className="flex-1 overflow-auto">
          {viewMode === 'list' ? (
            <FileTable
              items={items}
              selectedIds={selectedIds}
              onItemClick={(item, e) => { e.stopPropagation(); selectItem(item.id, e.metaKey || e.ctrlKey) }}
              onItemDoubleClick={handleDoubleClick}
              onItemContextMenu={handleContextMenu}
              onStarClick={handleStarClick}
            />
          ) : (
            <FileGrid
              items={items}
              selectedIds={selectedIds}
              onItemClick={(item, e) => { e.stopPropagation(); selectItem(item.id, e.metaKey || e.ctrlKey) }}
              onItemDoubleClick={handleDoubleClick}
              onItemContextMenu={handleContextMenu}
              onStarClick={handleStarClick}
            />
          )}
        </div>
      )}

      {contextMenu && (
        <FileContextMenu
          item={contextMenu.item}
          position={{ x: contextMenu.x, y: contextMenu.y }}
          onClose={() => setContextMenu(null)}
          onPreview={() => {}}
          onRename={(item) => setRenameTarget(item)}
          onMove={(item) => setMoveTarget(item)}
          onShare={() => {}}
          onCopyLink={() => {}}
          onToggleStar={(item) => star.mutate({ id: item.id, starred: !item.is_starred })}
          onTrash={(item) => setTrashTargets([item])}
        />
      )}

      <CreateFolderDialog
        open={showCreateFolder}
        loading={createFolder.isPending}
        onConfirm={(name) => createFolder.mutate(name, { onSuccess: () => setShowCreateFolder(false) })}
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
    </div>
  )
}
