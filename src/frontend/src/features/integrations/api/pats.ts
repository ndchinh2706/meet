import { fetchApi } from '@/api/fetchApi'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

export interface PersonalAccessToken {
  id: string
  name: string
  token_prefix: string
  last_used_at: string | null
  expires_at: string | null
  is_active: boolean
  created_at: string
}

export interface NewPersonalAccessToken extends PersonalAccessToken {
  /** Raw token, returned exactly once at creation. Never readable again. */
  token: string
}

const PATS_KEY = ['pats'] as const

export const usePats = () => {
  return useQuery({
    queryKey: PATS_KEY,
    queryFn: () => fetchApi<PersonalAccessToken[]>('pats/'),
  })
}

export const useCreatePat = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) =>
      fetchApi<NewPersonalAccessToken>('pats/', {
        method: 'POST',
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: PATS_KEY }),
  })
}

export const useDeletePat = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      fetchApi(`pats/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: PATS_KEY }),
  })
}
