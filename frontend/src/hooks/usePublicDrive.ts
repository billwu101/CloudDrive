import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { isApiError } from '@/api/client'
import {
  createSharedFolder,
  downloadSharedItem,
  fetchSharePreviewUrl,
  listShareChildren,
  uploadSharedFile,
} from '@/api/publicShareApi'
import type { PreviewInfoResponse, PublicItem } from '@/api/types'
import type { FolderSource } from '@/components/drive/MoveDialog'
import type { PreviewSource } from '@/components/preview/PreviewDialog'
import { runWithConcurrency, UPLOAD_CONCURRENCY, uploadErrorMessage } from '@/lib/uploadLimits'
import { useUploadStore } from '@/stores/uploadStore'

import { relativePathOf } from './useUpload'

/**
 * Guest-side equivalents of the drive hooks (proposal §28.8).
 *
 * These exist so the guest page can reuse My Drive's components rather than
 * growing a parallel UI. Differences from `useUpload` / `useDrive` are only
 * ever "which endpoint", never "which behaviour".
 */

export const publicKeys = {
  children: (folderId: string) => ['public-share', 'children', folderId] as const,
  /** Whole prefix — a move touches two folders, so invalidating one would miss. */
  allChildren: ['public-share', 'children'] as const,
}

export function useGuestChildren(folderId: string) {
  return useQuery({
    queryKey: publicKeys.children(folderId),
    queryFn: () => listShareChildren(folderId),
  })
}

/**
 * Upload into a shared folder.
 *
 * No chunked path and no quota pre-check, unlike the signed-in version: the
 * guest endpoint is a single multipart POST, and the quota being spent belongs
 * to the owner, whose numbers a guest cannot read. An over-quota upload is
 * therefore rejected by the server rather than predicted here.
 */
export function useGuestUploadFiles(folderId: string) {
  const qc = useQueryClient()
  const { addTasks, markUploading, markCompleted, markFailed, settleBatch } = useUploadStore()

  const upload = useCallback(
    async (files: File[]) => {
      const tasks = addTasks(files, folderId)
      await runWithConcurrency(tasks, UPLOAD_CONCURRENCY, async (task) => {
        if (task.file === null) return
        markUploading(task.id)
        try {
          await uploadSharedFile(folderId, task.file)
          markCompleted(task.id)
        } catch (err) {
          markFailed(task.id, uploadErrorMessage(err), isApiError(err) ? err.code : undefined)
        }
      })
      void qc.invalidateQueries({ queryKey: publicKeys.allChildren })
      settleBatch(tasks.map((t) => t.id))
    },
    [folderId, addTasks, markUploading, markCompleted, markFailed, settleBatch, qc],
  )

  return { upload }
}

/** Upload whole folders, recreating their structure inside the shared subtree. */
export function useGuestUploadFolders(folderId: string) {
  const qc = useQueryClient()
  const { addTasks, markUploading, markCompleted, markFailed, settleBatch } = useUploadStore()

  const uploadFolders = useCallback(
    async (files: File[]) => {
      // Keyed by path so each directory is created once however many files
      // land in it; '' is the folder we are uploading into.
      const idByPath = new Map<string, string>([['', folderId]])

      const ensureFolder = async (path: string): Promise<string | null> => {
        const known = idByPath.get(path)
        if (known) return known
        const cut = path.lastIndexOf('/')
        const parentPath = cut === -1 ? '' : path.slice(0, cut)
        const name = cut === -1 ? path : path.slice(cut + 1)
        const parentId = await ensureFolder(parentPath)
        if (parentId === null) return null
        try {
          const created = await createSharedFolder(parentId, name)
          idByPath.set(path, created.id)
          return created.id
        } catch {
          // Most likely the name is taken — reuse it, so uploading the same
          // tree twice merges instead of failing.
          const listing = await listShareChildren(parentId)
          const existing = listing.items.find((i) => i.name === name && i.item_type === 'FOLDER')
          if (!existing) return null
          idByPath.set(path, existing.id)
          return existing.id
        }
      }

      const tasks = addTasks(files, folderId)
      // Sequential: concurrent creates of the same directory would race, and
      // the loser gets a name conflict rather than the folder it needed.
      for (const task of tasks) {
        if (task.file === null) continue
        const rel = relativePathOf(task.file)
        const cut = rel.lastIndexOf('/')
        markUploading(task.id)
        const parentId = await ensureFolder(cut === -1 ? '' : rel.slice(0, cut))
        if (parentId === null) {
          markFailed(task.id, 'Could not create the containing folder')
          continue
        }
        try {
          await uploadSharedFile(parentId, task.file)
          markCompleted(task.id)
        } catch (err) {
          markFailed(task.id, uploadErrorMessage(err), isApiError(err) ? err.code : undefined)
        }
      }
      void qc.invalidateQueries({ queryKey: publicKeys.allChildren })
      settleBatch(tasks.map((t) => t.id))
    },
    [folderId, addTasks, markUploading, markCompleted, markFailed, settleBatch, qc],
  )

  return { uploadFolders }
}

/** Object URL for a shared file's preview bytes; revoked on change/unmount. */
function useGuestBlobUrl(itemId: string | null): { url: string | null; isError: boolean } {
  const [url, setUrl] = useState<string | null>(null)
  const [isError, setIsError] = useState(false)

  useEffect(() => {
    if (!itemId) return
    let objectUrl: string | null = null
    let cancelled = false
    fetchSharePreviewUrl(itemId)
      .then((u) => {
        // A late arrival after unmount still allocated a URL — release it
        // rather than setting state on a gone component.
        if (cancelled) {
          URL.revokeObjectURL(u)
          return
        }
        objectUrl = u
        setUrl(u)
        setIsError(false)
      })
      .catch(() => {
        if (!cancelled) setIsError(true)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      setUrl(null)
      setIsError(false)
    }
  }, [itemId])

  return { url, isError }
}

/**
 * Preview wiring for the shared `PreviewDialog`.
 *
 * There is no guest equivalent of `/preview/{id}`: the type and filename came
 * down with the folder listing, so the "info" half is answered from the items
 * already on screen instead of another request.
 */
export function useGuestPreviewSource(items: PublicItem[]): PreviewSource {
  return useMemo(
    () => ({
      useInfo: (itemId: string | null) => {
        const item = itemId ? items.find((i) => i.id === itemId) : undefined
        const data: PreviewInfoResponse | undefined = item
          ? {
              item_id: item.id,
              preview_type: item.preview_type,
              mime_type: item.mime_type,
              size_bytes: item.size_bytes,
              filename: item.name,
            }
          : undefined
        return { data, isLoading: false, isError: false }
      },
      useBlobUrl: useGuestBlobUrl,
      download: downloadSharedItem,
    }),
    [items],
  )
}

/** Folder picker for `MoveDialog`, rooted at the share root (design §5.9.6). */
export function useGuestFolderSource(shareRootId: string, shareRootName: string): FolderSource {
  return useMemo(
    () => ({
      useFolders: (parentId?: string) => {
        const { data, isLoading } = useGuestChildren(parentId ?? shareRootId)
        return {
          folders: (data?.items ?? []).filter((i) => i.item_type === 'FOLDER'),
          isLoading,
        }
      },
      rootLabel: shareRootName,
      rootId: shareRootId,
    }),
    [shareRootId, shareRootName],
  )
}
