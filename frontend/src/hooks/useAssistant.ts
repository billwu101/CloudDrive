import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { assistantApi } from '@/api/assistantApi'
import type { AssistantSaveWorkflowRequest, AssistantSkillUpdateRequest } from '@/api/types'
import type { AssistantChatRequest } from '@/api/types'

export const assistantKeys = {
  all: ['assistant'] as const,
  skills: (status: string) => [...assistantKeys.all, 'skills', status] as const,
  savedWorkflows: () => [...assistantKeys.all, 'saved-workflows'] as const,
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

export function useUpdateAssistantSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ skillId, body }: { skillId: string; body: AssistantSkillUpdateRequest }) =>
      assistantApi.updateSkill(skillId, body).then((response) => response.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: assistantKeys.all })
    },
  })
}

export function useDeleteAssistantSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (skillId: string) => assistantApi.deleteSkill(skillId).then((response) => response.data),
    onSuccess: () => {
      // Removing a skill also drops its right-click action from the drive menu.
      void queryClient.invalidateQueries({ queryKey: assistantKeys.all })
    },
  })
}

export function useExecuteAssistantSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ skillId, itemId }: { skillId: string; itemId: string }) =>
      assistantApi.executeSkill(skillId, { item_id: itemId }).then((response) => response.data),
    onSuccess: () => {
      // A generated skill (e.g. a 7zip extractor) writes new items into the drive.
      void queryClient.invalidateQueries({ queryKey: ['drive'] })
    },
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

export function useSavedWorkflows() {
  return useQuery({
    queryKey: assistantKeys.savedWorkflows(),
    queryFn: () => assistantApi.listSavedWorkflows().then((response) => response.data),
  })
}

export function useSaveWorkflow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AssistantSaveWorkflowRequest) =>
      assistantApi.saveWorkflow(body).then((response) => response.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: assistantKeys.savedWorkflows() })
    },
  })
}

export function useRerunWorkflow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (workflowId: string) =>
      assistantApi.rerunWorkflow(workflowId).then((response) => response.data),
    onSuccess: () => {
      // A re-run workflow may have changed drive contents.
      void queryClient.invalidateQueries({ queryKey: ['drive'] })
    },
  })
}
