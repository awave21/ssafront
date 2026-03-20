import { ref } from 'vue'

type SessionMap = Record<string, string>
const STORAGE_KEY = 'agent-chat-sessions'
const isBrowser = typeof window !== 'undefined'

const readStoredSessions = (): SessionMap => {
  if (!isBrowser) return {}
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return stored ? (JSON.parse(stored) as SessionMap) : {}
  } catch (error) {
    console.error('Failed to parse stored agent sessions:', error)
    return {}
  }
}

const writeStoredSessions = (sessions: SessionMap) => {
  if (!isBrowser) return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
  } catch (error) {
    console.error('Failed to persist agent sessions:', error)
  }
}

export const useAgentSession = () => {
  const sessions = ref<SessionMap>(isBrowser ? readStoredSessions() : {})

  const persist = (payload: SessionMap) => {
    sessions.value = payload
    writeStoredSessions(payload)
  }

  const getSessionId = (agentId: string) => sessions.value[agentId] ?? null

  const setSessionId = (agentId: string, sessionId: string) => {
    persist({ ...sessions.value, [agentId]: sessionId })
  }

  const clearSessionId = (agentId: string) => {
    if (!sessions.value[agentId]) return
    const { [agentId]: _, ...rest } = sessions.value
    persist(rest)
  }

  return {
    getSessionId,
    setSessionId,
    clearSessionId
  }
}
