import type { DriveItemResponse, Page } from './types'
import { api } from './client'

export const trashApi = {
  moveToTrash: (item_id: string) =>
    api.post<DriveItemResponse>(`/trash/items/${item_id}`),

  listTrash: (page = 1, page_size = 50, signal?: AbortSignal) =>
    api.get<Page<DriveItemResponse>>('/trash', { params: { page, page_size }, signal }),

  restore: (item_id: string) =>
    api.post<DriveItemResponse>(`/trash/items/${item_id}/restore`),

  permanentDelete: (item_id: string) =>
    api.delete<void>(`/trash/items/${item_id}`),

  emptyTrash: () => api.delete<void>('/trash'),
}
