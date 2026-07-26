import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { type Permission, shareApi } from '@/api/shareApi'

export type { Permission }

export const shareKeys = {
  sharedWithMe: (page = 1) => ['share', 'shared-with-me', page] as const,
  sharedByMe: (page = 1) => ['share', 'shared-by-me', page] as const,
}

export function useSharedWithMe(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: shareKeys.sharedWithMe(page),
    queryFn: ({ signal }) =>
      shareApi.sharedWithMe(page, pageSize, signal).then((r) => r.data),
  })
}

/** Items this user has shared out — the reverse of "shared with me". */
export function useSharedByMe(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: shareKeys.sharedByMe(page),
    queryFn: ({ signal }) => shareApi.sharedByMe(page, pageSize, signal).then((r) => r.data),
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
      qc.invalidateQueries({ queryKey: ['drive'] })
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
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (linkId: string) => shareApi.deactivateLink(linkId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['share'] })
      // The drive listing carries the sharing badges, so it goes stale too.
      qc.invalidateQueries({ queryKey: ['drive'] })
    },
  })
}
