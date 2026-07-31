import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Check,
  ChevronRight,
  Download,
  File,
  Folder,
  FolderPlus,
  Loader2,
  Pencil,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { useRef, useState } from 'react'

import { isApiError } from '@/api/client'
import {
  createSharedFolder,
  listShareChildren,
  moveSharedItem,
  renameSharedItem,
  trashSharedItem,
  uploadSharedFile,
} from '@/api/publicShareApi'
import type { PublicItem } from '@/api/types'
import { DRAG_MIME } from '@/hooks/useDragMove'
import { formatBytes } from '@/lib/uploadLimits'

interface PublicFolderBrowserProps {
  /** Folder currently being shown — the share root, or one of its descendants. */
  folder: PublicItem
  /** Path from the share root down to `folder`, root first. */
  trail: PublicItem[]
  canDownload: boolean
  /** Editor links only (proposal §33) — turns on the write controls. */
  canEdit: boolean
  onOpenFolder: (item: PublicItem) => void
  onOpenFile: (item: PublicItem) => void
  onNavigateTo: (depth: number) => void
  onDownload: (item: PublicItem) => void
}

export function PublicFolderBrowser({
  folder,
  trail,
  canDownload,
  canEdit,
  onOpenFolder,
  onOpenFile,
  onNavigateTo,
  onDownload,
}: PublicFolderBrowserProps) {
  const qc = useQueryClient()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['public-share', 'children', folder.id],
    queryFn: () => listShareChildren(folder.id),
  })

  const [creating, setCreating] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [dropTargetId, setDropTargetId] = useState<string | null>(null)
  const [draggingId, setDraggingId] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  // Moves touch two folders (source and destination), so the whole children
  // prefix is invalidated rather than just the folder on screen.
  const invalidate = () => qc.invalidateQueries({ queryKey: ['public-share', 'children'] })
  const fail = (err: unknown) =>
    setActionError(isApiError(err) ? err.message : 'Something went wrong.')

  const createFolder = useMutation({
    mutationFn: (name: string) => createSharedFolder(folder.id, name),
    onSuccess: () => {
      setCreating(false)
      setNewFolderName('')
      setActionError(null)
      void invalidate()
    },
    onError: fail,
  })

  const rename = useMutation({
    mutationFn: (input: { id: string; name: string }) => renameSharedItem(input.id, input.name),
    onSuccess: () => {
      setRenamingId(null)
      setActionError(null)
      void invalidate()
    },
    onError: fail,
  })

  const trash = useMutation({
    mutationFn: (id: string) => trashSharedItem(id),
    onSuccess: () => {
      setActionError(null)
      void invalidate()
    },
    onError: fail,
  })

  const move = useMutation({
    mutationFn: (input: { id: string; parentId: string }) =>
      moveSharedItem(input.id, input.parentId),
    onSuccess: () => {
      setActionError(null)
      void invalidate()
    },
    onError: fail,
  })

  const upload = useMutation({
    // One file per call — a per-file failure (name clash, quota) should not
    // take the rest of the batch down with it.
    mutationFn: (file: globalThis.File) => uploadSharedFile(folder.id, file),
  })

  const handleFiles = async (list: FileList | null) => {
    if (!list || list.length === 0) return
    setActionError(null)
    const failures: string[] = []
    for (const file of Array.from(list)) {
      try {
        await upload.mutateAsync(file)
      } catch (err) {
        failures.push(`${file.name} — ${isApiError(err) ? err.message : 'upload failed'}`)
      }
    }
    void invalidate()
    if (failures.length > 0) setActionError(failures.join('; '))
  }

  // ── Drag to move (same gesture and MIME as the main drive, proposal §31).
  // No multi-select on the guest page, so a drag carries exactly one id.

  const canAcceptDrop = (targetId: string, e: React.DragEvent) =>
    canEdit && e.dataTransfer.types.includes(DRAG_MIME) && draggingId !== targetId

  const handleDrop = (targetId: string, e: React.DragEvent) => {
    if (!canAcceptDrop(targetId, e)) return
    e.preventDefault()
    setDropTargetId(null)
    const id = e.dataTransfer.getData(DRAG_MIME)
    if (!id || id === targetId) return
    move.mutate({ id, parentId: targetId })
  }

  const dropHandlers = (targetId: string) => ({
    onDragOver: (e: React.DragEvent) => {
      if (!canAcceptDrop(targetId, e)) return
      e.preventDefault()
      e.dataTransfer.dropEffect = 'move'
      setDropTargetId(targetId)
    },
    onDragLeave: () => setDropTargetId((cur) => (cur === targetId ? null : cur)),
    onDrop: (e: React.DragEvent) => handleDrop(targetId, e),
  })

  return (
    <div className="w-full">
      {/* At the share root the breadcrumb's only entry equals the page title —
          rendering it would just print the same name twice. */}
      {trail.length > 1 && (
        <nav aria-label="Breadcrumb" className="mb-3 flex flex-wrap items-center gap-1 text-sm">
          {trail.map((crumb, i) => (
            <span key={crumb.id} className="flex items-center gap-1">
              {i > 0 && (
                <ChevronRight className="size-3 text-muted-foreground" aria-hidden="true" />
              )}
              <button
                type="button"
                onClick={() => onNavigateTo(i)}
                disabled={i === trail.length - 1}
                className={`rounded px-1 hover:bg-accent disabled:font-medium disabled:hover:bg-transparent ${
                  dropTargetId === crumb.id ? 'bg-accent ring-1 ring-ring' : ''
                }`}
                {...(i < trail.length - 1 ? dropHandlers(crumb.id) : {})}
              >
                {crumb.name}
              </button>
            </span>
          ))}
        </nav>
      )}

      {canEdit && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setCreating(true)
              setNewFolderName('')
            }}
            className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
          >
            <FolderPlus className="size-4" aria-hidden="true" />
            New folder
          </button>
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            disabled={upload.isPending}
            className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
          >
            {upload.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Upload className="size-4" aria-hidden="true" />
            )}
            {upload.isPending ? 'Uploading…' : 'Upload'}
          </button>
          <input
            ref={fileInput}
            type="file"
            multiple
            hidden
            aria-label="Upload files"
            onChange={(e) => {
              void handleFiles(e.target.files)
              e.target.value = ''
            }}
          />
        </div>
      )}

      {creating && (
        <form
          className="mb-3 flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (newFolderName.trim()) createFolder.mutate(newFolderName.trim())
          }}
        >
          <input
            autoFocus
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            placeholder="Folder name"
            aria-label="Folder name"
            className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
          />
          <button
            type="submit"
            disabled={createFolder.isPending || !newFolderName.trim()}
            aria-label="Create folder"
            className="rounded-md bg-primary p-1.5 text-primary-foreground disabled:opacity-50"
          >
            <Check className="size-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="Cancel new folder"
            onClick={() => setCreating(false)}
            className="rounded-md border p-1.5 hover:bg-accent"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </form>
      )}

      {actionError && (
        <p role="alert" className="mb-3 text-sm text-destructive">
          {actionError}
        </p>
      )}

      {isLoading && (
        <div className="flex justify-center py-10">
          <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Loading" />
        </div>
      )}

      {isError && (
        <p className="py-10 text-center text-sm text-destructive">Could not load this folder.</p>
      )}

      {data && data.items.length === 0 && !creating && (
        <p className="py-10 text-center text-sm text-muted-foreground">This folder is empty.</p>
      )}

      {data && data.items.length > 0 && (
        <ul className="divide-y rounded-md border">
          {data.items.map((item) => (
            <li
              key={item.id}
              draggable={canEdit}
              onDragStart={(e) => {
                if (!canEdit) return
                e.dataTransfer.effectAllowed = 'move'
                e.dataTransfer.setData(DRAG_MIME, item.id)
                setDraggingId(item.id)
              }}
              onDragEnd={() => {
                setDraggingId(null)
                setDropTargetId(null)
              }}
              {...(item.item_type === 'FOLDER' ? dropHandlers(item.id) : {})}
              className={`flex items-center gap-3 px-3 py-2 ${
                dropTargetId === item.id ? 'bg-accent' : ''
              } ${draggingId === item.id ? 'opacity-50' : ''}`}
            >
              {renamingId === item.id ? (
                <form
                  className="flex min-w-0 flex-1 items-center gap-2"
                  onSubmit={(e) => {
                    e.preventDefault()
                    if (renameValue.trim()) rename.mutate({ id: item.id, name: renameValue.trim() })
                  }}
                >
                  <input
                    autoFocus
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    aria-label={`New name for ${item.name}`}
                    className="min-w-0 flex-1 rounded-md border border-input bg-background px-2 py-1 text-sm outline-none focus:border-ring"
                  />
                  <button
                    type="submit"
                    disabled={rename.isPending || !renameValue.trim()}
                    aria-label="Save name"
                    className="rounded p-1 hover:bg-accent disabled:opacity-50"
                  >
                    <Check className="size-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    aria-label="Cancel rename"
                    onClick={() => setRenamingId(null)}
                    className="rounded p-1 hover:bg-accent"
                  >
                    <X className="size-4" aria-hidden="true" />
                  </button>
                </form>
              ) : (
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-center gap-3 text-left"
                  onClick={() =>
                    item.item_type === 'FOLDER' ? onOpenFolder(item) : onOpenFile(item)
                  }
                >
                  {item.item_type === 'FOLDER' ? (
                    <Folder className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  ) : (
                    <File className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  )}
                  <span className="truncate text-sm">{item.name}</span>
                </button>
              )}
              {item.item_type === 'FILE' && renamingId !== item.id && (
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatBytes(item.size_bytes)}
                </span>
              )}
              {canDownload && item.item_type === 'FILE' && (
                <button
                  type="button"
                  aria-label={`Download ${item.name}`}
                  onClick={() => onDownload(item)}
                  className="shrink-0 rounded p-1 hover:bg-accent"
                >
                  <Download className="size-4" aria-hidden="true" />
                </button>
              )}
              {canEdit && renamingId !== item.id && (
                <>
                  <button
                    type="button"
                    aria-label={`Rename ${item.name}`}
                    onClick={() => {
                      setRenamingId(item.id)
                      setRenameValue(item.name)
                    }}
                    className="shrink-0 rounded p-1 hover:bg-accent"
                  >
                    <Pencil className="size-4" aria-hidden="true" />
                  </button>
                  {/* Only children are ever listed, never the share root
                      itself — so a trash button here can never aim at the
                      root the server refuses to trash (§6.12.11b). */}
                  <button
                    type="button"
                    aria-label={`Move ${item.name} to trash`}
                    onClick={() => trash.mutate(item.id)}
                    disabled={trash.isPending}
                    className="shrink-0 rounded p-1 hover:bg-accent disabled:opacity-50"
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
