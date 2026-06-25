import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { snapshotApi } from '@/api/snapshotApi'
import type { RestoreRequest, UpdateSnapshotSettingsRequest } from '@/api/types'

export const snapshotKeys = {
  all: ['snapshots'] as const,
  list: () => [...snapshotKeys.all, 'list'] as const,
  items: (id: string, parentId?: string) =>
    [...snapshotKeys.all, 'items', id, parentId ?? 'root'] as const,
  settings: () => [...snapshotKeys.all, 'settings'] as const,
}

export function useSnapshots() {
  return useQuery({
    queryKey: snapshotKeys.list(),
    queryFn: () => snapshotApi.list().then((r) => r.data),
  })
}

export function useCreateSnapshot() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (label?: string) => snapshotApi.create(label).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: snapshotKeys.list() })
    },
  })
}

export function useSnapshotItems(snapshotId: string | null, parentId?: string) {
  return useQuery({
    queryKey: snapshotKeys.items(snapshotId ?? '', parentId),
    enabled: snapshotId !== null,
    queryFn: () => snapshotApi.items(snapshotId as string, parentId).then((r) => r.data),
  })
}

export function useRestoreSnapshot() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ snapshotId, body }: { snapshotId: string; body: RestoreRequest }) =>
      snapshotApi.restore(snapshotId, body).then((r) => r.data),
    onSuccess: () => {
      // A restore mutates the drive and creates a pre-restore snapshot.
      void queryClient.invalidateQueries({ queryKey: ['drive'] })
      void queryClient.invalidateQueries({ queryKey: snapshotKeys.list() })
    },
  })
}

export function useSnapshotSettings() {
  return useQuery({
    queryKey: snapshotKeys.settings(),
    queryFn: () => snapshotApi.getSettings().then((r) => r.data),
  })
}

export function useUpdateSnapshotSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateSnapshotSettingsRequest) =>
      snapshotApi.updateSettings(body).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: snapshotKeys.settings() })
      // Tightening retention/quota may have pruned snapshots.
      void queryClient.invalidateQueries({ queryKey: snapshotKeys.list() })
    },
  })
}
