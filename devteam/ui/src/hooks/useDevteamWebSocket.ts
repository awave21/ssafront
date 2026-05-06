import { useEffect, useRef, useCallback } from 'react'
import { getWsUrl } from '@/api/devteamApi'
import type { WsEvent } from '@/types/devteam'

const MAX_RECONNECT = 5
const BASE_DELAY = 1000
const MAX_DELAY = 16000

export function useDevteamWebSocket(
  chatId: number | null,
  onEvent: (event: WsEvent) => void,
) {
  const wsRef = useRef<WebSocket | null>(null)
  const attemptsRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const destroyedRef = useRef(false)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const connect = useCallback(() => {
    if (chatId == null || destroyedRef.current) return

    const ws = new WebSocket(getWsUrl(chatId))
    wsRef.current = ws

    ws.onopen = () => {
      attemptsRef.current = 0
    }

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as WsEvent
        if (event.type === 'pong') return
        onEventRef.current(event)
      } catch {
        // ignore
      }
    }

    ws.onclose = () => {
      if (destroyedRef.current) return
      if (attemptsRef.current < MAX_RECONNECT) {
        const delay = Math.min(BASE_DELAY * 2 ** attemptsRef.current, MAX_DELAY)
        attemptsRef.current++
        timerRef.current = setTimeout(connect, delay)
      }
    }

    // ping every 25s
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 25_000)

    ws.addEventListener('close', () => clearInterval(ping))
  }, [chatId])

  useEffect(() => {
    destroyedRef.current = false
    attemptsRef.current = 0
    connect()

    return () => {
      destroyedRef.current = true
      if (timerRef.current) clearTimeout(timerRef.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connect])
}
