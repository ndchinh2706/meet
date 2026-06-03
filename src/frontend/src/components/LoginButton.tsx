import { LinkButton } from '@/primitives'
import { useTranslation } from 'react-i18next'
import { useConfig } from '@/api/useConfig'
import { ProConnectButton } from './ProConnectButton'

type LoginButtonProps = {
  proConnectHint?: boolean // Hide hint in layouts where space doesn't allow it.
}

const localLoginUrl = () => {
  if (typeof window === 'undefined') return '/login'
  return `/login?returnTo=${encodeURIComponent(window.location.pathname + window.location.search)}`
}

export const LoginButton = ({ proConnectHint = true }: LoginButtonProps) => {
  const { t } = useTranslation('global', { keyPrefix: 'login' })
  const { data } = useConfig()

  if (data?.use_proconnect_button) {
    return <ProConnectButton hint={proConnectHint} />
  }

  return (
    <LinkButton href={localLoginUrl()} data-attr="login" variant="primary">
      {t('buttonLabel')}
    </LinkButton>
  )
}
