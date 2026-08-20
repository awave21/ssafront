import { computed, ref } from 'vue'
import { useApiFetch } from './useApiFetch'
import { getReadableErrorMessage } from '~/utils/api-errors'
import {
  buildActionCatalog,
  buildFunctionPresetCatalog,
  buildScenarioPresetCatalog,
} from '~/utils/assistantCapabilities'

export type AssistantSuggestionKind =
  | 'function'
  | 'scenario'
  | 'table'
  | 'knowledge'
  | 'prompt'
  | 'channel'

export type AssistantSuggestion = {
  kind: AssistantSuggestionKind
  title: string
  rationale: string
  preset_id: string | null
}

export type AssistantMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  suggestions?: AssistantSuggestion[]
  followups?: string[]
  failed?: boolean
}

type AssistantChatResponse = {
  message: string
  suggestions: AssistantSuggestion[]
  followups: string[]
  model: string
}

/** Сколько реплик отправляем в контекст. Столько же принимает бэкенд. */
const HISTORY_LIMIT = 20

const storageKey = (agentId: string) => `agent-assistant-messages-${agentId}`

/**
 * Куда ведёт карточка-предложение.
 *
 * Помощник ничего не создаёт: он присылает вид раздела и, если подходит,
 * id заготовки. Ссылку собираем здесь — бэкенду знать о роутинге незачем.
 */
export const suggestionRoute = (agentId: string, suggestion: AssistantSuggestion): string => {
  const preset = suggestion.preset_id ? `?preset=${encodeURIComponent(suggestion.preset_id)}` : ''
  switch (suggestion.kind) {
    case 'function':
      return `/agents/${agentId}/functions/new${preset}`
    case 'scenario':
      return `/agents/${agentId}/scenarios${preset}`
    case 'table':
      return `/agents/${agentId}/knowledge?knowledgeTab=tables`
    case 'knowledge':
      return `/agents/${agentId}/knowledge`
    case 'prompt':
      return `/agents/${agentId}/prompt`
    case 'channel':
      return `/agents/${agentId}/channels`
    default:
      return `/agents/${agentId}`
  }
}

export const useAgentAssistant = (agentId: string) => {
  const apiFetch = useApiFetch()

  const messages = ref<AssistantMessage[]>([])
  const isThinking = ref(false)
  const error = ref<string | null>(null)

  const isEmpty = computed(() => messages.value.length === 0)

  const nextId = () => `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`

  const persist = () => {
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(
        storageKey(agentId),
        JSON.stringify(messages.value.slice(-HISTORY_LIMIT * 2)),
      )
    } catch {
      // Переполненный localStorage не повод ронять чат.
    }
  }

  const restore = () => {
    if (typeof window === 'undefined') return
    try {
      const raw = window.localStorage.getItem(storageKey(agentId))
      if (!raw) return
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) messages.value = parsed
    } catch {
      messages.value = []
    }
  }

  const clear = () => {
    messages.value = []
    error.value = null
    persist()
  }

  const ask = async (text: string) => {
    const question = text.trim()
    if (!question || isThinking.value) return

    error.value = null
    messages.value.push({ id: nextId(), role: 'user', content: question })
    persist()
    isThinking.value = true

    try {
      const response = await apiFetch<AssistantChatResponse>(
        `/agents/${agentId}/assistant/chat`,
        {
          method: 'POST',
          body: {
            message: question,
            // Историю отдаём без карточек: модели нужен текст разговора,
            // а не то, какие кнопки мы под ним нарисовали.
            history: messages.value
              .slice(-HISTORY_LIMIT - 1, -1)
              .map((message) => ({ role: message.role, content: message.content })),
            actions: buildActionCatalog(),
            function_presets: buildFunctionPresetCatalog(),
            scenario_presets: buildScenarioPresetCatalog(),
          },
          // Мета-агент отвечает дольше обычного запроса: контекст большой.
          timeout: 120_000,
        },
      )

      messages.value.push({
        id: nextId(),
        role: 'assistant',
        content: response.message,
        suggestions: response.suggestions || [],
        followups: response.followups || [],
      })
    } catch (err: any) {
      const message = getReadableErrorMessage(err, 'Помощник не ответил. Попробуйте ещё раз.')
      error.value = message
      messages.value.push({ id: nextId(), role: 'assistant', content: message, failed: true })
    } finally {
      isThinking.value = false
      persist()
    }
  }

  restore()

  return { messages, isThinking, isEmpty, error, ask, clear }
}
