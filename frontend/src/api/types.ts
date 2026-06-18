export interface TokenPairResponse {
  access_token: string
  token_type: string
}

export interface CurrentUserResponse {
  id: string
  email: string
  username: string
  avatar_url: string | null
  quota_bytes: number
  used_bytes: number
  is_active: boolean
  is_admin: boolean
  must_change_password: boolean
  created_at: string
}

export interface QuotaResponse {
  quota_bytes: number
  used_bytes: number
  available_bytes: number
  used_percent: number
}

export interface DriveItemResponse {
  id: string
  owner_id: string
  parent_id: string | null
  item_type: 'FILE' | 'FOLDER'
  name: string
  mime_type: string | null
  extension: string | null
  size_bytes: number
  is_starred: boolean
  is_deleted: boolean
  deleted_at: string | null
  created_by: string
  updated_by: string | null
  created_at: string
  updated_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface FileVersionResponse {
  id: string
  file_id: string
  version_no: number
  size_bytes: number
  checksum_sha256: string | null
  created_by: string
  created_at: string
}

export interface ShareResponse {
  id: string
  item_id: string
  owner_id: string
  target_user_id: string
  permission: string
  created_at: string
  updated_at: string
}

export interface ShareLinkResponse {
  id: string
  item_id: string
  token: string | null
  permission: string
  expires_at: string | null
  is_active: boolean
  created_by: string
  created_at: string
}

export interface PreviewInfoResponse {
  item_id: string
  preview_type: 'image' | 'pdf' | 'text' | 'video' | 'audio' | 'unsupported'
  mime_type: string | null
  size_bytes: number
  filename: string
}

export interface AssistantToolCall {
  name: string
  arguments: Record<string, unknown>
}

export interface AssistantToolResult {
  name: string
  ok: boolean
  output?: unknown
  error?: string | null
}

export interface AssistantSkillContextMenuAction {
  label: string
  handler: string
  item_types: string[]
}

export interface AssistantSkillManifest {
  name: string
  description: string
  version: string
  ui: {
    context_menu: AssistantSkillContextMenuAction[]
  }
}

export interface AssistantSkillResponse {
  id: string
  name: string
  description: string
  manifest: AssistantSkillManifest
  code: string
  status: 'pending' | 'installed' | string
  created_at: string
  updated_at: string
}

export interface AssistantSkillApproveResponse {
  skill: AssistantSkillResponse
  message: string
}

export interface AssistantSkillUpdateRequest {
  description?: string
  code?: string
}

export interface AssistantSkillExecuteRequest {
  item_id: string
}

export interface AssistantSkillExecuteResponse {
  skill_id: string
  skill_name: string
  item_id: string
  message: string
  output: Record<string, unknown>
}

export interface AssistantChatRequest {
  message: string
  session_id?: string
}

export interface WorkflowStep {
  index: number
  skill: string
  arguments: Record<string, unknown>
  depends_on: number[]
  permission_tier: string
  requires_approval: boolean
}

export interface WorkflowStepResult {
  index: number
  skill: string
  ok: boolean
  output?: unknown
  error?: string | null
}

export interface WorkflowPlanView {
  workflow_id: string | null
  status: 'auto_executed' | 'pending_approval'
  steps: WorkflowStep[]
}

export interface AssistantChatResponse {
  session_id: string
  message: string
  tool_calls: AssistantToolCall[]
  tool_results: AssistantToolResult[]
  plan?: WorkflowPlanView | null
  results: WorkflowStepResult[]
  skill_proposal?: AssistantSkillResponse | null
}

export interface AssistantWorkflowConfirmResponse {
  workflow_id: string
  status: 'executed' | 'cancelled'
  message: string
  results: WorkflowStepResult[]
}

export interface AssistantPlannedStep {
  skill: string
  arguments: Record<string, unknown>
  depends_on?: number[]
}

export interface AssistantSaveWorkflowRequest {
  name: string
  source_nl?: string
  steps: AssistantPlannedStep[]
}

export interface AssistantSavedWorkflowResponse {
  id: string
  name: string
  source_nl: string
  steps: WorkflowStep[]
  created_at: string
}

// ── Time Machine (snapshots) ──────────────────────────────────────────────
export interface SnapshotResponse {
  id: string
  trigger: 'scheduled' | 'manual' | 'assistant' | 'pre_restore' | string
  label: string
  item_count: number
  total_bytes: number
  pinned: boolean
  created_at: string
}

export interface SnapshotEntryResponse {
  item_id: string
  parent_item_id: string | null
  name: string
  item_type: 'FILE' | 'FOLDER' | string
  size_bytes: number
  checksum_sha256: string | null
}

export interface RestoreRequest {
  scope?: 'whole' | 'items'
  item_ids?: string[]
  subtree_mode?: 'keep_new' | 'exact_mirror'
}

export interface RestoreResponse {
  pre_restore_snapshot_id: string
  restored: number
  trashed: number
}

export interface SnapshotSettingsResponse {
  retention_n: number
  schedule_enabled: boolean
  schedule_interval_minutes: number
  quota_bytes: number | null
  effective_quota_bytes: number
  used_bytes: number
}

export interface UpdateSnapshotSettingsRequest {
  retention_n: number
  schedule_enabled: boolean
  schedule_interval_minutes: number
  quota_bytes: number | null
}
