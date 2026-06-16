import { useMutation } from '@tanstack/react-query'

import { assistantApi } from '@/api/assistantApi'
import type { AssistantChatRequest } from '@/api/types'

export function useAssistantChatMutation() {
  return useMutation({
    mutationFn: (body: AssistantChatRequest) =>
      assistantApi.chat(body).then((response) => response.data),
  })
}
