import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { type Permission, shareApi } from '@/api/shareApi'

export type { Permission }

export const shareKeys = {
  sharedWithMe: (page = 1) => ['share', 'shared-with-me', page] as const,
}

export function useSharedWithMe(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: shareKeys.sharedWithMe(page),
    queryFn: ({ signal }) =>
      shareApi.sharedWithMe(page, pageSize, signal).then((r) => r.data),
  })
}

export function useShareWithUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      itemId,
      targetEmail,
      permission,
    }: {
      itemId: string
      targetEmail: string
      permission: Permission
    }) => shareApi.shareItem(itemId, targetEmail, permission).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['share'] })
    },
  })
}

export function useRemoveUserShare() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, targetUserId }: { itemId: string; targetUserId: string }) =>
      shareApi.removeShare(itemId, targetUserId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['share'] })
    },
  })
}

export function useCreateShareLink() {
  return useMutation({
    mutationFn: ({
      itemId,
      permission,
      password,
      expiresAt,
    }: {
      itemId: string
      permission: Permission
      password?: string
      expiresAt?: string
    }) =>
      shareApi
        .createLink(itemId, permission, { password, expires_at: expiresAt })
        .then((r) => r.data),
  })
}

export function useDeactivateShareLink() {
  return useMutation({
    mutationFn: (linkId: string) => shareApi.deactivateLink(linkId),
  })
}
