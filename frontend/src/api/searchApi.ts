import type { DriveItemResponse, Page } from './types'
import { api } from './client'

export interface SearchParams {
  q: string
  item_type?: 'file' | 'folder'
  mime_type?: string
  page?: number
  page_size?: number
  signal?: AbortSignal
}

export const searchApi = {
  search: ({ signal, ...params }: SearchParams) =>
    api.get<Page<DriveItemResponse>>('/search', { params, signal }),
}
