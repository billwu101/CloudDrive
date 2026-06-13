import type { DriveItemResponse, FileVersionResponse, Page } from './types'
import { api } from './client'

export type SortField = 'name' | 'created_at' | 'updated_at' | 'size_bytes'
export type SortOrder = 'asc' | 'desc'

export interface ListItemsParams {
  parent_id?: string
  sort_by?: SortField
  order?: SortOrder
  page?: number
  page_size?: number
  signal?: AbortSignal
}

export const driveApi = {
  listItems: ({ signal, ...params }: ListItemsParams = {}) =>
    api.get<Page<DriveItemResponse>>('/drive/items', { params, signal }),

  createFolder: (name: string, parent_id?: string) =>
    api.post<DriveItemResponse>('/drive/items/folders', { name, parent_id }),

  rename: (item_id: string, name: string) =>
    api.patch<DriveItemResponse>(`/drive/items/${item_id}/rename`, { name }),

  move: (item_id: string, parent_id: string | null) =>
    api.patch<DriveItemResponse>(`/drive/items/${item_id}/move`, { parent_id }),

  star: (item_id: string, is_starred: boolean) =>
    api.patch<DriveItemResponse>(`/drive/items/${item_id}/star`, { is_starred }),

  getRecent: (limit = 20, signal?: AbortSignal) =>
    api.get<DriveItemResponse[]>('/drive/items/recent', { params: { limit }, signal }),

  listVersions: (item_id: string, signal?: AbortSignal) =>
    api.get<FileVersionResponse[]>(`/drive/items/${item_id}/versions`, { signal }),
}
