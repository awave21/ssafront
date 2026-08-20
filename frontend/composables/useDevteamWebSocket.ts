import { ref, onUnmounted } from 'vue'
import type { DevteamWsEvent, DevteamStreamingMessage } from '~/types/devteam'

type WsState = 'disconnected' | 'connecting' | 'connected' | 'error'

const MAX_RECONNECT = 5
const BASE_DELAY = 1000
const MAX_DELAY = 16000

export const useDevteamWebSocket = (
  chatId: number,
  onEvent: (event: DevteamWsEvent) => void,
) => {
  const state = ref<WsState>('disconnected')
  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let pingTimer: ReturnType<typeof setTimeout> | null = null
  let destroyed = false

  function getUrl(): string {
    const config = useRuntimeConfig()
    const token = config.public.devteamToken as string
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/api/devteam/chats/${chatId}/ws?token=${token}`
  }

  function schedulePing() {
    pingTimer = setTimeout(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
      schedulePing()
    }, 30_000)
  }

  function connect() {
    if (destroyed) return
    state.value = 'connecting'
    ws = new WebSocket(getUrl())

    ws.onopen = () => {
      state.value = 'connected'
      reconnectAttempts = 0
      schedulePing()
    }

    ws.onmessage = (e: MessageEvent) => {
      try {
        const event = JSON.parse(e.data) as DevteamWsEvent
        onEvent(event)
      } catch {
        // ignore invalid JSON
      }
    }

    ws.onclose = () => {
      if (pingTimer) clearTimeout(pingTimer)
      if (destroyed) return
      state.value = 'disconnected'
      scheduleReconnect()
    }

    ws.onerror = () => {
      state.value = 'error'
    }
  }

  function scheduleReconnect() {
    if (reconnectAttempts >= MAX_RECONNECT) return
    const delay = Math.min(BASE_DELAY * 2 ** reconnectAttempts, MAX_DELAY)
    reconnectAttempts++
    reconnectTimer = setTimeout(connect, delay)
  }

  function disconnect() {
    destroyed = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (pingTimer) clearTimeout(pingTimer)
    ws?.close()
    ws = null
    state.value = 'disconnected'
  }

  onUnmounted(disconnect)

  return { state, connect, disconnect }
}
