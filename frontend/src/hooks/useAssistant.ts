import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { assistantApi } from '@/api/assistantApi'
import type { AssistantChatRequest } from '@/api/types'

export const assistantKeys = {
  all: ['assistant'] as const,
  skills: (status: string) => [...assistantKeys.all, 'skills', status] as const,
}

export function useAssistantChatMutation() {
  return useMutation({
    mutationFn: (body: AssistantChatRequest) =>
      assistantApi.chat(body).then((response) => response.data),
  })
}

export function useAssistantSkills(status = 'installed') {
  return useQuery({
    queryKey: assistantKeys.skills(status),
    queryFn: () => assistantApi.listSkills(status).then((response) => response.data),
  })
}

export function useApproveAssistantSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (skillId: string) =>
      assistantApi.approveSkill(skillId).then((response) => response.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: assistantKeys.all })
    },
  })
}

export function useExecuteAssistantSkill() {
  return useMutation({
    mutationFn: ({ skillId, itemId }: { skillId: string; itemId: string }) =>
      assistantApi.executeSkill(skillId, { item_id: itemId }).then((response) => response.data),
  })
}

export function useConfirmWorkflow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (workflowId: string) =>
      assistantApi.confirmWorkflow(workflowId).then((response) => response.data),
    onSuccess: () => {
      // A confirmed workflow may have changed drive contents.
      void queryClient.invalidateQueries({ queryKey: ['drive'] })
    },
  })
}

export function useCancelWorkflow() {
  return useMutation({
    mutationFn: (workflowId: string) =>
      assistantApi.cancelWorkflow(workflowId).then((response) => response.data),
  })
}
