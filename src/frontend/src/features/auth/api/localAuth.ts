import { fetchApi } from '@/api/fetchApi'
import { type ApiUser } from './ApiUser'

export type LoginPayload = { email: string; password: string }
export type SignupPayload = LoginPayload & { full_name?: string }

/**
 * Seeds the csrftoken cookie. Call once before any local-auth POST.
 *
 * The OIDC flow normally sets this cookie as a side-effect of /authenticate/,
 * but users hitting /login directly have no cookie yet — without one, Django
 * would 403 the POST.
 */
export const fetchCsrf = () =>
  fetchApi<{ csrfToken: string }>('/auth/csrf/', { method: 'GET' })

export const apiLogin = (payload: LoginPayload) =>
  fetchApi<ApiUser>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const apiSignup = (payload: SignupPayload) =>
  fetchApi<ApiUser>('/auth/signup/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const apiLogout = () =>
  fetchApi<void>('/auth/logout/', { method: 'POST' })
