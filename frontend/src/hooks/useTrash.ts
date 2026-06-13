import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { trashApi } from '@/api/trashApi'
import { authKeys } from '@/hooks/useAuth'
import { driveKeys } from '@/hooks/useDrive'

export const trashKeys = {
  list: (page = 1) => ['trash', 'list', page] as const,
}

export function useTrashItems(page = 1, pageSize = 50) {
  return useQuery({
    queryKey: trashKeys.list(page),
    queryFn: ({ signal }) => trashApi.listTrash(page, pageSize, signal).then((r) => r.data),
  })
}

export function useRestoreItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (itemId: string) => trashApi.restore(itemId).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trash'] })
      qc.invalidateQueries({ queryKey: ['drive', 'items'] })
    },
  })
}

export function usePermanentDelete() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (itemId: string) => trashApi.permanentDelete(itemId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trash'] })
      qc.invalidateQueries({ queryKey: authKeys.quota() })
    },
  })
}

export function useEmptyTrash() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => trashApi.emptyTrash(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trash'] })
      qc.invalidateQueries({ queryKey: authKeys.quota() })
      qc.invalidateQueries({ queryKey: driveKeys.items() })
    },
  })
}
