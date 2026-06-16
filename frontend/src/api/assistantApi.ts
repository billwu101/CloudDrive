import type {
  AssistantChatRequest,
  AssistantChatResponse,
  AssistantSkillApproveResponse,
  AssistantSkillExecuteRequest,
  AssistantSkillExecuteResponse,
  AssistantSkillResponse,
} from './types'
import { api } from './client'

export const assistantApi = {
  chat: (body: AssistantChatRequest) =>
    api.post<AssistantChatResponse>('/assistant/chat', body),
  listSkills: (status = 'installed') =>
    api.get<AssistantSkillResponse[]>('/assistant/skills', { params: { status } }),
  approveSkill: (skillId: string) =>
    api.post<AssistantSkillApproveResponse>(`/assistant/skills/${skillId}/approve`),
  executeSkill: (skillId: string, body: AssistantSkillExecuteRequest) =>
    api.post<AssistantSkillExecuteResponse>(`/assistant/skills/${skillId}/execute`, body),
}
