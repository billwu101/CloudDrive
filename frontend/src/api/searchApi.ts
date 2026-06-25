import type { BackfillResponse, DriveItemResponse, Page, SemanticHitResponse } from './types'
import { api } from './client'

export interface SearchParams {
  q: string
  item_type?: 'file' | 'folder'
  mime_type?: string
  page?: number
  page_size?: number
  signal?: AbortSignal
}

export interface SemanticSearchParams {
  q: string
  limit?: number
  signal?: AbortSignal
}

export const searchApi = {
  search: ({ signal, ...params }: SearchParams) =>
    api.get<Page<DriveItemResponse>>('/search', { params, signal }),
  semanticSearch: ({ q, limit, signal }: SemanticSearchParams) =>
    api.get<SemanticHitResponse[]>('/search/semantic', { params: { q, limit }, signal }),
  backfillEmbeddings: (batchSize = 50) =>
    api.post<BackfillResponse>('/search/embeddings/backfill', null, {
      params: { batch_size: batchSize },
    }),
}
