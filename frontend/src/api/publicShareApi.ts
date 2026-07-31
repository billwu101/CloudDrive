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

// ── Guest writes — editor links only (proposal §33) ─────────────────────────
// The server re-checks the permission on every call; these wrappers exist so
// the guest page has something to wire its UI to, not as the enforcement.

export function createSharedFolder(parentId: string, name: string): Promise<PublicItem> {
  return unwrap(
    publicClient.post<PublicItem>(
      '/public/folders',
      { parent_id: parentId, name },
      { headers: authHeaders() },
    ),
  )
}

export function renameSharedItem(itemId: string, name: string): Promise<PublicItem> {
  return unwrap(
    publicClient.patch<PublicItem>(
      `/public/items/${itemId}/name`,
      { name },
      { headers: authHeaders() },
    ),
  )
}

export function moveSharedItem(itemId: string, parentId: string): Promise<PublicItem> {
  return unwrap(
    publicClient.patch<PublicItem>(
      `/public/items/${itemId}/parent`,
      { parent_id: parentId },
      { headers: authHeaders() },
    ),
  )
}

export function trashSharedItem(itemId: string): Promise<void> {
  return unwrap(
    publicClient.post<void>(`/public/items/${itemId}/trash`, undefined, {
      headers: authHeaders(),
    }),
  )
}

export function uploadSharedFile(folderId: string, file: File): Promise<PublicItem> {
  const form = new FormData()
  form.append('file', file)
  return unwrap(
    publicClient.post<PublicItem>(`/public/items/${folderId}/upload`, form, {
      headers: authHeaders(),
    }),
  )
}

export function downloadSharedArchive(folderName: string): Promise<void> {
  return saveBlob('/public/archive', `${folderName}.zip`)
}

/** Zip just the items the guest selected (proposal §28.8.3). */
export async function downloadSharedSelection(itemIds: string[]): Promise<void> {
  const res = await publicClient.post<Blob>(
    '/public/archive',
    { item_ids: itemIds },
    { headers: authHeaders(), responseType: 'blob' },
  )
  const disposition = String(res.headers['content-disposition'] ?? '')
  const match = /filename\*=UTF-8''([^;]+)/.exec(disposition)
  const url = URL.createObjectURL(res.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = match?.[1] ? decodeURIComponent(match[1]) : 'download.zip'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

/** Preview bytes as an object URL, for the shared `PreviewDialog`. */
export async function fetchSharedPreviewBlob(itemId: string): Promise<string> {
  return fetchSharePreviewUrl(itemId)
}

export type { ApiError }
