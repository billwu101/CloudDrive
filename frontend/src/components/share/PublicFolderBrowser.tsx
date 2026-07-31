import { useQueryClient } from '@tanstack/react-query'
import { ChevronRight, Folder } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'

import {
  createSharedFolder,
  downloadSharedItem,
  downloadSharedSelection,
  moveSharedItem,
  renameSharedItem,
  trashSharedItem,
} from '@/api/publicShareApi'
import type { PublicItem } from '@/api/types'
import { DriveExplorer, type ExplorerActions } from '@/components/drive/DriveExplorer'
import {
  publicKeys,
  useGuestChildren,
  useGuestFolderSource,
  useGuestPreviewSource,
  useGuestUploadFiles,
  useGuestUploadFolders,
} from '@/hooks/usePublicDrive'

/**
 * The guest file browser: the *same* `DriveExplorer` My Drive renders, with a
 * guest-shaped set of capabilities (proposal §34, user decision 2026-07-31).
 *
 * What is missing is expressed by what is not wired — a viewer wires nothing,
 * a downloader only downloads, an editor gets everything except starring,
 * re-sharing and assistant skills (proposal §34.3), which need an account or
 * the owner's private state.
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

export function PublicFolderBrowser({
  folder,
  trail,
  canDownload,
  canEdit,
  onOpenFolder,
  onNavigateTo,
}: PublicFolderBrowserProps) {
  const qc = useQueryClient()
  const { data, isLoading } = useGuestChildren(folder.id)
  const items = useMemo(() => data?.items ?? [], [data?.items])

  // Guest selection is page-local: uiStore's set is global and feeds the
  // assistant panel, so sharing it would leak picks across open tabs.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const selectItem = useCallback((id: string, multi = false) => {
    setSelectedIds((prev) => {
      if (!multi) return new Set([id])
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])
  const selectAll = useCallback((ids: string[]) => setSelectedIds(new Set(ids)), [])
  const clearSelection = useCallback(() => setSelectedIds(new Set()), [])

  const shareRoot = trail[0] ?? folder
  const previewSource = useGuestPreviewSource(items)
  const folderSource = useGuestFolderSource(shareRoot.id, shareRoot.name)
  const { upload } = useGuestUploadFiles(folder.id)
  const { uploadFolders } = useGuestUploadFolders(folder.id)

  const invalidate = useCallback(
    () => qc.invalidateQueries({ queryKey: publicKeys.allChildren }),
    [qc],
  )

  const actions: ExplorerActions<PublicItem> = useMemo(() => {
    const out: ExplorerActions<PublicItem> = {}
    if (canDownload) {
      out.downloadItem = (item) => void downloadSharedItem(item.id, item.name)
      out.downloadSelection = (selected) => downloadSharedSelection(selected.map((i) => i.id))
    }
    if (canEdit) {
      out.createFolder = (name) => createSharedFolder(folder.id, name).then(invalidate)
      out.renameItem = (id, name) => renameSharedItem(id, name).then(invalidate)
      // `null` would mean the picker's root, which for a guest *is* the share
      // root — resolve it here so the endpoint always gets a real id.
      out.moveItem = (id, targetParentId) =>
        moveSharedItem(id, targetParentId ?? shareRoot.id).then(invalidate)
      out.trashItem = (id) => trashSharedItem(id).then(invalidate)
      out.uploadFiles = upload
      out.uploadFolders = uploadFolders
    }
    return out
  }, [canDownload, canEdit, folder.id, shareRoot.id, invalidate, upload, uploadFolders])

  return (
    <DriveExplorer
      items={items}
      isLoading={isLoading}
      folderKey={folder.id}
      selection={{ selectedIds, selectItem, selectAll, clearSelection }}
      breadcrumb={
        <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1 text-sm">
          {trail.map((crumb, i) => (
            <span key={crumb.id} className="flex min-w-0 items-center gap-1">
              {i > 0 && (
                <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              )}
              <button
                type="button"
                onClick={() => onNavigateTo(i)}
                disabled={i === trail.length - 1}
                className={`flex min-w-0 items-center gap-1 truncate transition-colors ${
                  i === trail.length - 1
                    ? 'font-medium text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {i === 0 && <Folder className="size-4 shrink-0" aria-hidden="true" />}
                <span className="truncate">{crumb.name}</span>
              </button>
            </span>
          ))}
        </nav>
      }
      onOpenFolder={onOpenFolder}
      actions={actions}
      folderSource={folderSource}
      previewSource={previewSource}
    />
  )
}
