import { ref, reactive, readonly } from 'vue'
import type { Message, MessageRole, MessageStatus, MessageType, MessagesListResponse } from '../types/dialogs'
import type { SendMessageData, SendManagerMessageData } from '../types/dialogs'
import { useApiFetch } from './useApiFetch'
import { useDialogs } from './useDialogs'
import { getReadableErrorMessage } from '~/utils/api-errors'

// Per-dialog message storage
const messagesMap = reactive<Record<string, Message[]>>({})

// Per-dialog has_more flag (reactive Record — Map inside ref does not trigger Vue reactivity)
const hasMoreMap = reactive<Record<string, boolean>>({})

const isLoading = ref(false)
const isSending = ref(false)
const isStreaming = ref(false)
const streamingMessageId = ref<string | null>(null)
const error = ref<string | null>(null)

const normalizeRole = (
  rawRole: unknown,
  flags: { isUser?: boolean; is_user?: boolean; isAgent?: boolean; is_agent?: boolean }
): MessageRole => {
  const isUserFlag = flags.isUser ?? flags.is_user
  const isAgentFlag = flags.isAgent ?? flags.is_agent

  if (typeof isUserFlag === 'boolean') return isUserFlag ? 'user' : 'agent'
  if (typeof isAgentFlag === 'boolean') return isAgentFlag ? 'agent' : 'user'

  if (typeof rawRole === 'string') {
    const value = rawRole.toLowerCase()
    if (['user', 'human', 'client', 'customer', 'visitor', 'requester'].includes(value)) return 'user'
    if (['manager', 'operator', 'admin', 'support'].includes(value)) return 'manager'
    if (value === 'system') return 'system'
    if (['agent', 'assistant', 'bot', 'ai'].includes(value)) return 'agent'
  }

  return 'agent'
}

const normalizeType = (rawType: unknown): MessageType => {
  if (typeof rawType === 'string') {
    const value = rawType.toLowerCase()
    if (value === 'tool_call') return 'tool_call'
    if (value === 'tool_result') return 'tool_result'
    if (value.includes('image') || value.includes('photo') || value.includes('img')) return 'image'
    if (value.includes('voice') || value.includes('audio') || value.includes('wav') || value.includes('mp3')) return 'voice'
  }
  return 'text'
}

const normalizeStatus = (rawStatus: unknown): MessageStatus => {
  if (typeof rawStatus !== 'string') return 'sent'
  const value = rawStatus.toLowerCase()
  if (value === 'sending') return 'sending'
  if (value === 'delivered' || value === 'received') return 'delivered'
  if (value === 'read' || value === 'seen' || value === 'displayed') return 'read'
  if (value === 'failed') return 'failed'
  if (value === 'streaming') return 'streaming'
  if (value === 'done') return 'done'
  return 'sent'
}

// Roles that indicate internal/tool messages (should not be displayed in chat)
export const INTERNAL_ROLES = new Set([
  'tool', 'function', 'tool_result', 'function_result',
  'function_call', 'tool_use'
])

// Message types that are treated as tool UI cards (not filtered out, rendered specially)
const TOOL_TYPES = new Set(['tool_call', 'tool_result'])

// Message types that indicate truly internal/system usage (filtered out completely)
const INTERNAL_TYPES = new Set([
  'function_call', 'function_result', 'tool_use'
])

const looksLikeRawData = (text: string): boolean => {
  const trimmed = text.trim()
  if (trimmed.length < 20) return false
  const isWrapped =
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'))
  if (!isWrapped) return false
  try {
    const parsed = JSON.parse(trimmed)
    if (typeof parsed === 'object' && parsed !== null) return true
  } catch {
    // Python-format dict: {'key': value}
    if (/^\{\s*'[^']+'\s*:/.test(trimmed)) return true
    // Python-format list of dicts: [{'key': value}, ...]
    if (/^\[\s*\{/.test(trimmed)) return true
  }
  return false
}

const normalizeMessage = (raw: any, fallbackDialogId: string): Message | null => {
  const rawRoleValue = raw?.role ?? raw?.sender ?? raw?.author ?? raw?.from ?? raw?.direction
  if (typeof rawRoleValue === 'string' && INTERNAL_ROLES.has(rawRoleValue.toLowerCase())) {
    return null
  }

  const rawMsgType = raw?.type ?? raw?.message_type ?? raw?.content_type ?? raw?.kind
  const isTool = typeof rawMsgType === 'string' && TOOL_TYPES.has(rawMsgType.toLowerCase())
  if (typeof rawMsgType === 'string' && INTERNAL_TYPES.has(rawMsgType.toLowerCase())) {
    return null
  }

  const contentValue = raw?.content ?? raw?.text ?? raw?.message ?? raw?.body ?? raw?.payload ?? raw?.data?.content ?? ''

  if (!isTool && typeof contentValue === 'object' && contentValue !== null) {
    return null
  }

  const content = typeof contentValue === 'string'
    ? contentValue
    : (typeof contentValue === 'object' ? JSON.stringify(contentValue) : String(contentValue))

  if (!isTool && looksLikeRawData(content)) {
    return null
  }

  const dialogId = raw?.dialog_id ?? raw?.dialogId ?? raw?.session_id ?? raw?.sessionId ?? fallbackDialogId
  const id = raw?.id ?? raw?.message_id ?? raw?.messageId ?? raw?.uuid ?? raw?._id ?? `${dialogId}-${raw?.created_at ?? raw?.createdAt ?? Date.now()}`
  const serverIdRaw = raw?.server_id ?? raw?.serverId
  const serverId = typeof serverIdRaw === 'string' && serverIdRaw.trim()
    ? serverIdRaw.trim()
    : undefined
  let role = normalizeRole(rawRoleValue, {
    isUser: raw?.isUser,
    is_user: raw?.is_user,
    isAgent: raw?.isAgent,
    is_agent: raw?.is_agent
  })
  const type = normalizeType(raw?.type ?? raw?.message_type ?? raw?.content_type ?? raw?.kind ?? raw?.media_type)
  const createdAt = raw?.created_at ?? raw?.createdAt ?? raw?.timestamp ?? raw?.time ?? raw?.created ?? new Date().toISOString()
  const status = normalizeStatus(raw?.status)
  const durationSeconds = raw?.duration_seconds ?? raw?.durationSeconds ?? raw?.duration
  const durationValue = typeof durationSeconds === 'number'
    ? durationSeconds
    : Number.isFinite(Number(durationSeconds))
      ? Number(durationSeconds)
      : undefined

  const senderKind = typeof raw?.sender_kind === 'string' ? raw.sender_kind : undefined
  let senderLabel = typeof raw?.sender_label === 'string' ? raw.sender_label.trim() : undefined
  const userInfo = raw?.user_info && typeof raw.user_info === 'object' ? raw.user_info : undefined
  if (role === 'user' && userInfo) {
    const ui = userInfo as Record<string, unknown>
    const wappiDirection = typeof ui.wappi_direction === 'string' ? ui.wappi_direction.toLowerCase() : ''
    const senderKindFromUi = typeof ui.message_sender_kind === 'string' ? ui.message_sender_kind.toLowerCase() : ''
    if (wappiDirection === 'out' || senderKindFromUi === 'wappi_operator' || senderKind === 'wappi_operator') {
      role = 'manager'
    }
  }
  if (!senderLabel && raw?.user_info && typeof raw.user_info === 'object') {
    const ui = raw.user_info as Record<string, unknown>
    const fromUi = typeof ui.sender_display_label === 'string' ? ui.sender_display_label.trim() : ''
    if (fromUi) senderLabel = fromUi
  }

  return {
    id: String(id),
    server_id: serverId,
    dialog_id: String(dialogId),
    role,
    type,
    content,
    status,
    duration_seconds: durationValue,
    created_at: String(createdAt),
    sender_kind: senderKind || undefined,
    sender_label: senderLabel || undefined,
    user_info: userInfo,
    tool_name: raw?.tool_name ?? undefined,
    tool_call_id: raw?.tool_call_id ?? undefined,
    args: raw?.args ?? undefined,
    result: raw?.result ?? undefined,
    is_edited: raw?.is_edited ?? undefined,
    is_deleted: raw?.is_deleted ?? undefined,
  }
}

export const useMessages = () => {
  const apiFetch = useApiFetch()
  const { updateLastMessage, resolveDialogId } = useDialogs()

  const getMessages = (dialogId: string): Message[] => {
    return messagesMap[dialogId] || []
  }

  const fetchMessages = async (agentId: string, dialogId: string, options?: { before?: string; limit?: number }) => {
    if (!agentId || !dialogId) return

    isLoading.value = true
    error.value = null
    let responseHasMore = false

    const params = new URLSearchParams()
    if (options?.before) params.set('before', options.before)
    if (options?.limit) params.set('limit', String(options.limit))

    const queryString = params.toString()
    const encodedDialogId = encodeURIComponent(dialogId)
    const url = `agents/${agentId}/dialogs/${encodedDialogId}/messages${queryString ? `?${queryString}` : ''}`

    try {
      const response = await apiFetch<MessagesListResponse | Message[]>(url, { method: 'GET' })

      let rawMessages: any[] = []
      if (Array.isArray(response)) {
        rawMessages = response
        responseHasMore = false
      } else if (response && typeof response === 'object' && 'messages' in response) {
        rawMessages = response.messages || []
        responseHasMore = response.has_more || false
      } else if (response && typeof response === 'object' && 'items' in response) {
        rawMessages = (response as any).items || []
        responseHasMore = (response as any).has_more || false
      } else if (response && typeof response === 'object' && 'data' in response) {
        rawMessages = (response as any).data || []
        responseHasMore = (response as any).has_more || false
      }

      const messagesList: Message[] = []
      for (const message of rawMessages) {
        const normalized = normalizeMessage(message, dialogId)
        if (normalized) messagesList.push(normalized)
      }

      const existingMessages = messagesMap[dialogId] || []
      if (options?.before) {
        messagesMap[dialogId] = [...messagesList, ...existingMessages]
      } else {
        messagesMap[dialogId] = messagesList
      }

      hasMoreMap[dialogId] = responseHasMore
    } catch (err: any) {
      console.error('[useMessages] fetchMessages error:', err)
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить сообщения')
    } finally {
      isLoading.value = false
    }
  }

  const sendMessage = async (
    agentId: string,
    dialogId: string,
    content: string,
    type: MessageType = 'text',
  ): Promise<Message | null> => {
    if (!agentId || !dialogId || !content.trim()) return null

    isSending.value = true
    error.value = null

    const tempId = `temp-${Date.now()}`
    const optimisticMessage: Message = {
      id: tempId,
      dialog_id: dialogId,
      role: 'user',
      type,
      content: content.trim(),
      status: 'sending',
      created_at: new Date().toISOString(),
      sender_kind: 'contact',
      sender_label: 'Клиент',
    }

    if (!messagesMap[dialogId]) messagesMap[dialogId] = []
    messagesMap[dialogId].push(optimisticMessage)

    try {
      const body: SendMessageData = { content: content.trim(), type }
      const encodedDialogId = encodeURIComponent(dialogId)
      const response = await apiFetch<Message>(`agents/${agentId}/dialogs/${encodedDialogId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body
      })

      const index = (messagesMap[dialogId] || []).findIndex(m => m.id === tempId)
      if (index !== -1) {
        messagesMap[dialogId][index] = { ...messagesMap[dialogId][index], status: 'sent' }
      }

      updateLastMessage(dialogId, content.trim().slice(0, 100), response.created_at || new Date().toISOString())
      return response
    } catch (err: any) {
      const index = (messagesMap[dialogId] || []).findIndex(m => m.id === tempId)
      if (index !== -1) {
        messagesMap[dialogId][index] = {
          ...messagesMap[dialogId][index],
          status: 'failed',
          error_message: getReadableErrorMessage(err, 'Ошибка отправки')
        }
      }
      error.value = getReadableErrorMessage(err, 'Не удалось отправить сообщение')
      return null
    } finally {
      isSending.value = false
    }
  }

  const retryMessage = async (agentId: string, dialogId: string, messageId: string) => {
    const messages = messagesMap[dialogId] || []
    const message = messages.find(m => m.id === messageId)
    if (!message || message.status !== 'failed') return
    messagesMap[dialogId] = messages.filter(m => m.id !== messageId)
    await sendMessage(agentId, dialogId, message.content, message.type)
  }

  const sendManagerMessage = async (
    agentId: string,
    dialogId: string,
    content: string
  ): Promise<Message | null> => {
    if (!agentId || !dialogId || !content.trim()) return null

    isSending.value = true
    error.value = null

    const tempId = `temp-mgr-${Date.now()}`
    const optimisticMessage: Message = {
      id: tempId,
      dialog_id: dialogId,
      role: 'manager',
      type: 'text',
      content: content.trim(),
      status: 'sending',
      created_at: new Date().toISOString(),
      sender_kind: 'manager',
      sender_label: 'Менеджер',
    }

    if (!messagesMap[dialogId]) messagesMap[dialogId] = []
    messagesMap[dialogId].push(optimisticMessage)

    try {
      const body: SendManagerMessageData = { content: content.trim() }
      const encodedDialogId = encodeURIComponent(dialogId)

      const response = await apiFetch<Record<string, unknown>>(
        `agents/${agentId}/dialogs/${encodedDialogId}/manager-message`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body
        }
      )
      const realIdRaw = response?.message_id ?? response?.id
      const realId = typeof realIdRaw === 'string' ? realIdRaw : (realIdRaw ? String(realIdRaw) : '')

      const index = (messagesMap[dialogId] || []).findIndex(m => m.id === tempId)
      if (index !== -1) {
        messagesMap[dialogId][index] = {
          ...messagesMap[dialogId][index],
          status: 'sent',
          server_id: realId || messagesMap[dialogId][index].server_id
        }
      }

      updateLastMessage(dialogId, content.trim().slice(0, 100), new Date().toISOString())
      return { ...optimisticMessage, status: 'sent' as MessageStatus }
    } catch (err: any) {
      const index = (messagesMap[dialogId] || []).findIndex(m => m.id === tempId)
      if (index !== -1) {
        messagesMap[dialogId][index] = {
          ...messagesMap[dialogId][index],
          status: 'failed',
          error_message: getReadableErrorMessage(err, 'Ошибка отправки')
        }
      }
      error.value = getReadableErrorMessage(err, 'Не удалось отправить сообщение менеджера')
      return null
    } finally {
      isSending.value = false
    }
  }

  // ===========================================
  // WebSocket-specific methods
  // ===========================================

  const createOptimisticMessage = (
    dialogId: string,
    content: string,
    type: MessageType = 'text'
  ): string => {
    const tempId = `temp-${Date.now()}`
    const optimisticMessage: Message = {
      id: tempId,
      dialog_id: dialogId,
      role: 'user',
      type,
      content: content.trim(),
      status: 'sending',
      created_at: new Date().toISOString(),
      sender_kind: 'contact',
      sender_label: 'Клиент',
    }
    if (!messagesMap[dialogId]) messagesMap[dialogId] = []
    messagesMap[dialogId].push(optimisticMessage)
    isSending.value = true
    return tempId
  }

  const markMessageSent = (dialogId: string, tempId: string, realId?: string) => {
    const messages = messagesMap[dialogId] || []
    const index = messages.findIndex(m => m.id === tempId)
    if (index !== -1) {
      messagesMap[dialogId][index] = {
        ...messagesMap[dialogId][index],
        status: 'sent',
        server_id: realId || messagesMap[dialogId][index].server_id
      }
    }
    isSending.value = false
  }

  const markMessageFailed = (dialogId: string, tempId: string, errorMessage?: string) => {
    const readableMsg = errorMessage || 'Не удалось отправить сообщение'
    const messages = messagesMap[dialogId] || []
    const index = messages.findIndex(m => m.id === tempId)
    if (index !== -1) {
      messagesMap[dialogId][index] = {
        ...messagesMap[dialogId][index],
        status: 'failed',
        error_message: readableMsg
      }
    }
    isSending.value = false
    error.value = readableMsg
  }

  const handleRunStart = (runId: string, dialogId: string) => {
    isStreaming.value = true
    const agentMessageId = `agent-${runId}`
    streamingMessageId.value = agentMessageId

    const agentMessage: Message = {
      id: agentMessageId,
      dialog_id: dialogId,
      role: 'agent',
      type: 'text',
      content: '',
      status: 'streaming',
      created_at: new Date().toISOString(),
      sender_kind: 'agent',
      sender_label: 'Агент',
    }
    if (!messagesMap[dialogId]) messagesMap[dialogId] = []
    messagesMap[dialogId].push(agentMessage)
  }

  const handleRunResult = (runId: string, dialogId: string, output: string) => {
    const agentMessageId = `agent-${runId}`
    const messages = messagesMap[dialogId] || []
    const index = messages.findIndex(m => m.id === agentMessageId)
    if (index !== -1) {
      messagesMap[dialogId][index] = {
        ...messagesMap[dialogId][index],
        content: output,
        status: 'done'
      }
    }
    isStreaming.value = false
    streamingMessageId.value = null
  }

  const handleRunError = (runId: string, dialogId: string, errorMsg: string) => {
    const agentMessageId = `agent-${runId}`
    const displayContent =
      typeof errorMsg === 'string' && errorMsg.trim().length > 0 ? errorMsg.trim() : 'Не удалось получить ответ агента.'

    const messages = messagesMap[dialogId] || []
    const index = messages.findIndex(m => m.id === agentMessageId)
    if (index !== -1) {
      messagesMap[dialogId][index] = {
        ...messagesMap[dialogId][index],
        content: displayContent,
        status: 'failed',
        error_message: displayContent
      }
    }
    isStreaming.value = false
    streamingMessageId.value = null
    error.value = displayContent
  }

  const addMessage = (dialogId: string, message: Message) => {
    const resolvedDialogId = resolveDialogId(dialogId) ?? dialogId
    if (!messagesMap[resolvedDialogId]) messagesMap[resolvedDialogId] = []
    messagesMap[resolvedDialogId].push({ ...message, dialog_id: resolvedDialogId })
  }

  const updateMessage = (dialogId: string, messageId: string, updates: Partial<Message>) => {
    const resolvedDialogId = resolveDialogId(dialogId) ?? dialogId
    const messages = messagesMap[resolvedDialogId] || []
    const index = messages.findIndex(m => m.id === messageId || m.server_id === messageId)
    if (index !== -1) {
      messagesMap[resolvedDialogId][index] = { ...messagesMap[resolvedDialogId][index], ...updates }
    }
  }

  const clearMessages = (dialogId: string) => {
    const resolvedDialogId = resolveDialogId(dialogId) ?? dialogId
    delete messagesMap[resolvedDialogId]
    delete hasMoreMap[resolvedDialogId]
  }

  const clearHistory = async (agentId: string, dialogId: string): Promise<boolean> => {
    if (!agentId || !dialogId) return false
    const encodedDialogId = encodeURIComponent(dialogId)
    try {
      await apiFetch(`agents/${agentId}/dialogs/${encodedDialogId}/history`, { method: 'DELETE' })
      clearMessages(dialogId)
      return true
    } catch (err) {
      console.error('[useMessages] clearHistory error:', err)
      return false
    }
  }

  const dialogHasMore = (dialogId: string): boolean => {
    return hasMoreMap[dialogId] ?? true
  }

  const addIncomingMessage = (message: any) => {
    const rawDialogId = message?.dialog_id ?? message?.session_id
    const dialogId = resolveDialogId(rawDialogId)
    if (!dialogId) return

    const currentMessages = messagesMap[dialogId] || []
    const normalizedMessage = normalizeMessage({ ...message, dialog_id: dialogId }, dialogId)
    if (!normalizedMessage) return

    // Dedup by ID
    if (currentMessages.some(m => m.id === normalizedMessage.id || m.server_id === normalizedMessage.id)) return

    // Dedup optimistic messages by content+role within 15s window
    const now = Date.now()
    const isDuplicateByContent = currentMessages.some(m =>
      m.role === normalizedMessage.role &&
      m.content.trim() === normalizedMessage.content.trim() &&
      m.status !== 'failed' &&
      now - new Date(m.created_at).getTime() < 15_000
    )
    if (isDuplicateByContent) return

    if (!messagesMap[dialogId]) messagesMap[dialogId] = []
    messagesMap[dialogId].push(normalizedMessage)
    updateLastMessage(dialogId, normalizedMessage.content.slice(0, 100), normalizedMessage.created_at)
  }

  return {
    // State
    isLoading: readonly(isLoading),
    isSending: readonly(isSending),
    isStreaming: readonly(isStreaming),
    streamingMessageId: readonly(streamingMessageId),
    error: readonly(error),
    messagesMap,

    // Getters
    getMessages,
    dialogHasMore,

    // Actions
    fetchMessages,
    sendMessage,
    sendManagerMessage,
    retryMessage,
    addMessage,
    addIncomingMessage,
    updateMessage,
    clearMessages,
    clearHistory,

    // WebSocket-specific methods
    createOptimisticMessage,
    markMessageSent,
    markMessageFailed,
    handleRunStart,
    handleRunResult,
    handleRunError,
  }
}
