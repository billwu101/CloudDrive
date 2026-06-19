import type { ExternalCredentialUpsert, ExternalCredentialView } from './types'
import { api } from './client'

export const externalModelApi = {
  list: () => api.get<ExternalCredentialView[]>('/users/me/external-credentials'),
  upsert: (body: ExternalCredentialUpsert) =>
    api.put<ExternalCredentialView>('/users/me/external-credentials', body),
  remove: (provider: string) => api.delete(`/users/me/external-credentials/${provider}`),
}
