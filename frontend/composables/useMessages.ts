import { ref, reactive, readonly } from 'vue'
import type { Message, MessageRole, MessageStatus, MessageType, MessagesListResponse, SendMessageData, SendManagerMessageData } from '../types/dialogs'
import { useApiFetch } from './useApiFetch'
import { useDialogs } from './useDialogs'
import { getStoredAccessToken } from '~/composables/authSessionManager'
import { getReadableErrorMessage } from '~/utils/api-errors'

// State per dialog - using reactive for better dynamic key tracking
const messagesMap = reactive<Record<string, Message[]>>({})

// Helper to update messages
const setMessages = (dialogId: string, messages: Message[]) => {
  messagesMap[dialogId] = [...messages]
}
const isLoading = ref(false)
const isSending = ref(false)
const isStreaming = ref(false)
const streamingMessageId = ref<string | null>(null)
const error = ref<string | null>(null)
const hasMore = ref<Map<string, boolean>>(new Map())

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
    if (['agent', 'assistant', 'bot', 'ai', 'system'].includes(value)) return 'agent'
  }

  return 'agent'
}

const normalizeType = (rawType: unknown): MessageType => {
  if (typeof rawType === 'string') {
    const value = rawType.toLowerCase()
    if (value.includes('image') || value.includes('photo') || value.includes('img')) return 'image'
    if (value.includes('voice') || value.includes('audio') || value.includes('wav') || value.includes('mp3')) return 'voice'
  }

  return 'text'
}

const normalizeStatus = (rawStatus: unknown): MessageStatus => {
  if (typeof rawStatus !== 'string') return 'sent'
  const value = rawStatus.toLowerCase()
  if (value === 'sending') return 'sending'
  if (value === 'failed') return 'failed'
  if (value === 'streaming') return 'streaming'
  if (value === 'done') return 'done'
  return 'sent'
}

// Roles that indicate internal/tool messages (should not be displayed in chat)
const INTERNAL_ROLES = new Set([
  'tool', 'function', 'tool_result', 'function_result',
  'tool_call', 'function_call', 'tool_use'
])

// Message types that indicate internal/tool usage
const INTERNAL_TYPES = new Set([
  'tool_result', 'tool_call', 'function_call', 'function_result', 'tool_use'
])

/**
 * Check if string content looks like raw serialized data (JSON or Python dict/list)
 * that shouldn't be displayed as a human-readable chat message.
 */
const looksLikeRawData = (text: string): boolean => {
  const trimmed = text.trim()
  if (trimmed.length < 20) return false

  // Entire message must look like a data structure
  const isWrapped =
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'))
  if (!isWrapped) return false

  // Try JSON parse
  try {
    const parsed = JSON.parse(trimmed)
    if (typeof parsed === 'object' && parsed !== null) return true
  } catch {
    // Not JSON — check for Python-style dict: {'key': value, ...}
    if (/^\{\s*'[^']+'\s*:/.test(trimmed)) return true
  }

  return false
}

const normalizeMessage = (raw: any, fallbackDialogId: string): Message | null => {
  // --- Filter out internal / tool messages ---

  // 1) Skip by role (tool, function, etc.)
  const rawRoleValue = raw?.role ?? raw?.sender ?? raw?.author ?? raw?.from ?? raw?.direction
  if (typeof rawRoleValue === 'string' && INTERNAL_ROLES.has(rawRoleValue.toLowerCase())) {
    return null
  }

  // 2) Skip by message type (tool_result, function_call, etc.)
  const rawMsgType = raw?.type ?? raw?.message_type ?? raw?.content_type ?? raw?.kind
  if (typeof rawMsgType === 'string' && INTERNAL_TYPES.has(rawMsgType.toLowerCase())) {
    return null
  }

  // 3) Extract content early to check for raw data objects
  const contentValue = raw?.content ?? raw?.text ?? raw?.message ?? raw?.body ?? raw?.payload ?? raw?.data?.content ?? ''

  // Skip when content is a raw object (not string) — likely tool/API response
  if (typeof contentValue === 'object' && contentValue !== null) {
    return null
  }

  const content = typeof contentValue === 'string' ? contentValue : String(contentValue)

  // 4) Skip when content looks like serialized data (JSON / Python dict)
  if (looksLikeRawData(content)) {
    return null
  }

  // --- Normal message normalization ---
  const dialogId = raw?.dialog_id ?? raw?.dialogId ?? raw?.session_id ?? raw?.sessionId ?? fallbackDialogId
  const id = raw?.id ?? raw?.message_id ?? raw?.messageId ?? raw?.uuid ?? raw?._id ?? `${dialogId}-${raw?.created_at ?? raw?.createdAt ?? Date.now()}`
  const role = normalizeRole(rawRoleValue, {
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

  return {
    id: String(id),
    dialog_id: String(dialogId),
    role,
    type,
    content,
    status,
    duration_seconds: durationValue,
    created_at: String(createdAt)
  }
}

export const useMessages = () => {
  const apiFetch = useApiFetch()
  const { dialogs, updateDialogStatus, updateLastMessage, incrementUnread, resolveDialogId } = useDialogs()

  /**
   * Get messages for a dialog
   */
  const getMessages = (dialogId: string): Message[] => {
    return messagesMap[dialogId] || []
  }

  /**
   * Fetch messages for a dialog (with pagination for infinite scroll)
   */
  const fetchMessages = async (agentId: string, dialogId: string, options?: { before?: string; limit?: number }) => {
    if (!agentId || !dialogId) {
      console.warn('[useMessages] Missing agentId or dialogId:', { agentId, dialogId })
      return
    }

    isLoading.value = true
    error.value = null
    let responseHasMore = false

    const params = new URLSearchParams()
    if (options?.before) params.set('before', options.before)
    if (options?.limit) params.set('limit', String(options.limit))
    
    const queryString = params.toString()
    // URL-encode dialogId to handle special characters like ':'
    const encodedDialogId = encodeURIComponent(dialogId)
    const url = `agents/${agentId}/dialogs/${encodedDialogId}/messages${queryString ? `?${queryString}` : ''}`

    try {

      console.log('[useMessages] fetchMessages URL:', url)
      
      const response = await apiFetch<MessagesListResponse | Message[]>(url, {
        method: 'GET'
      })
      
      console.log('[useMessages] fetchMessages raw response:', response)
      console.log('[useMessages] fetchMessages response type:', typeof response, Array.isArray(response) ? 'array' : '')
      
      // Handle both response formats: {messages: [...], has_more: bool} or direct array [...]
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
      } else {
        console.error('[useMessages] Unexpected response format:', response)
      }

      console.log('[useMessages] rawMessages count:', rawMessages.length)
      if (rawMessages.length > 0) {
        console.log('[useMessages] first raw message sample:', rawMessages[0])
      }

      // Normalize messages (with debug logging for filtered messages)
      const messagesList: Message[] = []
      for (const message of rawMessages) {
        const normalized = normalizeMessage(message, dialogId)
        if (normalized) {
          messagesList.push(normalized)
        } else {
          console.warn('[useMessages] Message filtered out by normalizeMessage:', {
            id: message?.id,
            role: message?.role ?? message?.sender,
            type: message?.type ?? message?.message_type,
            content_type: typeof message?.content,
            content_preview: typeof message?.content === 'string' ? message.content.slice(0, 80) : typeof message?.content
          })
        }
      }
      const existingMessages = messagesMap[dialogId] || []
      
      if (options?.before) {
        setMessages(dialogId, [...messagesList, ...existingMessages])
      } else {
        setMessages(dialogId, messagesList)
      }

      hasMore.value.set(dialogId, responseHasMore)
      console.log('[useMessages] Final messages count for dialog', dialogId, ':', (messagesMap[dialogId] || []).length)
    } catch (err: any) {
      console.error('[useMessages] fetchMessages error:', err)
      console.error('[useMessages] fetchMessages error details:', {
        status: err?.statusCode || err?.status,
        data: err?.data,
        message: err?.message,
        url
      })
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить сообщения')
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Send a message (text, image, voice)
   */
  const sendMessage = async (
    agentId: string,
    dialogId: string,
    content: string,
    type: MessageType = 'text',
    agentEnabled: boolean = true
  ): Promise<Message | null> => {
    if (!agentId || !dialogId || !content.trim()) return null

    isSending.value = true
    error.value = null

    // Create optimistic message
    const tempId = `temp-${Date.now()}`
    const optimisticMessage: Message = {
      id: tempId,
      dialog_id: dialogId,
      role: 'user',
      type,
      content: content.trim(),
      status: 'sending',
      created_at: new Date().toISOString()
    }

    // Add to messages immediately
    const messages = messagesMap[dialogId] || []
    setMessages(dialogId, [...messages, optimisticMessage])

    try {
      const body: SendMessageData = { content: content.trim(), type }
      
      const encodedDialogId = encodeURIComponent(dialogId)
      const response = await apiFetch<Message>(`agents/${agentId}/dialogs/${encodedDialogId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body
      })

      // Keep temp ID stable — only update status to avoid TransitionGroup key change (prevents UI flicker)
      const currentMessages = messagesMap[dialogId] || []
      const index = currentMessages.findIndex(m => m.id === tempId)
      if (index !== -1) {
        const updatedMessages = [...currentMessages]
        updatedMessages[index] = { ...updatedMessages[index], status: 'sent' }
        setMessages(dialogId, updatedMessages)
      }

      // Update dialog preview
      updateLastMessage(dialogId, content.trim().slice(0, 100), response.created_at || new Date().toISOString())

      // If agent is enabled, start streaming response
      if (agentEnabled) {
        const realId = response?.id || (response as any)?.message_id
        if (realId) {
          await startAgentStream(agentId, dialogId, realId)
        }
      }

      return response
    } catch (err: any) {
      // Mark message as failed
      const currentMessages = messagesMap[dialogId] || []
      const index = currentMessages.findIndex(m => m.id === tempId)
      if (index !== -1) {
        const updatedMessages = [...currentMessages]
        updatedMessages[index] = { 
          ...updatedMessages[index], 
          status: 'failed',
          error_message: getReadableErrorMessage(err, 'Ошибка отправки')
        }
        setMessages(dialogId, updatedMessages)
      }

      error.value = getReadableErrorMessage(err, 'Не удалось отправить сообщение')
      return null
    } finally {
      isSending.value = false
    }
  }

  /**
   * Retry failed message
   */
  const retryMessage = async (agentId: string, dialogId: string, messageId: string, agentEnabled: boolean = true) => {
    const messages = messagesMap[dialogId] || []
    const message = messages.find(m => m.id === messageId)
    
    if (!message || message.status !== 'failed') return
    
    // Remove failed message
    setMessages(dialogId, messages.filter(m => m.id !== messageId))
    
    // Resend
    await sendMessage(agentId, dialogId, message.content, message.type, agentEnabled)
  }

  /**
   * Send a manager (operator) message in a dialog
   * POST /agents/{agent_id}/dialogs/{dialog_id}/manager-message
   */
  const sendManagerMessage = async (
    agentId: string,
    dialogId: string,
    content: string
  ): Promise<Message | null> => {
    if (!agentId || !dialogId || !content.trim()) return null

    isSending.value = true
    error.value = null

    // Create optimistic message with 'manager' role
    const tempId = `temp-mgr-${Date.now()}`
    const optimisticMessage: Message = {
      id: tempId,
      dialog_id: dialogId,
      role: 'manager',
      type: 'text',
      content: content.trim(),
      status: 'sending',
      created_at: new Date().toISOString()
    }

    // Add to messages immediately
    const messages = messagesMap[dialogId] || []
    setMessages(dialogId, [...messages, optimisticMessage])

    try {
      const body: SendManagerMessageData = { content: content.trim() }
      const encodedDialogId = encodeURIComponent(dialogId)

      await apiFetch<Message>(
        `agents/${agentId}/dialogs/${encodedDialogId}/manager-message`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body
        }
      )

      // Keep temp ID stable — only update status to avoid TransitionGroup key change (prevents UI flicker)
      const currentMessages = messagesMap[dialogId] || []
      const index = currentMessages.findIndex(m => m.id === tempId)
      if (index !== -1) {
        const updatedMessages = [...currentMessages]
        updatedMessages[index] = { ...updatedMessages[index], status: 'sent' }
        setMessages(dialogId, updatedMessages)
      }

      updateLastMessage(dialogId, content.trim().slice(0, 100), new Date().toISOString())

      return { ...optimisticMessage, status: 'sent' as MessageStatus }
    } catch (err: any) {
      // Mark message as failed
      const currentMessages = messagesMap[dialogId] || []
      const index = currentMessages.findIndex(m => m.id === tempId)
      if (index !== -1) {
        const updatedMessages = [...currentMessages]
        updatedMessages[index] = {
          ...updatedMessages[index],
          status: 'failed',
          error_message: getReadableErrorMessage(err, 'Ошибка отправки')
        }
        setMessages(dialogId, updatedMessages)
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

  /**
   * Create optimistic user message (for WebSocket mode)
   * Returns the temp ID for tracking
   */
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
      created_at: new Date().toISOString()
    }

    const messages = messagesMap[dialogId] || []
    setMessages(dialogId, [...messages, optimisticMessage])
    isSending.value = true

    return tempId
  }

  /**
   * Mark optimistic message as sent (when server confirms via WebSocket)
   * Keeps the temp ID stable to avoid TransitionGroup key change (prevents UI flicker)
   */
  const markMessageSent = (dialogId: string, tempId: string, _realId?: string) => {
    const messages = messagesMap[dialogId] || []
    const index = messages.findIndex(m => m.id === tempId)
    
    if (index !== -1) {
      const updatedMessages = [...messages]
      updatedMessages[index] = {
        ...updatedMessages[index],
        status: 'sent'
      }
      setMessages(dialogId, updatedMessages)
    }
    
    isSending.value = false
  }

  /**
   * Mark optimistic message as failed
   */
  const markMessageFailed = (dialogId: string, tempId: string, errorMessage?: string) => {
    const readableMsg = errorMessage || 'Не удалось отправить сообщение'
    const messages = messagesMap[dialogId] || []
    const index = messages.findIndex(m => m.id === tempId)
    
    if (index !== -1) {
      const updatedMessages = [...messages]
      updatedMessages[index] = {
        ...updatedMessages[index],
        status: 'failed',
        error_message: readableMsg
      }
      setMessages(dialogId, updatedMessages)
    }
    
    isSending.value = false
    error.value = readableMsg
  }

  /**
   * Handle run_start event from WebSocket
   * Creates streaming placeholder for agent response
   */
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
      created_at: new Date().toISOString()
    }

    const messages = messagesMap[dialogId] || []
    setMessages(dialogId, [...messages, agentMessage])
  }

  /**
   * Handle run_result event from WebSocket
   * Updates agent message with final content
   */
  const handleRunResult = (runId: string, dialogId: string, output: string) => {
    const agentMessageId = `agent-${runId}`
    
    const messages = messagesMap[dialogId] || []
    const index = messages.findIndex(m => m.id === agentMessageId)
    
    if (index !== -1) {
      const updatedMessages = [...messages]
      updatedMessages[index] = {
        ...updatedMessages[index],
        content: output,
        status: 'done'
      }
      setMessages(dialogId, updatedMessages)
    }

    isStreaming.value = false
    streamingMessageId.value = null
  }

  /**
   * Handle run_error event from WebSocket
   */
  const handleRunError = (runId: string, dialogId: string, errorMsg: string) => {
    const agentMessageId = `agent-${runId}`
    
    const messages = messagesMap[dialogId] || []
    const index = messages.findIndex(m => m.id === agentMessageId)
    
    if (index !== -1) {
      const updatedMessages = [...messages]
      updatedMessages[index] = {
        ...updatedMessages[index],
        content: `Ошибка: ${errorMsg}`,
        status: 'failed',
        error_message: errorMsg
      }
      setMessages(dialogId, updatedMessages)
    }

    isStreaming.value = false
    streamingMessageId.value = null
    error.value = errorMsg
  }

  /**
   * @deprecated Use WebSocket for streaming instead
   * Start SSE stream for agent response (HTTP fallback)
   */
  const startAgentStream = async (agentId: string, dialogId: string, userMessageId: string) => {
    isStreaming.value = true
    updateDialogStatus(dialogId, 'IN_PROGRESS')

    // Create placeholder for agent message
    const agentMessageId = `agent-${Date.now()}`
    streamingMessageId.value = agentMessageId
    
    const agentMessage: Message = {
      id: agentMessageId,
      dialog_id: dialogId,
      role: 'agent',
      type: 'text',
      content: '',
      status: 'streaming',
      created_at: new Date().toISOString()
    }

    const messages = messagesMap[dialogId] || []
    setMessages(dialogId, [...messages, agentMessage])

    try {
      // Get auth token
      const token = getStoredAccessToken()
      
      const encodedDialogId = encodeURIComponent(dialogId)
      const response = await fetch(`/api/v1/agents/${agentId}/dialogs/${encodedDialogId}/messages/stream`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ user_message_id: userMessageId })
      })

      if (!response.ok) {
        throw new Error(getReadableErrorMessage({ status: response.status }, 'Не удалось получить ответ агента'))
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No reader available')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue

            try {
              const event = JSON.parse(data)
              
              if (event.type === 'delta' && event.data?.content) {
                // Update streaming message content
                const currentMessages = messagesMap[dialogId] || []
                const index = currentMessages.findIndex(m => m.id === agentMessageId)
                if (index !== -1) {
                  const updatedMessages = [...currentMessages]
                  updatedMessages[index] = {
                    ...updatedMessages[index],
                    content: updatedMessages[index].content + event.data.content
                  }
                  setMessages(dialogId, updatedMessages)
                }
              } else if (event.type === 'done') {
                // Mark as complete
                const currentMessages = messagesMap[dialogId] || []
                const index = currentMessages.findIndex(m => m.id === agentMessageId)
                if (index !== -1) {
                  const updatedMessages = [...currentMessages]
                  updatedMessages[index] = {
                    ...updatedMessages[index],
                    id: event.data?.message_id || agentMessageId,
                    status: 'done'
                  }
                  setMessages(dialogId, updatedMessages)
                }
              } else if (event.type === 'error') {
                throw new Error(event.data?.error || 'Stream error')
              }
            } catch (parseError) {
              console.warn('Failed to parse SSE event:', parseError)
            }
          }
        }
      }

      // Finalize streaming
      const finalMessages = messagesMap[dialogId] || []
      const finalIndex = finalMessages.findIndex(m => m.id === agentMessageId || m.status === 'streaming')
      if (finalIndex !== -1 && finalMessages[finalIndex].status === 'streaming') {
        const updatedFinalMessages = [...finalMessages]
        updatedFinalMessages[finalIndex] = { ...updatedFinalMessages[finalIndex], status: 'done' }
        setMessages(dialogId, updatedFinalMessages)
      }

      // Update dialog preview with agent response
      const agentContent = finalMessages[finalIndex]?.content || ''
      if (agentContent) {
        updateLastMessage(dialogId, agentContent.slice(0, 100), new Date().toISOString())
      }

      updateDialogStatus(dialogId, 'NORMAL')
    } catch (err: any) {
      console.error('Stream error:', err)
      
      // Mark agent message as failed/remove it
      const currentMessages = messagesMap[dialogId] || []
      const index = currentMessages.findIndex(m => m.id === agentMessageId)
      if (index !== -1) {
        // Remove the failed streaming message
        const updatedMessages = currentMessages.filter((_, i) => i !== index)
        setMessages(dialogId, updatedMessages)
      }

      updateDialogStatus(dialogId, 'ERROR')
      error.value = getReadableErrorMessage(err, 'Не удалось получить ответ агента')
    } finally {
      isStreaming.value = false
      streamingMessageId.value = null
    }
  }

  /**
   * Add message locally (for real-time updates)
   */
  const addMessage = (dialogId: string, message: Message) => {
    const resolvedDialogId = resolveDialogId(dialogId) ?? dialogId
    const messages = messagesMap[resolvedDialogId] || []
    setMessages(resolvedDialogId, [...messages, { ...message, dialog_id: resolvedDialogId }])
  }

  /**
   * Update message locally
   */
  const updateMessage = (dialogId: string, messageId: string, updates: Partial<Message>) => {
    const resolvedDialogId = resolveDialogId(dialogId) ?? dialogId
    const messages = messagesMap[resolvedDialogId] || []
    const index = messages.findIndex(m => m.id === messageId)
    if (index !== -1) {
      const updatedMessages = [...messages]
      updatedMessages[index] = { ...updatedMessages[index], ...updates }
      setMessages(resolvedDialogId, updatedMessages)
    }
  }

  /**
   * Clear messages for a dialog
   */
  const clearMessages = (dialogId: string) => {
    const resolvedDialogId = resolveDialogId(dialogId) ?? dialogId
    delete messagesMap[resolvedDialogId]
    hasMore.value.delete(resolvedDialogId)
  }

  /**
   * Check if dialog has more messages to load
   */
  const dialogHasMore = (dialogId: string): boolean => {
    return hasMore.value.get(dialogId) ?? true
  }

  /**
   * Add incoming message from WebSocket/SSE (for real-time updates)
   */
  const addIncomingMessage = (message: any) => {
    const rawDialogId = message?.dialog_id ?? message?.session_id
    const dialogId = resolveDialogId(rawDialogId)

    if (!dialogId) return

    const currentMessages = messagesMap[dialogId] || []
    const normalizedMessage = normalizeMessage({ ...message, dialog_id: dialogId }, dialogId)

    // Skip internal/tool messages (normalizeMessage returns null for those)
    if (!normalizedMessage) return

    // Avoid duplicates by ID
    if (currentMessages.some(m => m.id === normalizedMessage.id)) return

    // Avoid duplicates by content+role for recent messages
    // (handles temp ID vs real ID mismatch from optimistic updates)
    const now = Date.now()
    const isDuplicateByContent = currentMessages.some(m =>
      m.role === normalizedMessage.role &&
      m.content.trim() === normalizedMessage.content.trim() &&
      m.status !== 'failed' &&
      now - new Date(m.created_at).getTime() < 15_000
    )
    if (isDuplicateByContent) return

    setMessages(dialogId, [...currentMessages, normalizedMessage])
    updateLastMessage(dialogId, normalizedMessage.content.slice(0, 100), normalizedMessage.created_at)
  }

  return {
    // State
    isLoading: readonly(isLoading),
    isSending: readonly(isSending),
    isStreaming: readonly(isStreaming),
    streamingMessageId: readonly(streamingMessageId),
    error: readonly(error),
    messagesMap, // Export for direct reactive access

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

    // WebSocket-specific methods
    createOptimisticMessage,
    markMessageSent,
    markMessageFailed,
    handleRunStart,
    handleRunResult,
    handleRunError,

    // @deprecated - use WebSocket streaming instead
    startAgentStream
  }
}
