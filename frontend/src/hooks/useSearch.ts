import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { searchApi } from '@/api/searchApi'

export const searchKeys = {
  results: (q: string, itemType?: string, mimeType?: string, page?: number) =>
    ['search', q, itemType, mimeType, page] as const,
}

export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setDebounced(value), delayMs)
    return () => { if (timer.current) clearTimeout(timer.current) }
  }, [value, delayMs])

  return debounced
}

export interface SearchFilters {
  itemType?: 'FILE' | 'FOLDER'
  mimeType?: string
}

export function useSearchItems(
  query: string,
  filters: SearchFilters = {},
  page = 1,
  pageSize = 20,
) {
  const trimmed = query.trim()
  return useQuery({
    queryKey: searchKeys.results(trimmed, filters.itemType, filters.mimeType, page),
    queryFn: ({ signal }) =>
      searchApi
        .search({
          q: trimmed,
          item_type: filters.itemType === 'FILE' ? 'file' : filters.itemType === 'FOLDER' ? 'folder' : undefined,
          mime_type: filters.mimeType,
          page,
          page_size: pageSize,
          signal,
        })
        .then((r) => r.data),
    enabled: trimmed.length > 0,
    staleTime: 10_000,
  })
}
