import { onUnmounted, watch, type ComputedRef, unref } from 'vue'
import { useDialogs } from './useDialogs'
import { useMessages } from './useMessages'
import { EventSourcePolyfill } from 'event-source-polyfill'
import { getStoredAccessToken } from '~/composables/authSessionManager'

/**
 * @deprecated Use useAgentWebSocket instead.
 * This SSE-based composable is kept for backward compatibility
 * and will be removed after full WebSocket migration.
 */
export const useAgentEvents = (agentId: string | null | ComputedRef<string | null>) => {
  const dialogsStore = useDialogs()
  const messagesStore = useMessages()
  
  let eventSource: EventSourcePolyfill | null = null

  const connect = () => {
    const id = unref(agentId)
    if (!id || typeof window === 'undefined') return
    
    // Close previous connection if it exists
    disconnect()

    const token = getStoredAccessToken()
    if (!token) {
      console.warn('[SSE] Отсутствует токен авторизации')
      return
    }
    const url = `/api/v1/agents/${id}/dialogs/events`

    console.log(`[SSE] Connecting to ${url}`)

    eventSource = new EventSourcePolyfill(url, {
      headers: {
        'Authorization': `Bearer ${token}`
      },
      withCredentials: true,
      heartbeatTimeout: 60000 // 1 minute
    })

    eventSource.addEventListener('message_created', (e: any) => {
      try {
        const message = JSON.parse(e.data)
        console.log('[SSE] message_created:', message)
        messagesStore.addIncomingMessage(message)
      } catch (err) {
        console.error('[SSE] Error parsing message_created data:', err)
      }
    })

    eventSource.addEventListener('dialog_updated', (e: any) => {
      try {
        const dialog = JSON.parse(e.data)
        console.log('[SSE] dialog_updated:', dialog)
        dialogsStore.upsertDialog(dialog)
      } catch (err) {
        console.error('[SSE] Error parsing dialog_updated data:', err)
      }
    })

    eventSource.onopen = () => {
      console.log('[SSE] Connection established')
    }

    eventSource.onerror = (err: any) => {
      console.error('[SSE] Connection error:', err)
      // Polyfill handles reconnection automatically by default
    }
  }

  const disconnect = () => {
    if (eventSource) {
      console.log('[SSE] Disconnecting')
      eventSource.close()
      eventSource = null
    }
  }

  // Reconnect when agentId changes
  watch(() => unref(agentId), (newId) => {
    if (newId) {
      connect()
    } else {
      disconnect()
    }
  }, { immediate: true })

  // Automatically disconnect on unmount
  onUnmounted(() => {
    disconnect()
  })

  return { connect, disconnect }
}
