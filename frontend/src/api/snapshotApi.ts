import type {
  RestoreRequest,
  RestoreResponse,
  SnapshotEntryResponse,
  SnapshotResponse,
} from './types'
import { api } from './client'

export const snapshotApi = {
  list: () => api.get<SnapshotResponse[]>('/snapshots'),
  create: (label = '') => api.post<SnapshotResponse>('/snapshots', { label }),
  items: (snapshotId: string, parentId?: string) =>
    api.get<SnapshotEntryResponse[]>(`/snapshots/${snapshotId}/items`, {
      params: parentId ? { parent_id: parentId } : undefined,
    }),
  restore: (snapshotId: string, body: RestoreRequest) =>
    api.post<RestoreResponse>(`/snapshots/${snapshotId}/restore`, body),
}
