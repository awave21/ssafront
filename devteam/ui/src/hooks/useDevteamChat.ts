import { useState, useCallback, useRef } from 'react'
import { devteamApi } from '@/api/devteamApi'
import type {
  DevteamAgent,
  DevteamChat,
  DevteamMessage,
  StreamingMessage,
  WsEvent,
} from '@/types/devteam'

export interface ChatState {
  agents: DevteamAgent[]
  chats: DevteamChat[]
  messages: DevteamMessage[]
  streaming: StreamingMessage | null
  typingRole: string | null
  loading: boolean
  sending: boolean
}

export function useDevteamChat() {
  const [agents, setAgents] = useState<DevteamAgent[]>([])
  const [chats, setChats] = useState<DevteamChat[]>([])
  const [messages, setMessages] = useState<DevteamMessage[]>([])
  const [streaming, setStreaming] = useState<StreamingMessage | null>(null)
  const [typingRole, setTypingRole] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [waitingForAgent, setWaitingForAgent] = useState(false)
  const messageIdsRef = useRef(new Set<number>())

  const loadAgents = useCallback(async () => {
    const data = await devteamApi.listAgents()
    setAgents(data)
    return data
  }, [])

  const loadChats = useCallback(async () => {
    const data = await devteamApi.listChats()
    setChats(data)
    return data
  }, [])

  const loadMessages = useCallback(async (chatId: number) => {
    setLoading(true)
    messageIdsRef.current.clear()
    try {
      const data = await devteamApi.getMessages(chatId)
      data.forEach((m) => messageIdsRef.current.add(m.id))
      setMessages(data)
    } finally {
      setLoading(false)
    }
  }, [])

  const openDm = useCallback(
    async (role: string, existingChats: DevteamChat[]) => {
      const existing = existingChats.find(
        (c) => c.kind === 'dm' && c.agents.length === 1 && c.agents[0] === role,
      )
      if (existing) return existing
      const chat = await devteamApi.createChat('dm', [role])
      setChats((prev) => [chat, ...prev])
      return chat
    },
    [],
  )

  const createGroupChat = useCallback(async (roles: string[], title?: string) => {
    const chat = await devteamApi.createChat('group', roles, title)
    setChats((prev) => [chat, ...prev])
    return chat
  }, [])

  const deleteChat = useCallback(async (chatId: number) => {
    await devteamApi.deleteChat(chatId)
    setChats((prev) => prev.filter((c) => c.id !== chatId))
  }, [])

  const updateChatAgents = useCallback(async (chatId: number, agents: string[]) => {
    const updated = await devteamApi.updateChat(chatId, agents)
    setChats((prev) => prev.map((c) => (c.id === chatId ? { ...c, agents: updated.agents } : c)))
    return updated
  }, [])

  const sendMessage = useCallback(async (chatId: number, content: string, replyToId?: number) => {
    setSending(true)
    setWaitingForAgent(true)
    try {
      const msg = await devteamApi.sendMessage(chatId, content, replyToId)
      if (!messageIdsRef.current.has(msg.id)) {
        messageIdsRef.current.add(msg.id)
        setMessages((prev) => [...prev, msg])
      }
      setChats((prev) =>
        prev.map((c) => (c.id === chatId ? { ...c, updated_at: new Date().toISOString() } : c)),
      )
    } finally {
      setSending(false)
      // waitingForAgent остаётся true — сбрасывается при первом WS-событии от агента
    }
  }, [])

  const handleWsEvent = useCallback((event: WsEvent) => {
    switch (event.type) {
      case 'message_created':
        setWaitingForAgent(false)
        if (!messageIdsRef.current.has(event.message.id)) {
          messageIdsRef.current.add(event.message.id)
          setMessages((prev) => [...prev, event.message])
        }
        setStreaming(null)
        setTypingRole(null)
        break

      case 'agent_typing':
        setWaitingForAgent(false)
        setTypingRole(event.role)
        setStreaming({ role: event.role, content: '', toolCalls: [] })
        break

      case 'agent_chunk':
        setWaitingForAgent(false)
        setStreaming((prev) =>
          prev
            ? { ...prev, role: event.role, content: prev.content + event.delta }
            : { role: event.role, content: event.delta, toolCalls: [] },
        )
        break

      case 'tool_call':
        setStreaming((prev) => {
          if (!prev) return { role: event.role, content: '', toolCalls: [{ name: event.tool, input: event.input, output: null }] }
          return { ...prev, toolCalls: [...prev.toolCalls, { name: event.tool, input: event.input, output: null }] }
        })
        break

      case 'tool_result':
        setStreaming((prev) => {
          if (!prev) return prev
          const toolCalls = [...prev.toolCalls]
          const last = [...toolCalls].reverse().find((t) => t.output === null)
          if (last) last.output = event.output
          return { ...prev, toolCalls }
        })
        break

      case 'error':
        setWaitingForAgent(false)
        setTypingRole(null)
        setStreaming(null)
        console.error('[DevTeam WS error]', event.message)
        break
    }
  }, [])

  const clearChatState = useCallback(() => {
    setStreaming(null)
    setWaitingForAgent(false)
    setSending(false)
    setTypingRole(null)
  }, [])

  return {
    agents,
    chats,
    messages,
    streaming,
    typingRole,
    loading,
    sending,
    waitingForAgent,
    loadAgents,
    loadChats,
    loadMessages,
    openDm,
    createGroupChat,
    deleteChat,
    updateChatAgents,
    sendMessage,
    handleWsEvent,
    clearChatState,
    setMessages,
    setChats,
  }
}
