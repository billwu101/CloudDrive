import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { driveApi } from '@/api/driveApi'
import { trashApi } from '@/api/trashApi'
import type { SortField, SortOrder } from '@/api/driveApi'

export { type SortField, type SortOrder }

export const driveKeys = {
  items: (parentId?: string) => ['drive', 'items', parentId ?? 'root'] as const,
  recent: () => ['drive', 'recent'] as const,
  starred: () => ['drive', 'starred'] as const,
}

export function useDriveItems(parentId?: string, sortBy?: SortField, order?: SortOrder) {
  return useQuery({
    queryKey: driveKeys.items(parentId),
    queryFn: ({ signal }) =>
      driveApi
        .listItems({ parent_id: parentId, sort_by: sortBy, order, signal })
        .then((r) => r.data),
  })
}

export function useRecentItems() {
  return useQuery({
    queryKey: driveKeys.recent(),
    queryFn: ({ signal }) =>
      driveApi.getRecent(20, signal).then((r) => ({
        items: r.data,
        total: r.data.length,
        page: 1,
        page_size: r.data.length,
        pages: 1,
      })),
  })
}

export function useStarredItems() {
  return useQuery({
    queryKey: driveKeys.starred(),
    queryFn: ({ signal }) =>
      driveApi.listItems({ signal }).then((r) => ({
        ...r.data,
        items: r.data.items.filter((i) => i.is_starred),
      })),
  })
}

export function useCreateFolder(parentId?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => driveApi.createFolder(name, parentId).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: driveKeys.items(parentId) }),
  })
}

export function useRenameItem(parentId?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      driveApi.rename(id, name).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: driveKeys.items(parentId) }),
  })
}

export function useMoveItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, targetParentId }: { id: string; targetParentId: string | null }) =>
      driveApi.move(id, targetParentId).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['drive', 'items'] }),
  })
}

export function useSetStarred(parentId?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, starred }: { id: string; starred: boolean }) =>
      driveApi.star(id, starred).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: driveKeys.items(parentId) })
      qc.invalidateQueries({ queryKey: driveKeys.starred() })
    },
  })
}

export function useMoveToTrash(parentId?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => trashApi.moveToTrash(id).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: driveKeys.items(parentId) }),
  })
}
