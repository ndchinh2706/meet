import { useTranslation } from 'react-i18next'
import { H, P } from '@/primitives'
import { TabPanel, type TabPanelProps } from '@/primitives/Tabs'
import { useUser } from '@/features/auth/api/useUser'
import { IntegrationsContent } from './IntegrationsContent'

export type IntegrationsTabProps = Pick<TabPanelProps, 'id'>

export const IntegrationsTab = ({ id }: IntegrationsTabProps) => {
  const { t } = useTranslation('settings', { keyPrefix: 'integrations' })
  const { isLoggedIn } = useUser()

  return (
    <TabPanel padding={'md'} flex id={id}>
      {isLoggedIn ? (
        <IntegrationsContent />
      ) : (
        <>
          <H lvl={2}>{t('heading')}</H>
          <P>{t('loginRequired')}</P>
        </>
      )}
    </TabPanel>
  )
}
