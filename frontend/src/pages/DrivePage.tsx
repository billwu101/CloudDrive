import { ArrowLeft } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { downloadItem, triggerBlobDownload } from '@/api/download'
import { driveApi } from '@/api/driveApi'
import type {
  AssistantSkillExecuteResponse,
  AssistantSkillResponse,
  DriveItemResponse,
} from '@/api/types'
import { AssistantSkillResultDialog } from '@/components/assistant/AssistantSkillResultDialog'
import { Breadcrumbs, type BreadcrumbItem } from '@/components/drive/Breadcrumbs'
import { DriveExplorer, type ExplorerActions } from '@/components/drive/DriveExplorer'
import { type AssistantContextMenuAction } from '@/components/drive/FileContextMenu'
import { ShareDialog } from '@/components/share/ShareDialog'
import { useAssistantSkills, useExecuteAssistantSkill } from '@/hooks/useAssistant'
import {
  useCreateFolder,
  useDriveItems,
  useFolderAncestors,
  useFolderItem,
  useMoveItem,
  useMoveToTrash,
  useRenameItem,
  useSetStarred,
} from '@/hooks/useDrive'
import { useUploadFiles, useUploadFolders } from '@/hooks/useUpload'
import { useUIStore } from '@/stores/uiStore'

function assistantActionsForItem(
  skills: AssistantSkillResponse[],
  item: DriveItemResponse,
): AssistantContextMenuAction[] {
  return skills.flatMap((skill) =>
    skill.manifest.ui.context_menu
      .filter((action) => action.item_types.includes(item.item_type))
      .map((action) => ({
        skillId: skill.id,
        label: action.label,
        handler: action.handler,
      })),
  )
}

/**
 * My Drive — a thin assembly around `DriveExplorer` (design §5.9.6 point 10):
 * routing, the uiStore-backed selection (AssistantPanel reads it for chat
 * attachments), and the owner-only capabilities the guest page never wires —
 * starring, sharing, assistant skills.
 */
export function DrivePage() {
  const { folderId } = useParams<{ folderId?: string }>()
  const navigate = useNavigate()
  const selectedIds = useUIStore((s) => s.selectedItemIds)
  const selectItem = useUIStore((s) => s.selectItem)
  const selectAll = useUIStore((s) => s.selectAll)
  const clearSelection = useUIStore((s) => s.clearSelection)

  const { data, isLoading } = useDriveItems(folderId)
  const { data: folderItem } = useFolderItem(folderId)
  const { data: ancestorsData } = useFolderAncestors(folderId)
  const { data: assistantSkills = [] } = useAssistantSkills()
  const createFolder = useCreateFolder(folderId)
  const rename = useRenameItem(folderId)
  const move = useMoveItem()
  const star = useSetStarred(folderId)
  const trash = useMoveToTrash(folderId)
  const executeAssistantSkill = useExecuteAssistantSkill()
  const { upload } = useUploadFiles(folderId)
  const { uploadFolders } = useUploadFolders(folderId)

  const [shareTarget, setShareTarget] = useState<DriveItemResponse | null>(null)
  const [assistantSkillResult, setAssistantSkillResult] =
    useState<AssistantSkillExecuteResponse | null>(null)

  const ancestors: BreadcrumbItem[] = (ancestorsData ?? []).map((a) => ({ id: a.id, name: a.name }))
  const items = useMemo(() => data?.items ?? [], [data?.items])

  // Selection belongs to one folder's listing. Without this, double-clicking a
  // folder (the click selects it, the second click navigates) left that folder
  // selected while you stood inside it — the toolbar then offered to trash an
  // item that wasn't even on screen. Keyed on folderId so it also covers
  // breadcrumbs, the back button and browser history.
  useEffect(() => {
    clearSelection()
  }, [folderId, clearSelection])

  const handleBack = useCallback(() => {
    if (!folderId) return
    const parentId = folderItem?.parent_id
    if (parentId) {
      navigate(`/drive/folder/${parentId}`)
    } else {
      navigate('/drive')
    }
  }, [folderId, folderItem?.parent_id, navigate])

  const handleDownloadSelection = useCallback(async (selected: DriveItemResponse[]) => {
    const ids = selected.map((i) => i.id)
    if (ids.length === 0) return
    const res = await driveApi.downloadArchive(ids)
    // The server names the zip after the selection (folder/file name); read it
    // back from Content-Disposition since a blob URL carries no filename.
    const cd = (res.headers['content-disposition'] as string | undefined) ?? ''
    const match = /filename\*=UTF-8''([^;]+)/i.exec(cd)
    const filename = match ? decodeURIComponent(match[1]) : 'download.zip'
    triggerBlobDownload(res.data, filename)
  }, [])

  const handleAssistantAction = useCallback(
    (action: AssistantContextMenuAction, item: DriveItemResponse) => {
      executeAssistantSkill.mutate(
        { skillId: action.skillId, itemId: item.id },
        { onSuccess: setAssistantSkillResult },
      )
    },
    [executeAssistantSkill],
  )

  const actions: ExplorerActions<DriveItemResponse> = useMemo(
    () => ({
      createFolder: (name) => createFolder.mutateAsync(name),
      renameItem: (id, name) => rename.mutateAsync({ id, name }),
      moveItem: (id, targetParentId) => move.mutateAsync({ id, targetParentId }),
      trashItem: (id) => trash.mutateAsync(id),
      uploadFiles: upload,
      uploadFolders,
      downloadItem: (item) => void downloadItem(item.id, item.name),
      downloadSelection: handleDownloadSelection,
      toggleStar: (item) => star.mutate({ id: item.id, starred: !item.is_starred }),
      share: setShareTarget,
    }),
    [createFolder, rename, move, trash, upload, uploadFolders, handleDownloadSelection, star],
  )

  return (
    <>
      <DriveExplorer
        items={items}
        isLoading={isLoading}
        selection={{ selectedIds, selectItem, selectAll, clearSelection }}
        breadcrumb={
          <>
            {folderId && (
              <button
                onClick={handleBack}
                aria-label="Go to parent folder"
                className="flex shrink-0 items-center rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <ArrowLeft className="size-4" aria-hidden="true" />
              </button>
            )}
            <Breadcrumbs ancestors={ancestors} current={folderItem?.name} />
          </>
        }
        onOpenFolder={(item) => navigate(`/drive/folder/${item.id}`)}
        actions={actions}
        assistantActions={(item) => assistantActionsForItem(assistantSkills, item)}
        onAssistantAction={handleAssistantAction}
      />

      {shareTarget && (
        <ShareDialog
          open
          itemId={shareTarget.id}
          itemName={shareTarget.name}
          onClose={() => setShareTarget(null)}
        />
      )}
      <AssistantSkillResultDialog
        result={assistantSkillResult}
        onClose={() => setAssistantSkillResult(null)}
      />
    </>
  )
}
