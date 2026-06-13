import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { authApi } from '@/api/authApi'
import { useAuthStore } from '@/stores/authStore'

export const authKeys = {
  me: () => ['auth', 'me'] as const,
  quota: () => ['auth', 'quota'] as const,
}

export function useCurrentUserQuery() {
  const accessToken = useAuthStore((s) => s.accessToken)
  return useQuery({
    queryKey: authKeys.me(),
    queryFn: ({ signal }) => authApi.me(signal).then((r) => r.data),
    enabled: !!accessToken,
    staleTime: 5 * 60 * 1000,
  })
}

export function useQuotaQuery() {
  const accessToken = useAuthStore((s) => s.accessToken)
  return useQuery({
    queryKey: authKeys.quota(),
    queryFn: ({ signal }) => authApi.quota(signal).then((r) => r.data),
    enabled: !!accessToken,
    staleTime: 30_000,
  })
}

export function useLoginMutation() {
  const queryClient = useQueryClient()
  const { setToken, setUser } = useAuthStore()
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      authApi.login(email, password).then((r) => r.data),
    onSuccess: async (data) => {
      setToken(data.access_token)
      const me = await authApi.me().then((r) => r.data)
      setUser(me)
      await queryClient.invalidateQueries({ queryKey: authKeys.me() })
    },
  })
}

export function useRegisterMutation() {
  const { setToken } = useAuthStore()
  return useMutation({
    mutationFn: ({
      email,
      username,
      password,
    }: {
      email: string
      username: string
      password: string
    }) => authApi.register(email, username, password).then((r) => r.data),
    onSuccess: (data) => {
      setToken(data.access_token)
    },
  })
}

export function useLogoutMutation() {
  const queryClient = useQueryClient()
  const clearAuth = useAuthStore((s) => s.clearAuth)
  return useMutation({
    mutationFn: () => authApi.logout().then((r) => r.data),
    onSettled: () => {
      clearAuth()
      queryClient.clear()
    },
  })
}
