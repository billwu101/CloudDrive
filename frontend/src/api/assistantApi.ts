import type {
  AssistantChatRequest,
  AssistantChatResponse,
  AssistantSkillApproveResponse,
  AssistantSkillExecuteRequest,
  AssistantSkillExecuteResponse,
  AssistantSkillResponse,
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
  listSkills: (status = 'installed') =>
    api.get<AssistantSkillResponse[]>('/assistant/skills', { params: { status } }),
  approveSkill: (skillId: string) =>
    api.post<AssistantSkillApproveResponse>(`/assistant/skills/${skillId}/approve`),
  executeSkill: (skillId: string, body: AssistantSkillExecuteRequest) =>
    api.post<AssistantSkillExecuteResponse>(`/assistant/skills/${skillId}/execute`, body),
}
