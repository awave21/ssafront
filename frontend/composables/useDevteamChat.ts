import { ref, reactive } from 'vue'
import { useDevteamApi } from '~/composables/useDevteamApi'
import { useDevteamWebSocket } from '~/composables/useDevteamWebSocket'
import type {
  DevteamAgent,
  DevteamChat,
  DevteamMessage,
  DevteamTask,
  DevteamWsEvent,
} from '~/types/devteam'

// ─── Singleton state (shared across components) ───────────────────────────────

const agents = ref<DevteamAgent[]>([])
const chats = ref<DevteamChat[]>([])
const messagesByChat = reactive<Record<number, DevteamMessage[]>>({})
// Стримящийся текст агента до прихода message_created
const streamingByChat = reactive<Record<number, { role: string; content: string; toolCalls: { name: string; input: any; output: string | null }[] } | null>>({})
// Статус "агент печатает"
const typingByChat = reactive<Record<number, string | null>>({})

const api = useDevteamApi()

// ─── Init ─────────────────────────────────────────────────────────────────────

async function loadAgents() {
  if (agents.value.length > 0) return
  agents.value = await api.listAgents()
}

async function loadChats() {
  chats.value = await api.listChats()
}

async function loadMessages(chatId: number) {
  if (messagesByChat[chatId]) return
  const msgs = await api.getMessages(chatId, 0, 100)
  messagesByChat[chatId] = msgs
}

// ─── Chat operations ──────────────────────────────────────────────────────────

async function openDm(role: string): Promise<DevteamChat> {
  // Найти существующий DM с этой ролью
  const existing = chats.value.find(
    (c) => c.kind === 'dm' && c.agents.length === 1 && c.agents[0] === role,
  )
  if (existing) return existing

  const chat = await api.createChat('dm', [role])
  chats.value.unshift(chat)
  return chat
}

async function createGroupChat(agentRoles: string[], title?: string): Promise<DevteamChat> {
  const chat = await api.createChat('group', agentRoles, title)
  chats.value.unshift(chat)
  return chat
}

async function deleteChat(chatId: number) {
  await api.deleteChat(chatId)
  chats.value = chats.value.filter((c) => c.id !== chatId)
  delete messagesByChat[chatId]
}

// ─── Send message ─────────────────────────────────────────────────────────────

async function sendMessage(chatId: number, content: string): Promise<void> {
  const userMsg = await api.sendMessage(chatId, content)
  if (!messagesByChat[chatId]) messagesByChat[chatId] = []
  // Добавляем если ещё нет (WS может прийти чуть раньше)
  if (!messagesByChat[chatId].some((m) => m.id === userMsg.id)) {
    messagesByChat[chatId].push(userMsg)
  }
  // Обновляем updated_at у чата
  const chat = chats.value.find((c) => c.id === chatId)
  if (chat) chat.updated_at = new Date().toISOString()
}

// ─── WebSocket event handling ─────────────────────────────────────────────────

function handleWsEvent(chatId: number, event: DevteamWsEvent) {
  switch (event.type) {
    case 'message_created': {
      if (!messagesByChat[chatId]) messagesByChat[chatId] = []
      if (!messagesByChat[chatId].some((m) => m.id === event.message.id)) {
        messagesByChat[chatId].push(event.message)
      }
      // Сбрасываем стрим и typing
      streamingByChat[chatId] = null
      typingByChat[chatId] = null
      break
    }

    case 'agent_typing': {
      typingByChat[chatId] = event.role
      if (!streamingByChat[chatId]) {
        streamingByChat[chatId] = { role: event.role, content: '', toolCalls: [] }
      }
      break
    }

    case 'agent_chunk': {
      if (!streamingByChat[chatId]) {
        streamingByChat[chatId] = { role: event.role, content: '', toolCalls: [] }
      }
      streamingByChat[chatId]!.content += event.delta
      break
    }

    case 'tool_call': {
      if (!streamingByChat[chatId]) {
        streamingByChat[chatId] = { role: event.role, content: '', toolCalls: [] }
      }
      streamingByChat[chatId]!.toolCalls.push({
        name: event.tool,
        input: event.input,
        output: null,
      })
      break
    }

    case 'tool_result': {
      if (streamingByChat[chatId]?.toolCalls.length) {
        const tc = [...streamingByChat[chatId]!.toolCalls].reverse().find((t) => t.output === null)
        if (tc) tc.output = event.output
      }
      break
    }

    case 'task_status': {
      // Обновляем задачи — для простоты уведомляем через отдельный ref
      // Список задач можно загрузить через api.listTasks(chatId)
      break
    }

    case 'error': {
      console.error('[DevTeam WS]', event.message)
      typingByChat[chatId] = null
      streamingByChat[chatId] = null
      break
    }

    case 'pong':
      break
  }
}

// ─── Composable ───────────────────────────────────────────────────────────────

export const useDevteamChat = () => {
  return {
    // State
    agents,
    chats,
    messagesByChat,
    streamingByChat,
    typingByChat,
    // Methods
    loadAgents,
    loadChats,
    loadMessages,
    openDm,
    createGroupChat,
    deleteChat,
    sendMessage,
    handleWsEvent,
    // API
    api,
  }
}
