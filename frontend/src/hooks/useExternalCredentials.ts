import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { externalModelApi } from '@/api/externalModelApi'
import type { ExternalCredentialUpsert } from '@/api/types'

export const externalCredentialKeys = {
  all: ['external-credentials'] as const,
}

export function useExternalCredentials() {
  return useQuery({
    queryKey: externalCredentialKeys.all,
    queryFn: () => externalModelApi.list().then((r) => r.data),
  })
}

export function useUpsertExternalCredential() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ExternalCredentialUpsert) =>
      externalModelApi.upsert(body).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: externalCredentialKeys.all })
    },
  })
}

export function useDeleteExternalCredential() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (provider: string) => externalModelApi.remove(provider).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: externalCredentialKeys.all })
    },
  })
}
