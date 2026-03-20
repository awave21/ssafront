import { ref, watch, onUnmounted, computed, type ComputedRef, unref } from 'vue'
import { useDialogs } from './useDialogs'
import { useMessages } from './useMessages'
import { getStoredAccessToken } from '~/composables/authSessionManager'
import type {
  WsConnectionState,
  WsOutgoingMessage,
  WsIncomingMessage,
  WsReconnectConfig
} from '../types/websocket'

const DEFAULT_RECONNECT_CONFIG: WsReconnectConfig = {
  maxAttempts: 5,
  baseDelay: 1000,
  maxDelay: 16000
}

export const useAgentWebSocket = (
  agentId: string | null | ComputedRef<string | null>,
  options?: {
    autoConnect?: boolean
    reconnectConfig?: Partial<WsReconnectConfig>
  }
) => {
  const dialogsStore = useDialogs()
  const messagesStore = useMessages()
  // Use resolveDialogId from dialogs store to avoid duplication
  const { resolveDialogId } = dialogsStore

  // Merge config with defaults
  const reconnectConfig: WsReconnectConfig = {
    ...DEFAULT_RECONNECT_CONFIG,
    ...options?.reconnectConfig
  }

  // State
  const connectionState = ref<WsConnectionState>('disconnected')
  const reconnectAttempts = ref(0)
  const currentRunId = ref<string | null>(null)
  const currentDialogId = ref<string | null>(null)
  const activeDialogId = ref<string | null>(null)

  // Internal refs
  let ws: WebSocket | null = null
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  let pingTimeout: ReturnType<typeof setTimeout> | null = null

  /**
   * Get WebSocket URL with token
   */
  const getWebSocketUrl = (id: string): string | null => {
    if (typeof window === 'undefined') return null

    const token = getStoredAccessToken()
    if (!token) {
      console.error('[WebSocket] No auth token found')
      return null
    }

    // Determine protocol (ws or wss)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host

    return `${protocol}//${host}/api/v1/agents/${id}/ws?token=${token}`
  }

  /**
   * Send message through WebSocket
   */
  const send = (message: WsOutgoingMessage): boolean => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('[WebSocket] Cannot send - connection not open')
      return false
    }

    try {
      ws.send(JSON.stringify(message))
      return true
    } catch (err) {
      console.error('[WebSocket] Send error:', err)
      return false
    }
  }

  /**
   * Handle incoming WebSocket message
   */
  const handleMessage = (event: MessageEvent) => {
    try {
      const rawMessage = JSON.parse(event.data)
      
      // Standard WebSocket event format: { type: "...", data: {...} }
      const message: WsIncomingMessage = rawMessage

      switch (message.type) {
        case 'message_created': {
          const msgData = message.data
          
          const rawDialogId = msgData.dialog_id ?? msgData.session_id
          const dialogId = resolveDialogId(rawDialogId) ?? (rawDialogId ? String(rawDialogId) : null)

          if (!dialogId) {
            console.warn('[WebSocket] message_created without dialog_id/session_id')
            break
          }

          // Skip internal/tool messages — they should not appear in chat or sidebar
          const msgRole = typeof msgData.role === 'string' ? msgData.role.toLowerCase() : ''
          const internalRoles = ['tool', 'function', 'tool_result', 'function_result', 'tool_call', 'function_call', 'tool_use']
          if (internalRoles.includes(msgRole)) break
          // Also skip when content is a raw object (not string)
          if (typeof msgData.content === 'object' && msgData.content !== null) break

          const isActiveDialog = dialogId === activeDialogId.value

          // Extract user_info from message data
          const userInfo = msgData.user_info
          const platform = userInfo?.platform || (dialogId.startsWith('telegram:') ? 'telegram' : undefined)

          // Safely convert content to string for preview
          const contentStr = typeof msgData.content === 'string' ? msgData.content : ''

          // Update dialog sidebar
          dialogsStore.upsertDialog({
            id: dialogId,
            session_id: dialogId,
            last_message_preview: contentStr,
            last_message_at: msgData.created_at,
            is_new: !isActiveDialog,
            platform,
            user_info: userInfo
          })

          // Match optimistic message or add new
          const existingMessages = messagesStore.getMessages(dialogId)
          const pendingMessage = existingMessages.find(m =>
            m.status === 'sending' &&
            (m.role === 'user' || m.role === 'manager') &&
            m.content.trim() === contentStr.trim()
          )

          if (pendingMessage) {
            messagesStore.markMessageSent(dialogId, pendingMessage.id, msgData.id)
          } else {
            messagesStore.addIncomingMessage({ ...msgData, dialog_id: dialogId })
          }

          if (isActiveDialog) {
            dialogsStore.markAsRead(dialogId)
          }
          break
        }

        case 'dialog_updated': {
          dialogsStore.upsertDialog(message.data)
          break
        }

        case 'run_start': {
          const { run_id, dialog_id } = message.data
          const resolvedDialogId = resolveDialogId(dialog_id) ?? dialog_id
          currentRunId.value = run_id
          currentDialogId.value = resolvedDialogId

          messagesStore.handleRunStart(run_id, resolvedDialogId)
          dialogsStore.updateDialogStatus(resolvedDialogId, 'IN_PROGRESS')
          break
        }

        case 'run_result': {
          const { run_id, output, dialog_id } = message.data
          const resolvedDialogId = resolveDialogId(dialog_id) ?? dialog_id
          const isActiveDialog = resolvedDialogId === activeDialogId.value

          messagesStore.handleRunResult(run_id, resolvedDialogId, output)

          dialogsStore.upsertDialog({
            id: resolvedDialogId,
            last_message_preview: output.slice(0, 100),
            last_message_at: new Date().toISOString(),
            is_new: !isActiveDialog
          })
          dialogsStore.updateDialogStatus(resolvedDialogId, 'NORMAL')

          if (isActiveDialog) {
            dialogsStore.markAsRead(resolvedDialogId)
          }

          if (currentRunId.value === run_id) {
            currentRunId.value = null
            currentDialogId.value = null
          }
          break
        }

        case 'run_error': {
          const { run_id, error, dialog_id } = message.data
          const resolvedDialogId = resolveDialogId(dialog_id) ?? dialog_id

          messagesStore.handleRunError(run_id, resolvedDialogId, error)
          dialogsStore.updateDialogStatus(resolvedDialogId, 'ERROR')

          if (currentRunId.value === run_id) {
            currentRunId.value = null
            currentDialogId.value = null
          }
          break
        }

        case 'ping': {
          send({ type: 'pong' })
          resetPingTimeout()
          break
        }

        case 'error': {
          console.error('[WebSocket] Server error:', message.data.message)
          break
        }

        case 'status':
        case 'dialog_joined':
        case 'dialog_left':
          break

        default: {
          console.warn('[WebSocket] Unknown message type:', (message as any).type)
        }
      }
    } catch (err) {
      console.error('[WebSocket] Error parsing message:', err)
    }
  }

  /**
   * Reset ping timeout (server sends ping every 20s)
   */
  const resetPingTimeout = () => {
    if (pingTimeout) {
      clearTimeout(pingTimeout)
    }
    // If no ping received in 60s, connection might be dead
    pingTimeout = setTimeout(() => {
      console.warn('[WebSocket] No ping received in 60s, reconnecting...')
      reconnect()
    }, 60000)
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  const scheduleReconnect = () => {
    if (reconnectAttempts.value >= reconnectConfig.maxAttempts) {
      console.error('[WebSocket] Max reconnect attempts reached')
      connectionState.value = 'error'
      return
    }

    const delay = Math.min(
      reconnectConfig.baseDelay * Math.pow(2, reconnectAttempts.value),
      reconnectConfig.maxDelay
    )


    reconnectTimeout = setTimeout(() => {
      reconnectAttempts.value++
      connect()
    }, delay)
  }

  /**
   * Connect to WebSocket
   */
  const connect = () => {
    const id = unref(agentId)
    if (!id || typeof window === 'undefined') {
      console.warn('[WebSocket] Cannot connect - no agent ID or not in browser')
      return
    }

    // Close existing connection
    disconnect(false)

    const url = getWebSocketUrl(id)
    if (!url) return

    connectionState.value = 'connecting'

    try {
      ws = new WebSocket(url)

      ws.onopen = () => {
        connectionState.value = 'connected'
        reconnectAttempts.value = 0
        resetPingTimeout()
      }

      ws.onclose = (event) => {
        connectionState.value = 'disconnected'

        if (pingTimeout) {
          clearTimeout(pingTimeout)
          pingTimeout = null
        }

        // Don't reconnect if closed normally (code 1000) or unauthorized (1008)
        if (event.code !== 1000 && event.code !== 1008) {
          scheduleReconnect()
        } else if (event.code === 1008) {
          console.error('[WebSocket] Unauthorized - invalid token')
          connectionState.value = 'error'
        }
      }

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error)
        connectionState.value = 'error'
      }

      ws.onmessage = handleMessage
    } catch (err) {
      console.error('[WebSocket] Connection error:', err)
      connectionState.value = 'error'
      scheduleReconnect()
    }
  }

  /**
   * Disconnect from WebSocket
   */
  const disconnect = (clearReconnect = true) => {
    if (clearReconnect && reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }

    if (pingTimeout) {
      clearTimeout(pingTimeout)
      pingTimeout = null
    }

    if (ws) {
      ws.close(1000, 'Client closed')
      ws = null
    }

    activeDialogId.value = null

    if (clearReconnect) {
      connectionState.value = 'disconnected'
      reconnectAttempts.value = 0
    }
  }

  /**
   * Force reconnect
   */
  const reconnect = () => {
    disconnect(false)
    reconnectAttempts.value = 0
    connect()
  }

  // ===========================================
  // Public API methods
  // ===========================================

  /**
   * Send a message to a dialog
   */
  const sendMessage = (dialogId: string, content: string): boolean => {
    return send({
      type: 'send_message',
      dialog_id: dialogId,
      content
    })
  }

  /**
   * Join a dialog (subscribe to updates)
   */
  const joinDialog = (dialogId: string): boolean => {
    const joined = send({
      type: 'join_dialog',
      dialog_id: dialogId
    })
    if (joined) {
      activeDialogId.value = dialogId
    }
    return joined
  }

  /**
   * Leave a dialog (unsubscribe)
   */
  const leaveDialog = (dialogId: string): boolean => {
    const left = send({
      type: 'leave_dialog',
      dialog_id: dialogId
    })
    if (left && activeDialogId.value === dialogId) {
      activeDialogId.value = null
    }
    return left
  }

  /**
   * Request connection status
   */
  const getStatus = (): boolean => {
    return send({ type: 'get_status' })
  }

  // ===========================================
  // Lifecycle
  // ===========================================

  // Auto-connect when agentId changes
  watch(
    () => unref(agentId),
    (newId, oldId) => {
      if (newId !== oldId) {
        if (newId) {
          connect()
        } else {
          disconnect()
        }
      }
    },
    { immediate: options?.autoConnect !== false }
  )

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })

  // Computed helpers
  const isConnected = computed(() => connectionState.value === 'connected')
  const isConnecting = computed(() => connectionState.value === 'connecting')

  return {
    // State
    connectionState,
    isConnected,
    isConnecting,
    reconnectAttempts,

    // Actions
    connect,
    disconnect,
    reconnect,
    sendMessage,
    joinDialog,
    leaveDialog,
    getStatus
  }
}
