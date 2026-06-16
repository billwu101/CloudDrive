import type { AssistantChatRequest, AssistantChatResponse } from './types'
import { api } from './client'

export const assistantApi = {
  chat: (body: AssistantChatRequest) =>
    api.post<AssistantChatResponse>('/assistant/chat', body),
}
