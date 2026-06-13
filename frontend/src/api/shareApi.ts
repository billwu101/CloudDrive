import type { Page, ShareLinkResponse, ShareResponse } from './types'
import { api } from './client'

export type Permission = 'viewer' | 'downloader' | 'editor' | 'owner'

export const shareApi = {
  shareItem: (item_id: string, target_email: string, permission: Permission) =>
    api.post<ShareResponse>(`/share/items/${item_id}`, { target_email, permission }),

  removeShare: (item_id: string, target_user_id: string) =>
    api.delete<void>(`/share/items/${item_id}/users/${target_user_id}`),

  sharedWithMe: (page = 1, page_size = 20, signal?: AbortSignal) =>
    api.get<Page<ShareResponse>>('/share/shared-with-me', {
      params: { page, page_size },
      signal,
    }),

  createLink: (
    item_id: string,
    permission: Permission,
    opts?: { password?: string; expires_at?: string },
  ) =>
    api.post<ShareLinkResponse>(`/share/items/${item_id}/links`, { permission, ...opts }),

  validateLink: (token: string, password?: string) =>
    api.post<ShareLinkResponse>('/share/links/validate', null, {
      params: { token, password },
    }),

  deactivateLink: (link_id: string) =>
    api.delete<void>(`/share/links/${link_id}`),
}
