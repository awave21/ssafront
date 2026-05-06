import type { DevteamAgent, DevteamChat, DevteamMessage, DevteamTask } from '@/types/devteam'

const BASE = '/api/devteam'
const TOKEN = import.meta.env.VITE_DEVTEAM_TOKEN ?? 'devteam-secret'

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${TOKEN}`,
      ...(init.headers ?? {}),
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const devteamApi = {
  listAgents: () => apiFetch<DevteamAgent[]>('/agents'),

  listChats: () => apiFetch<DevteamChat[]>('/chats'),

  createChat: (kind: 'dm' | 'group', agents: string[], title?: string) =>
    apiFetch<DevteamChat>('/chats', {
      method: 'POST',
      body: JSON.stringify({ kind, agents, title }),
    }),

  getChat: (id: number) => apiFetch<DevteamChat>(`/chats/${id}`),

  deleteChat: (id: number) => apiFetch<{ ok: boolean }>(`/chats/${id}`, { method: 'DELETE' }),

  updateChat: (id: number, agents: string[], title?: string) =>
    apiFetch<DevteamChat>(`/chats/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ agents, title }),
    }),

  getMessages: (chatId: number, offset = 0, limit = 100) =>
    apiFetch<DevteamMessage[]>(`/chats/${chatId}/messages?offset=${offset}&limit=${limit}`),

  sendMessage: (chatId: number, content: string, replyToId?: number) =>
    apiFetch<DevteamMessage>(`/chats/${chatId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, reply_to_id: replyToId ?? null }),
    }),

  listTasks: (chatId?: number) => {
    const qs = chatId != null ? `?chat_id=${chatId}` : ''
    return apiFetch<DevteamTask[]>(`/tasks${qs}`)
  },
}

export function getWsUrl(chatId: number): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/api/devteam/chats/${chatId}/ws?token=${TOKEN}`
}
