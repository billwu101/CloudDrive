import type {
  AssistantChatRequest,
  AssistantChatResponse,
  AssistantSavedWorkflowResponse,
  AssistantSaveWorkflowRequest,
  AssistantSkillApproveResponse,
  AssistantSkillExecuteRequest,
  AssistantSkillExecuteResponse,
  AssistantSkillResponse,
  AssistantSkillUpdateRequest,
  AssistantWorkflowConfirmResponse,
} from './types'
import { api } from './client'

export const assistantApi = {
  chat: (body: AssistantChatRequest) =>
    api.post<AssistantChatResponse>('/assistant/chat', body),
  confirmWorkflow: (workflowId: string) =>
    api.post<AssistantWorkflowConfirmResponse>(`/assistant/workflows/${workflowId}/confirm`),
  cancelWorkflow: (workflowId: string) =>
    api.post<AssistantWorkflowConfirmResponse>(`/assistant/workflows/${workflowId}/cancel`),
  saveWorkflow: (body: AssistantSaveWorkflowRequest) =>
    api.post<AssistantSavedWorkflowResponse>('/assistant/workflows/save', body),
  listSavedWorkflows: () =>
    api.get<AssistantSavedWorkflowResponse[]>('/assistant/workflows/saved'),
  rerunWorkflow: (workflowId: string) =>
    api.post<AssistantWorkflowConfirmResponse>(`/assistant/workflows/saved/${workflowId}/rerun`),
  listSkills: (status = 'installed') =>
    api.get<AssistantSkillResponse[]>('/assistant/skills', { params: { status } }),
  approveSkill: (skillId: string) =>
    api.post<AssistantSkillApproveResponse>(`/assistant/skills/${skillId}/approve`),
  updateSkill: (skillId: string, body: AssistantSkillUpdateRequest) =>
    api.patch<AssistantSkillResponse>(`/assistant/skills/${skillId}`, body),
  deleteSkill: (skillId: string) => api.delete<void>(`/assistant/skills/${skillId}`),
  executeSkill: (skillId: string, body: AssistantSkillExecuteRequest) =>
    api.post<AssistantSkillExecuteResponse>(`/assistant/skills/${skillId}/execute`, body),
}
