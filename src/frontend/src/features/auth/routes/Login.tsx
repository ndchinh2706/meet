import { FormEvent, useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { navigate } from 'wouter/use-browser-location'
import { css } from '@/styled-system/css'
import { Button, H, P, Text } from '@/primitives'
import { keys } from '@/api/queryKeys'
import { ApiError } from '@/api/ApiError'
import {
  apiLogin,
  apiSignup,
  fetchCsrf,
  type LoginPayload,
  type SignupPayload,
} from '../api/localAuth'

type Mode = 'login' | 'signup'

const getReturnTo = () => {
  if (typeof window === 'undefined') return '/'
  const params = new URLSearchParams(window.location.search)
  const raw = params.get('returnTo')
  if (!raw) return '/'
  try {
    const url = new URL(raw, window.location.origin)
    return url.origin === window.location.origin
      ? url.pathname + url.search
      : '/'
  } catch {
    return '/'
  }
}

const extractApiMessage = (err: unknown): string => {
  if (!(err instanceof ApiError))
    return 'Something went wrong. Please try again.'
  const body = err.body as Record<string, unknown> | undefined
  if (!body) return 'Request failed.'
  if (typeof body.detail === 'string') return body.detail
  for (const value of Object.values(body)) {
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
    if (typeof value === 'string') return value
  }
  return 'Request failed.'
}

const labelClass = css({
  display: 'block',
  fontSize: '0.875rem',
  fontWeight: 500,
  marginBottom: '0.375rem',
  color: 'neutral.700',
})

const inputClass = css({
  width: '100%',
  padding: '0.625rem 0.75rem',
  border: '1px solid',
  borderColor: 'control.border',
  borderRadius: '4px',
  fontSize: '0.95rem',
  backgroundColor: 'white',
  transition: 'border-color 150ms, box-shadow 150ms',
  _focus: {
    outline: 'none',
    borderColor: 'primary.500',
    boxShadow: '0 0 0 3px rgba(0,108,255,0.15)',
  },
  _disabled: {
    backgroundColor: 'neutral.50',
    cursor: 'not-allowed',
  },
})

const fieldGroupClass = css({ marginBottom: '1rem' })

export default function Login() {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<Mode>('login')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  useEffect(() => {
    fetchCsrf().catch(() => {
      /* surface as form error if the POST really cares */
    })
  }, [])

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'login') {
        await apiLogin({ email, password } as LoginPayload)
      } else {
        await apiSignup({
          email,
          password,
          full_name: fullName || undefined,
        } as SignupPayload)
      }
      await queryClient.invalidateQueries({ queryKey: [keys.user] })
      navigate(getReturnTo(), { replace: true })
    } catch (err) {
      setError(extractApiMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const toggleMode = () => {
    setError(null)
    setMode(mode === 'login' ? 'signup' : 'login')
  }

  return (
    <div
      className={css({
        minHeight: '100vh',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'neutral.50',
        padding: '1rem',
      })}
    >
      <div
        className={css({
          width: '100%',
          maxWidth: '440px',
          backgroundColor: 'white',
          borderRadius: '8px',
          boxShadow:
            '0 1px 3px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.08)',
          padding: { base: '1.75rem', md: '2.5rem' },
        })}
      >
        <H
          lvl={1}
          className={css({
            fontSize: '1.5rem',
            fontWeight: 600,
            marginBottom: '0.25rem',
            textAlign: 'center',
          })}
        >
          {mode === 'login' ? 'Sign in to Meet' : 'Create your Meet account'}
        </H>
        <P
          className={css({
            color: 'neutral.600',
            textAlign: 'center',
            marginBottom: '1.5rem',
            fontSize: '0.9rem',
          })}
        >
          {mode === 'login'
            ? 'Enter your credentials to continue'
            : 'Fill in the form to get started'}
        </P>

        {error && (
          <div
            role="alert"
            className={css({
              padding: '0.75rem 1rem',
              marginBottom: '1rem',
              borderRadius: '4px',
              backgroundColor: 'danger.100',
              color: 'danger.700',
              border: '1px solid',
              borderColor: 'danger.200',
              fontSize: '0.875rem',
            })}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          {mode === 'signup' && (
            <div className={fieldGroupClass}>
              <label htmlFor="full_name" className={labelClass}>
                Full name
              </label>
              <input
                id="full_name"
                name="full_name"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                disabled={submitting}
                className={inputClass}
              />
            </div>
          )}

          <div className={fieldGroupClass}>
            <label htmlFor="email" className={labelClass}>
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              // eslint-disable-next-line jsx-a11y/no-autofocus
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
              className={inputClass}
            />
          </div>

          <div className={fieldGroupClass}>
            <label htmlFor="password" className={labelClass}>
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              minLength={mode === 'signup' ? 8 : undefined}
              autoComplete={
                mode === 'login' ? 'current-password' : 'new-password'
              }
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
              className={inputClass}
            />
            {mode === 'signup' && (
              <span
                className={css({
                  display: 'block',
                  marginTop: '0.375rem',
                  fontSize: '0.75rem',
                  color: 'neutral.600',
                })}
              >
                At least 8 characters
              </span>
            )}
          </div>

          <Button
            type="submit"
            variant="primary"
            fullWidth
            isDisabled={submitting}
            data-attr={`local-auth-${mode}-submit`}
          >
            {submitting
              ? mode === 'login'
                ? 'Signing in…'
                : 'Creating account…'
              : mode === 'login'
                ? 'Sign in'
                : 'Sign up'}
          </Button>
        </form>

        <div
          className={css({
            marginTop: '1.5rem',
            paddingTop: '1.25rem',
            borderTop: '1px solid',
            borderColor: 'neutral.200',
            textAlign: 'center',
          })}
        >
          <Text variant="sm" className={css({ color: 'neutral.600' })}>
            {mode === 'login'
              ? "Don't have an account? "
              : 'Already have an account? '}
          </Text>
          <button
            type="button"
            onClick={toggleMode}
            disabled={submitting}
            className={css({
              background: 'none',
              border: 'none',
              padding: 0,
              color: 'primary.600',
              fontWeight: 600,
              cursor: 'pointer',
              fontSize: '0.875rem',
              _hover: { textDecoration: 'underline' },
              _disabled: { opacity: 0.5, cursor: 'not-allowed' },
            })}
          >
            {mode === 'login' ? 'Create one' : 'Sign in'}
          </button>
        </div>
      </div>
    </div>
  )
}
