import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { previewApi } from '@/api/previewApi'

export const previewKeys = {
  info: (itemId: string) => ['preview', 'info', itemId] as const,
}

export function usePreviewInfo(itemId: string | null) {
  return useQuery({
    queryKey: previewKeys.info(itemId ?? ''),
    queryFn: ({ signal }) => previewApi.getInfo(itemId!, signal).then((r) => r.data),
    enabled: !!itemId,
    staleTime: 60_000,
  })
}

/**
 * Fetch preview content (with auth) as an object URL usable by `<img>`,
 * `<iframe>`, `<video>` etc. `converted` requests the PDF-rendered version for
 * Office documents. Revokes the object URL on change/unmount.
 */
export function usePreviewBlobUrl(itemId: string | null, converted: boolean) {
  const [url, setUrl] = useState<string | null>(null)
  const [isError, setIsError] = useState(false)

  useEffect(() => {
    if (!itemId) return
    let objectUrl: string | null = null
    let cancelled = false
    previewApi
      .getContentBlob(itemId, { converted })
      .then((r) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(r.data)
        setUrl(objectUrl)
        setIsError(false)
      })
      .catch(() => {
        if (!cancelled) setIsError(true)
      })
    // Reset (and revoke) on itemId/converted change or unmount — done in cleanup
    // rather than synchronously in the effect body so a stale preview is cleared
    // before the next one loads without a cascading synchronous re-render.
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      setUrl(null)
      setIsError(false)
    }
  }, [itemId, converted])

  return { url, isError }
}
