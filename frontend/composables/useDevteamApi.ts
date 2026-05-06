import type { DevteamAgent, DevteamChat, DevteamMessage, DevteamTask } from '~/types/devteam'

const BASE = '/api/devteam'

function devteamFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const config = useRuntimeConfig()
  const token = config.public.devteamToken as string

  return $fetch<T>(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(opts.headers ?? {}),
    },
  })
}

export const useDevteamApi = () => {
  const listAgents = (): Promise<DevteamAgent[]> =>
    devteamFetch('/agents')

  const listChats = (): Promise<DevteamChat[]> =>
    devteamFetch('/chats')

  const createChat = (kind: 'dm' | 'group', agents: string[], title?: string): Promise<DevteamChat> =>
    devteamFetch('/chats', {
      method: 'POST',
      body: JSON.stringify({ kind, agents, title }),
    })

  const getChat = (chatId: number): Promise<DevteamChat> =>
    devteamFetch(`/chats/${chatId}`)

  const deleteChat = (chatId: number): Promise<{ ok: boolean }> =>
    devteamFetch(`/chats/${chatId}`, { method: 'DELETE' })

  const getMessages = (chatId: number, offset = 0, limit = 50): Promise<DevteamMessage[]> =>
    devteamFetch(`/chats/${chatId}/messages?offset=${offset}&limit=${limit}`)

  const sendMessage = (chatId: number, content: string): Promise<DevteamMessage> =>
    devteamFetch(`/chats/${chatId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    })

  const listTasks = (chatId?: number): Promise<DevteamTask[]> => {
    const qs = chatId != null ? `?chat_id=${chatId}` : ''
    return devteamFetch(`/tasks${qs}`)
  }

  return { listAgents, listChats, createChat, getChat, deleteChat, getMessages, sendMessage, listTasks }
}
