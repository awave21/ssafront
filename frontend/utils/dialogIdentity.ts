import type { DialogUserInfo } from '~/types/dialogs'

type DialogIdentityInput = {
  id?: string | null
  platform?: string | null
  title?: string | null
  user_info?: DialogUserInfo | Record<string, unknown> | null
}

const INTEGRATION_LABEL_BY_PLATFORM: Record<string, string> = {
  telegram: 'Telegram бот',
  telegram_phone: 'Telegram номер',
  whatsapp: 'WhatsApp',
  max: 'MAX'
}

const TELEGRAM_PLATFORMS = new Set(['telegram', 'telegram_phone'])
const PHONE_IDENTITY_PLATFORMS = new Set(['whatsapp', 'max'])

const asTrimmedString = (value: unknown): string => {
  return typeof value === 'string' ? value.trim() : ''
}

const resolvePlatformFromDialogId = (dialogId: unknown): string | undefined => {
  const id = asTrimmedString(dialogId)
  if (!id || !id.includes(':')) return undefined
  const [prefix] = id.split(':', 1)
  return prefix || undefined
}

const resolveDialogPeerId = (dialogId: unknown): string => {
  const id = asTrimmedString(dialogId)
  return id.replace(/^(telegram|telegram_phone|whatsapp|max):/, '')
}

const normalizePhoneCandidate = (value: unknown): string | null => {
  const raw = asTrimmedString(value)
  if (!raw) return null
  const peerPart = raw.includes('@') ? raw.split('@', 1)[0] : raw
  const digits = peerPart.replace(/\D+/g, '')
  if (!digits) return null
  if (digits.length < 10 || digits.length > 15) return null
  return `+${digits}`
}

const resolveWhatsAppPhone = (dialog: DialogIdentityInput): string | null => {
  const userInfo = dialog.user_info as (DialogUserInfo & Record<string, unknown>) | undefined
  const candidates: unknown[] = [
    userInfo?.contact_phone,
    userInfo?.phone,
    userInfo?.platform_id,
    userInfo?.whatsapp_id,
    userInfo?.whataspp_id,
    resolveDialogPeerId(dialog.id)
  ]
  for (const candidate of candidates) {
    const normalizedPhone = normalizePhoneCandidate(candidate)
    if (normalizedPhone) return normalizedPhone
  }
  return null
}

export const resolveDialogPlatform = (dialog: DialogIdentityInput): string | undefined => {
  const explicitPlatform = asTrimmedString(dialog.platform)
  if (explicitPlatform) return explicitPlatform

  const userInfoPlatform = asTrimmedString(
    (dialog.user_info as DialogUserInfo | undefined)?.platform
  )
  if (userInfoPlatform) return userInfoPlatform

  return resolvePlatformFromDialogId(dialog.id)
}

export const isTelegramDialog = (dialog: DialogIdentityInput): boolean => {
  const platform = resolveDialogPlatform(dialog)
  return platform ? TELEGRAM_PLATFORMS.has(platform) : false
}

export const resolveIntegrationChannelLabel = (dialog: DialogIdentityInput): string => {
  const explicitLabel = asTrimmedString(
    (dialog.user_info as DialogUserInfo | undefined)?.integration_channel_label
  )
  if (explicitLabel) return explicitLabel

  const platform = resolveDialogPlatform(dialog)
  if (!platform) return ''
  return INTEGRATION_LABEL_BY_PLATFORM[platform] || ''
}

export const resolveDialogUserTitle = (dialog: DialogIdentityInput): string | null => {
  const userInfo = dialog.user_info as DialogUserInfo | undefined
  const firstName = asTrimmedString(userInfo?.first_name)
  const lastName = asTrimmedString(userInfo?.last_name)
  if (firstName || lastName) {
    return [firstName, lastName].filter(Boolean).join(' ')
  }

  const username = asTrimmedString(userInfo?.username)
  if (username) {
    return username.startsWith('@') ? username : `@${username}`
  }

  if (isTelegramDialog(dialog) && dialog.id) {
    const peerId = resolveDialogPeerId(dialog.id)
    if (peerId) return `Telegram #${peerId}`
  }

  return null
}

export const resolveDialogSecondaryIdentity = (dialog: DialogIdentityInput): string | null => {
  const userInfo = dialog.user_info as DialogUserInfo | undefined
  const username = asTrimmedString(userInfo?.username)
  if (username) {
    return username.startsWith('@') ? username : `@${username}`
  }

  const platform = resolveDialogPlatform(dialog)
  if (platform && PHONE_IDENTITY_PLATFORMS.has(platform)) {
    return resolveWhatsAppPhone(dialog)
  }

  return null
}

export const normalizeDialogUserInfo = (
  dialog: DialogIdentityInput,
  rawUserInfo: DialogUserInfo | Record<string, unknown> | null | undefined
): DialogUserInfo | undefined => {
  if (!rawUserInfo || typeof rawUserInfo !== 'object') return undefined

  const userInfo = { ...(rawUserInfo as DialogUserInfo) }
  const platform = asTrimmedString(userInfo.platform) || resolveDialogPlatform(dialog)
  const channelLabel =
    asTrimmedString(userInfo.integration_channel_label) ||
    (platform ? INTEGRATION_LABEL_BY_PLATFORM[platform] : '')

  if (platform) userInfo.platform = platform
  if (channelLabel) userInfo.integration_channel_label = channelLabel

  return userInfo
}
