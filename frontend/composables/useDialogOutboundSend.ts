import { resolveDialogPlatform } from '~/utils/dialogIdentity'
import type { Dialog } from '~/types/dialogs'
import { useMessages } from './useMessages'

const PHONE_OPERATOR_PLATFORMS = new Set(['telegram_phone', 'whatsapp', 'max'])

type DialogOutboundSendParams = {
  agentId: string
  dialogId: string
  content: string
  dialog: Dialog | null | undefined
  isAgentEnabled: boolean
  isWsConnected?: boolean
  wsSendMessage?: (dialogId: string, content: string) => boolean
}

export const useDialogOutboundSend = () => {
  const {
    sendMessage,
    sendManagerMessage,
    createOptimisticMessage,
    markMessageFailed
  } = useMessages()

  const isPhoneOperatorDialog = (dialog: Dialog | null | undefined): boolean => {
    if (!dialog) return false
    const integrationType = typeof dialog.user_info?.integration_channel_type === 'string'
      ? dialog.user_info.integration_channel_type.toLowerCase()
      : ''
    if (integrationType && PHONE_OPERATOR_PLATFORMS.has(integrationType)) {
      return true
    }
    const platform = resolveDialogPlatform(dialog)
    return Boolean(platform && PHONE_OPERATOR_PLATFORMS.has(platform.toLowerCase()))
  }

  const shouldUseManagerSend = (
    dialog: Dialog | null | undefined,
    isAgentEnabled: boolean
  ): boolean => {
    if (isPhoneOperatorDialog(dialog)) return true
    return !isAgentEnabled
  }

  const sendDialogOutbound = async (params: DialogOutboundSendParams): Promise<void> => {
    const {
      agentId,
      dialogId,
      content,
      dialog,
      isAgentEnabled,
      isWsConnected,
      wsSendMessage
    } = params
    if (shouldUseManagerSend(dialog, isAgentEnabled)) {
      await sendManagerMessage(agentId, dialogId, content)
      return
    }

    if (isWsConnected && wsSendMessage) {
      const tempId = createOptimisticMessage(dialogId, content, 'text')
      const sent = wsSendMessage(dialogId, content)
      if (!sent) {
        markMessageFailed(dialogId, tempId, 'WebSocket отключен')
      }
      return
    }

    await sendMessage(agentId, dialogId, content, 'text', isAgentEnabled)
  }

  return {
    isPhoneOperatorDialog,
    shouldUseManagerSend,
    sendDialogOutbound
  }
}
