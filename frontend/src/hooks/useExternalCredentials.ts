import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { modelConnectionApi } from '@/api/externalModelApi'
import type { ConnectionCreate, ConnectionUpdate } from '@/api/types'

export const modelConnectionKeys = {
  all: ['model-connections'] as const,
}

export function useModelConnections() {
  return useQuery({
    queryKey: modelConnectionKeys.all,
    queryFn: () => modelConnectionApi.list().then((r) => r.data),
  })
}

export function useCreateModelConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ConnectionCreate) => modelConnectionApi.create(body).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: modelConnectionKeys.all })
    },
  })
}

export function useUpdateModelConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ConnectionUpdate }) =>
      modelConnectionApi.update(id, body).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: modelConnectionKeys.all })
    },
  })
}

export function useDeleteModelConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => modelConnectionApi.remove(id).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: modelConnectionKeys.all })
    },
  })
}
