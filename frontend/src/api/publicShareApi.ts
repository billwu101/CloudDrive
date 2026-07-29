import axios from 'axios'

import { BASE_URL, type ApiError, toApiError } from './client'
import type { Page, PublicItem, PublicSession } from './types'

/**
 * Guest-side client for public share links (proposal §28).
 *
 * Deliberately a separate axios instance from `api`: this one must never send
 * the user's access token, and must never run the 401 -> refresh -> retry
 * interceptor. A guest has no account to refresh into, and a 401 here means
 * "the link needs a password", not "your session expired".
 */
const publicClient = axios.create({ baseURL: BASE_URL, adapter: 'fetch' })

/** The share access credential, held in memory only — never persisted. */
let credential: string | null = null

export function setShareCredential(token: string | null): void {
  credential = token
}

function authHeaders(): Record<string, string> {
  return credential ? { Authorization: `Bearer ${credential}` } : {}
}

async function unwrap<T>(call: Promise<{ data: T }>): Promise<T> {
  try {
    return (await call).data
  } catch (err) {
    throw toApiError(err)
  }
}

/**
 * Exchanges the link token (plus password, when the link has one) for a
 * short-lived credential. Called with no password first: links without a
 * password open straight away, and only a password-protected link answers
 * with SHARE_LINK_PASSWORD_REQUIRED.
 */
export async function openShareSession(
  token: string,
  password?: string,
): Promise<PublicSession> {
  const session = await unwrap(
    publicClient.post<PublicSession>(`/public/links/${encodeURIComponent(token)}/session`, {
      password: password ?? null,
    }),
  )
  setShareCredential(session.access_token)
  return session
}

export async function refreshShareSession(token: string): Promise<PublicSession> {
  const session = await unwrap(
    publicClient.post<PublicSession>(
      `/public/links/${encodeURIComponent(token)}/session/refresh`,
      {},
      { headers: authHeaders() },
    ),
  )
  setShareCredential(session.access_token)
  return session
}

export function listShareChildren(itemId: string, page = 1): Promise<Page<PublicItem>> {
  return unwrap(
    publicClient.get<Page<PublicItem>>(`/public/items/${itemId}/children`, {
      headers: authHeaders(),
      params: { page, page_size: 100 },
    }),
  )
}

export async function fetchSharePreviewUrl(itemId: string): Promise<string> {
  const blob = await unwrap(
    publicClient.get<Blob>(`/public/items/${itemId}/preview`, {
      headers: authHeaders(),
      responseType: 'blob',
    }),
  )
  return URL.createObjectURL(blob)
}

async function saveBlob(path: string, fallbackName: string): Promise<void> {
  const res = await publicClient.get<Blob>(path, {
    headers: authHeaders(),
    responseType: 'blob',
  })
  // A blob URL carries no filename, so the server's Content-Disposition is the
  // only thing that knows what to call the download.
  const disposition = String(res.headers['content-disposition'] ?? '')
  const match = /filename\*=UTF-8''([^;]+)/.exec(disposition)
  const name = match?.[1] ? decodeURIComponent(match[1]) : fallbackName

  const url = URL.createObjectURL(res.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export function downloadSharedItem(itemId: string, filename: string): Promise<void> {
  return saveBlob(`/public/items/${itemId}/download`, filename)
}

export function downloadSharedArchive(folderName: string): Promise<void> {
  return saveBlob('/public/archive', `${folderName}.zip`)
}

export type { ApiError }
