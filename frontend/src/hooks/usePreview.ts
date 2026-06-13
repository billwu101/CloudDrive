import { useQuery } from '@tanstack/react-query'

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
