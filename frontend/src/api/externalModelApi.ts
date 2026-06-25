import type { ConnectionCreate, ConnectionUpdate, ConnectionView } from './types'
import { api } from './client'

const BASE = '/users/me/model-connections'

export const modelConnectionApi = {
  list: () => api.get<ConnectionView[]>(BASE),
  create: (body: ConnectionCreate) => api.post<ConnectionView>(BASE, body),
  update: (id: string, body: ConnectionUpdate) => api.put<ConnectionView>(`${BASE}/${id}`, body),
  remove: (id: string) => api.delete(`${BASE}/${id}`),
}
