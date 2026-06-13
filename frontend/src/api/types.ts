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
