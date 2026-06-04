import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { RiQuestionLine } from '@remixicon/react'
import {
  Button as RACButton,
  Dialog as RACDialog,
  DialogTrigger,
  OverlayArrow,
  Popover as RACPopover,
} from 'react-aria-components'
import { Button } from '@/primitives'
import { useConfig } from '@/api/useConfig'
import { css, cx } from '@/styled-system/css'
import { Box, HStack } from '@/styled-system/jsx'
import {
  useCreatePat,
  usePats,
  type NewPersonalAccessToken,
} from '../api/pats'

const sectionStyle = css({
  display: 'flex',
  flexDirection: 'column',
  gap: '0.75rem',
})

const headingRowStyle = css({
  display: 'flex',
  alignItems: 'center',
  gap: '0.35rem',
})

const headingStyle = css({
  fontSize: '1.05rem',
  fontWeight: 600,
  margin: 0,
  lineHeight: 1.2,
})

const tokenBoxBase = css({
  flex: 1,
  minWidth: 0,
  fontFamily: 'monospace',
  fontSize: '0.85rem',
  padding: '0.5rem 0.75rem',
  border: '1px solid',
  borderColor: 'control.border',
  borderRadius: '4px',
  background: 'white',
  height: '2.5rem',
  display: 'flex',
  alignItems: 'center',
  overflowX: 'auto',
  whiteSpace: 'nowrap',
  userSelect: 'all',
  scrollbarWidth: 'thin',
})

const tokenBoxMuted = css({
  background: '#fafafa',
  color: '#666',
})

const helperStyle = css({
  fontSize: '0.78rem',
  color: '#666',
  margin: 0,
  marginTop: '-0.15rem',
})

const helpButtonStyle = css({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '1.25rem',
  height: '1.25rem',
  padding: 0,
  border: 'none',
  background: 'transparent',
  color: '#9aa0a6',
  cursor: 'help',
  borderRadius: '999px',
  outline: 'none',
  '&[data-hovered]': { color: '#3c4043', background: '#f1f3f4' },
  '&[data-focus-visible]': {
    boxShadow: '0 0 0 2px token(colors.primary.600)',
  },
})

const popoverStyle = css({
  background: 'white',
  border: '1px solid',
  borderColor: 'control.border',
  borderRadius: '6px',
  padding: '0.5rem',
  boxShadow: '0 8px 24px rgba(0,0,0,0.14)',
  maxWidth: '34rem',
  outline: 'none',
})

const popoverUrlStyle = css({
  fontFamily: 'monospace',
  fontSize: '0.8rem',
  padding: '0.4rem 0.5rem',
  background: '#f5f6f7',
  borderRadius: '4px',
  wordBreak: 'break-all',
  userSelect: 'all',
  marginRight: '0.5rem',
})

const McpUrlPopover = ({ url }: { url: string }) => {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const id = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(id)
  }, [copied])

  const handleCopy = async () => {
    if (!url) return
    await navigator.clipboard.writeText(url)
    setCopied(true)
  }

  return (
    <DialogTrigger>
      <RACButton
        aria-label="MCP server URL"
        className={helpButtonStyle}
        excludeFromTabOrder
      >
        <RiQuestionLine size={14} />
      </RACButton>
      <RACPopover placement="top" offset={6} className={popoverStyle}>
        <OverlayArrow />
        <RACDialog
          className={css({ outline: 'none' })}
          aria-label="MCP server URL"
        >
          <HStack gap={'0.4rem'} alignItems={'center'}>
            <span className={popoverUrlStyle}>{url || '—'}</span>
            <Button
              variant="primary"
              onPress={handleCopy}
              isDisabled={!url}
            >
              {copied ? '✓' : 'Copy'}
            </Button>
          </HStack>
        </RACDialog>
      </RACPopover>
    </DialogTrigger>
  )
}

const useCopyButton = () => {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const id = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(id)
  }, [copied])
  return {
    copied,
    copy: async (value: string) => {
      await navigator.clipboard.writeText(value)
      setCopied(true)
    },
  }
}

export const IntegrationsContent = () => {
  const { t } = useTranslation('settings', { keyPrefix: 'integrations' })
  const config = useConfig()
  const pats = usePats()
  const createPat = useCreatePat()
  const { copied, copy } = useCopyButton()

  const [createdToken, setCreatedToken] =
    useState<NewPersonalAccessToken | null>(null)

  const mcpUrl = config.data?.mcp?.url || ''
  const existing = pats.data?.[0]

  const handleCreate = async () => {
    try {
      const token = await createPat.mutateAsync('')
      setCreatedToken(token)
    } catch (e) {
      console.error('Failed to create PAT', e)
    }
  }

  const Heading = (
    <div className={headingRowStyle}>
      <h2 className={headingStyle}>{t('heading')}</h2>
      <McpUrlPopover url={mcpUrl} />
    </div>
  )

  // STATE 2 — Just created: show full token + Copy
  if (createdToken) {
    return (
      <Box className={sectionStyle}>
        {Heading}
        <HStack gap={'0.5rem'} alignItems={'center'}>
          <span className={tokenBoxBase}>{createdToken.token}</span>
          <Button
            variant="primary"
            onPress={() => copy(createdToken.token)}
          >
            {copied ? t('copied') : t('copy')}
          </Button>
        </HStack>
        <p className={helperStyle}>{t('saveNow')}</p>
      </Box>
    )
  }

  // STATE 3 — Existing token (prefix only) + Recreate
  if (existing) {
    return (
      <Box className={sectionStyle}>
        {Heading}
        <HStack gap={'0.5rem'} alignItems={'center'}>
          <span className={cx(tokenBoxBase, tokenBoxMuted)}>
            {existing.token_prefix}…
          </span>
          <Button
            variant="secondary"
            onPress={handleCreate}
            isDisabled={createPat.isPending}
          >
            {createPat.isPending ? t('creating') : t('recreate')}
          </Button>
        </HStack>
        <p className={helperStyle}>{t('existsHelper')}</p>
      </Box>
    )
  }

  // STATE 1 — Empty: just the Create button
  return (
    <Box className={sectionStyle}>
      {Heading}
      <div>
        <Button
          variant="primary"
          onPress={handleCreate}
          isDisabled={createPat.isPending || pats.isLoading}
        >
          {createPat.isPending ? t('creating') : t('createButton')}
        </Button>
      </div>
    </Box>
  )
}
