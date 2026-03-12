import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { watchDebounced } from '@vueuse/core'
import { useAgents, type Agent, type AgentStatus, type SqnsResource, type SqnsService, type SqnsStatus } from '~/composables/useAgents'
import { useApiFetch } from '~/composables/useApiFetch'
import { useAuth } from '~/composables/useAuth'
import { useDirectories } from '~/composables/useDirectories'
import { useSystemPromptHistory } from '~/composables/useSystemPromptHistory'
import { useAgentSession } from '~/composables/useAgentSession'
import { useToast } from '~/composables/useToast'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { Tool, ToolBinding } from '~/types/tool'

type AgentForm = {
  name: string
  system_prompt: string
  model: string
  timezone: string
  status: AgentStatus
  is_disabled: boolean
  llm_params: {
    temperature: number
    max_tokens: number
  }
}

type ChannelTypePath = 'telegram' | 'telegram_phone' | 'whatsapp' | 'max'
type ChannelTypePublic = 'Telegram_Bot' | 'Telegram_Phone' | 'Whatsapp_Phone' | 'Max_Phone'
type PhoneChannelTypePath = 'telegram_phone' | 'whatsapp' | 'max'

type AgentChannelRecord = {
  id: string
  type: ChannelTypePath
  telegram_bot_token?: string | null
  telegram_webhook_enabled?: boolean | null
  telegram_webhook_endpoint?: string | null
  is_authorized?: boolean | null
}

type ChannelAuthQrResponse = {
  status: string
  qr_code: string
  uuid?: string | null
  time?: string | null
  timestamp?: number | null
}

type TelegramChannel = {
  id?: string
  bot_token?: string | null
  webhook_enabled?: boolean
  webhook_endpoint?: string | null
} | null

type ChatMessage = {
  role: 'user' | 'agent'
  content: string
  run_id?: string | null
  tokens?: {
    prompt?: number | null
    completion?: number | null
    total?: number | null
  }
  tools_called?: Array<{
    name: string
    tool_call_id: string | null
    args: Record<string, unknown>
  }>
}

type ToolCallView = {
  name: string
  tool_call_id: string | null
  args: Record<string, unknown>
}

type PromptSidebarToolSource = 'sqns' | 'knowledge' | 'functions' | 'webhook'

type PromptSidebarTool = {
  name: string
  description?: string
  source: PromptSidebarToolSource
}

type PromptSidebarToolGroup = {
  id: PromptSidebarToolSource
  label: string
  tools: PromptSidebarTool[]
}

const normalizeToolArgs = (raw: unknown): Record<string, unknown> => {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed as Record<string, unknown>
    } catch {
      return {}
    }
  }
  return {}
}

const collectCurrentTurnToolCallKeys = (messagesPayload: unknown): Set<string> => {
  const keys = new Set<string>()
  if (!Array.isArray(messagesPayload)) return keys
  for (const msg of messagesPayload) {
    if (!msg || typeof msg !== 'object') continue
    const parts = (msg as any).parts
    if (!Array.isArray(parts)) continue
    for (const part of parts) {
      if (!part || typeof part !== 'object') continue
      const kind = String((part as any).part_kind || (part as any).partKind || '')
      if (kind !== 'tool-call' && kind !== 'tool_call') continue
      const toolName = String((part as any).tool_name || (part as any).toolName || '')
      if (!toolName) continue
      const callIdRaw = (part as any).tool_call_id ?? (part as any).toolCallId ?? (part as any).id ?? null
      const callId = callIdRaw == null ? null : String(callIdRaw)
      const args = normalizeToolArgs((part as any).args ?? (part as any).arguments)
      if (callId) {
        keys.add(`id:${callId}`)
      } else {
        const argsKey = JSON.stringify(args, Object.keys(args).sort())
        keys.add(`payload:${toolName}:${argsKey}`)
      }
    }
  }
  return keys
}

const filterToolsCalledForCurrentTurn = (responsePayload: any): ToolCallView[] | undefined => {
  const rawTools = Array.isArray(responsePayload?.tools_called) ? responsePayload.tools_called : []
  if (!rawTools.length) return undefined

  const allowed = collectCurrentTurnToolCallKeys(responsePayload?.messages)
  if (!allowed.size) return undefined

  const filtered = rawTools.filter((item: any) => {
    if (!item || typeof item !== 'object') return false
    const toolName = String(item.name || '')
    if (!toolName) return false
    const toolCallId = item.tool_call_id == null ? null : String(item.tool_call_id)
    if (toolCallId) return allowed.has(`id:${toolCallId}`)
    const args = normalizeToolArgs(item.args)
    const argsKey = JSON.stringify(args, Object.keys(args).sort())
    return allowed.has(`payload:${toolName}:${argsKey}`)
  })

  return filtered.length ? filtered : undefined
}

const createEmptyForm = (): AgentForm => ({
  name: '',
  system_prompt: '',
  model: '',
  timezone: 'Europe/Moscow',
  status: 'draft',
  is_disabled: false,
  llm_params: {
    temperature: 0.7,
    max_tokens: 1000
  }
})

const buildForm = (agent: Agent): AgentForm => ({
  name: agent.name,
  system_prompt: agent.system_prompt,
  model: agent.model,
  timezone: agent.timezone ?? 'Europe/Moscow',
  status: agent.status,
  is_disabled: Boolean(agent.is_disabled),
  llm_params: {
    temperature: agent.llm_params?.temperature ?? 0.7,
    max_tokens: agent.llm_params?.max_tokens ?? 1000
  }
})

export const useAgentEditorStore = defineStore('agentEditor', () => {
  const { token } = useAuth()
  const apiFetch = useApiFetch()
  const { success: toastSuccess, error: toastError } = useToast()
  const {
    getAgent,
    updateAgent,
    deleteAgent,
    fetchSqnsStatus,
    enableSqns,
    disableSqns,
    fetchSqnsResources,
    fetchSqnsServices
  } = useAgents()
  const { getSessionId, setSessionId, clearSessionId } = useAgentSession()

  const agentId = ref<string | null>(null)
  const agent = ref<Agent | null>(null)
  const form = ref<AgentForm>(createEmptyForm())
  const isLoaded = ref(false)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const isDeleting = ref(false)
  const error = ref<string | null>(null)

  const isPromptFullscreen = ref(false)
  
  // Auto-save state
  const isAutoSaving = ref(false)
  const lastAutoSavedAt = ref<Date | null>(null)
  const isPromptFocused = ref(false)

  const boundTools = ref<ToolBinding[]>([])
  const isLoadingTools = ref(false)
  const toolsLoaded = ref(false)

  const channels = ref<AgentChannelRecord[]>([])
  const telegramChannel = ref<TelegramChannel>(null)
  const telegramPhoneChannel = computed(() => channels.value.find((ch) => ch.type === 'telegram_phone') ?? null)
  const whatsappPhoneChannel = computed(() => channels.value.find((ch) => ch.type === 'whatsapp') ?? null)
  const maxPhoneChannel = computed(() => channels.value.find((ch) => ch.type === 'max') ?? null)
  const isLoadingChannels = ref(false)
  const channelsLoaded = ref(false)

  const directoriesComposable = ref<ReturnType<typeof useDirectories> | null>(null)
  const directoriesLoaded = ref(false)

  const promptHistory = ref<ReturnType<typeof useSystemPromptHistory> | null>(null)
  const promptHistoryLoaded = ref(false)

  const sqnsStatus = ref<SqnsStatus | null>(null)
  const sqnsResources = ref<SqnsResource[]>([])
  const sqnsServices = ref<SqnsService[]>([])
  const sqnsError = ref<string | null>(null)
  const sqnsStatusLoaded = ref(false)
  const sqnsHintsLoaded = ref(false)

  const messages = ref<ChatMessage[]>([])
  const userInput = ref('')
  const isTyping = ref(false)
  const currentSessionId = ref<string | null>(null)
  const chatLoaded = ref(false)

  const STORAGE_MESSAGES_KEY = 'agent-chat-messages'

  const resetState = () => {
    agent.value = null
    form.value = createEmptyForm()
    isLoaded.value = false
    isLoading.value = false
    isSaving.value = false
    isDeleting.value = false
    error.value = null

    isPromptFullscreen.value = false
    isAutoSaving.value = false
    lastAutoSavedAt.value = null
    isPromptFocused.value = false

    boundTools.value = []
    isLoadingTools.value = false
    toolsLoaded.value = false

    channels.value = []
    telegramChannel.value = null
    isLoadingChannels.value = false
    channelsLoaded.value = false

    directoriesLoaded.value = false
    directoriesComposable.value = null

    promptHistoryLoaded.value = false
    promptHistory.value = null

    sqnsStatus.value = null
    sqnsResources.value = []
    sqnsServices.value = []
    sqnsError.value = null
    sqnsStatusLoaded.value = false
    sqnsHintsLoaded.value = false

    messages.value = []
    userInput.value = ''
    isTyping.value = false
    currentSessionId.value = null
    chatLoaded.value = false
  }

  const setAgentId = (id: string) => {
    if (agentId.value === id) return
    agentId.value = id
    resetState()
    directoriesComposable.value = useDirectories(id)
    promptHistory.value = useSystemPromptHistory(() => id)
  }

  const ensureAgentLoaded = async (id: string) => {
    if (!id) return
    if (agentId.value !== id) setAgentId(id)
    if (isLoaded.value || isLoading.value) return

    try {
      isLoading.value = true
      error.value = null
      const data = await getAgent(id)
      agent.value = data
      form.value = buildForm(data)
      isLoaded.value = true
    } catch (err: any) {
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить агента')
    } finally {
      isLoading.value = false
    }
  }

  const saveAgent = async () => {
    if (!agent.value) return false
    try {
      isSaving.value = true
      const updated = await updateAgent(agent.value.id, form.value)
      agent.value = updated
      form.value = buildForm(updated)
      toastSuccess('Изменения сохранены', 'Агент успешно обновлен')
      if (promptHistoryLoaded.value && promptHistory.value) {
        promptHistory.value.fetchHistory()
      }
      return true
    } catch (err: any) {
      toastError('Ошибка сохранения', getReadableErrorMessage(err, 'Не удалось сохранить изменения'))
      return false
    } finally {
      isSaving.value = false
    }
  }

  // Auto-save prompt without toast notifications
  const autoSavePrompt = async () => {
    if (!agent.value || !isLoaded.value) return false
    
    // Check if there are actually changes
    if (form.value.system_prompt === agent.value.system_prompt) return false
    
    try {
      isAutoSaving.value = true
      const updated = await updateAgent(agent.value.id, { system_prompt: form.value.system_prompt })
      agent.value = updated
      lastAutoSavedAt.value = new Date()
      
      // Refresh history if loaded
      if (promptHistoryLoaded.value && promptHistory.value) {
        promptHistory.value.fetchHistory()
      }
      return true
    } catch (err: any) {
      console.error('Auto-save failed:', err)
      return false
    } finally {
      isAutoSaving.value = false
    }
  }

  // Auto-save any field without toast notifications
  const autoSaveField = async (updates: Partial<AgentForm>) => {
    if (!agent.value || !isLoaded.value) return false
    
    try {
      isAutoSaving.value = true
      const updated = await updateAgent(agent.value.id, updates)
      agent.value = updated
      
      // Update form with new values
      Object.assign(form.value, updates)
      
      lastAutoSavedAt.value = new Date()
      
      // Refresh history if prompt was updated
      if (updates.system_prompt && promptHistoryLoaded.value && promptHistory.value) {
        promptHistory.value.fetchHistory()
      }
      return true
    } catch (err: any) {
      console.error('Auto-save failed:', err)
      return false
    } finally {
      isAutoSaving.value = false
    }
  }

  const removeAgent = async () => {
    if (!agent.value) return false
    try {
      isDeleting.value = true
      await deleteAgent(agent.value.id)
      return true
    } catch (err: any) {
      toastError('Ошибка удаления', getReadableErrorMessage(err, 'Не удалось удалить агента'))
      return false
    } finally {
      isDeleting.value = false
    }
  }

  const resetForm = () => {
    if (!agent.value) return
    form.value = buildForm(agent.value)
  }

  const resetPrompt = () => {
    form.value.system_prompt = agent.value?.system_prompt || ''
  }

  const fetchToolsData = async () => {
    if (!agent.value) return
    try {
      isLoadingTools.value = true
      const currentBindings = await apiFetch<ToolBinding[]>(
        `/agents/${agent.value.id}/tools/details`,
        { headers: { Authorization: `Bearer ${token.value}` } }
      )
      boundTools.value = currentBindings
      toolsLoaded.value = true
    } catch (err) {
      console.error('Failed to fetch tools:', err)
    } finally {
      isLoadingTools.value = false
    }
  }

  const ensureToolsLoaded = async () => {
    if (toolsLoaded.value || isLoadingTools.value) return
    await fetchToolsData()
  }

  const toggleTool = async (tool: Tool) => {
    if (!agent.value) return
    const isBound = boundTools.value.some(bt => bt.tool_id === tool.id)

    try {
      if (isBound) {
        await apiFetch(`/agents/${agent.value.id}/tools/${tool.id}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token.value}` }
        })
      } else {
        await apiFetch(`/agents/${agent.value.id}/tools/${tool.id}`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token.value}`,
            'Content-Type': 'application/json'
          },
          body: {
            permission_scope: 'read',
            timeout_ms: 15000
          }
        })
      }
      await fetchToolsData()
    } catch (err) {
      console.error('Failed to toggle tool:', err)
    }
  }

  const fetchChannels = async () => {
    if (!agent.value) return
    isLoadingChannels.value = true
    try {
      const fetchedChannels = await apiFetch<AgentChannelRecord[]>(`/agents/${agent.value.id}/channels/active`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${token.value}` }
      })
      channels.value = fetchedChannels
      const tg = fetchedChannels.find((ch) => ch.type === 'telegram')
      telegramChannel.value = tg ? {
        id: tg.id,
        bot_token: tg.telegram_bot_token ?? null,
        webhook_enabled: Boolean(tg.telegram_webhook_enabled),
        webhook_endpoint: tg.telegram_webhook_endpoint ?? null
      } : null
      channelsLoaded.value = true
    } catch (err: any) {
      console.error('Failed to fetch channels:', err)
      channels.value = []
      telegramChannel.value = null
    } finally {
      isLoadingChannels.value = false
    }
  }

  const ensureChannelsLoaded = async () => {
    if (channelsLoaded.value || isLoadingChannels.value) return
    await fetchChannels()
  }

  const connectChannel = async (payload: {
    type: ChannelTypePublic
    telegram_bot_token?: string | null
    whatsapp_phone?: string | null
  }) => {
    if (!agent.value) return false
    await apiFetch(`/agents/${agent.value.id}/channels`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token.value}`,
        'Content-Type': 'application/json'
      },
      body: payload
    })
    await fetchChannels()
    return true
  }

  const disconnectChannel = async (channelType: ChannelTypePath) => {
    if (!agent.value) return false
    await apiFetch(`/agents/${agent.value.id}/channels/${channelType}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token.value}` }
    })
    await fetchChannels()
    return true
  }

  const fetchChannelAuthQr = async (channelType: PhoneChannelTypePath): Promise<ChannelAuthQrResponse> => {
    if (!agent.value) {
      throw new Error('Агент не выбран')
    }
    return await apiFetch<ChannelAuthQrResponse>(`/agents/${agent.value.id}/channels/${channelType}/auth/qr`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${token.value}` }
    })
  }

  const ensureDirectoriesLoaded = async () => {
    if (!directoriesComposable.value || directoriesLoaded.value) return
    await directoriesComposable.value.fetchDirectories()
    directoriesLoaded.value = true
  }

  const loadSqnsStatusForAgent = async () => {
    if (!agent.value) return
    try {
      sqnsError.value = null
      const status = await fetchSqnsStatus(agent.value.id)
      sqnsStatus.value = status
      sqnsStatusLoaded.value = true
    } catch (err: any) {
      if (err?.statusCode === 404) {
        sqnsStatusLoaded.value = true
        return
      }
      sqnsError.value = getReadableErrorMessage(err, 'Не удалось загрузить статус SQNS')
    }
  }

  const ensureSqnsStatusLoaded = async () => {
    if (sqnsStatusLoaded.value) return
    await loadSqnsStatusForAgent()
  }

  const ensureSqnsHints = async () => {
    if (sqnsHintsLoaded.value || !agent.value || !sqnsStatus.value?.sqnsEnabled) return
    try {
      const [resources, services] = await Promise.all([
        fetchSqnsResources(agent.value.id),
        fetchSqnsServices(agent.value.id)
      ])
      sqnsResources.value = resources
      sqnsServices.value = services
      sqnsHintsLoaded.value = true
    } catch (err: any) {
      if (err?.statusCode === 400 || err?.statusCode === 404) {
        return
      }
      sqnsError.value = getReadableErrorMessage(err, 'Не удалось загрузить подсказки SQNS')
    }
  }

  const enableSqnsIntegration = async (payload: {
    email: string
    password: string
    defaultResourceId?: number
  }) => {
    if (!agent.value) return false
    try {
      await enableSqns(agent.value.id, {
        host: 'crmexchange.1denta.ru',
        email: payload.email,
        password: payload.password,
        defaultResourceId: payload.defaultResourceId
      })
      sqnsHintsLoaded.value = false
      await loadSqnsStatusForAgent()
      return true
    } catch (err: any) {
      sqnsError.value = getReadableErrorMessage(err, 'Не удалось включить интеграцию SQNS')
      return false
    }
  }

  const disableSqnsIntegration = async () => {
    if (!agent.value) return false
    try {
      await disableSqns(agent.value.id)
      sqnsHintsLoaded.value = false
      sqnsResources.value = []
      sqnsServices.value = []
      await loadSqnsStatusForAgent()
      return true
    } catch (err: any) {
      sqnsError.value = getReadableErrorMessage(err, 'Не удалось отключить интеграцию SQNS')
      return false
    }
  }

  const ensurePromptHistoryLoaded = async () => {
    if (!promptHistory.value || promptHistoryLoaded.value) return
    try {
      await promptHistory.value.fetchHistory()
      promptHistoryLoaded.value = true
    } catch (err) {
      promptHistoryLoaded.value = false
    }
  }

  const loadChatMessages = () => {
    if (typeof window === 'undefined' || !agent.value) return
    const stored = localStorage.getItem(`${STORAGE_MESSAGES_KEY}-${agent.value.id}`)
    if (!stored) return
    try {
      messages.value = JSON.parse(stored)
    } catch (err) {
      console.error('Failed to parse stored messages:', err)
      messages.value = []
    }
  }

  const saveChatMessages = () => {
    if (typeof window === 'undefined' || !agent.value) return
    localStorage.setItem(`${STORAGE_MESSAGES_KEY}-${agent.value.id}`, JSON.stringify(messages.value))
  }

  const ensureChatLoaded = () => {
    if (chatLoaded.value || !agent.value) return
    loadChatMessages()
    currentSessionId.value = getSessionId(agent.value.id)
    chatLoaded.value = true
  }

  const sendMessage = async () => {
    if (!userInput.value.trim() || isTyping.value || !agent.value) return false

    if (agent.value.is_disabled) {
      toastError('Агент отключен', 'Агент временно отключен и не может инициировать новые ответы')
      return false
    }

    const userMessage = userInput.value.trim()
    userInput.value = ''
    messages.value.push({ role: 'user', content: userMessage })

    try {
      isTyping.value = true
      const payload: Record<string, unknown> = {
        agent_id: agent.value.id,
        input_message: userMessage
      }
      if (currentSessionId.value) {
        payload.session_id = currentSessionId.value
      }

      const response = await apiFetch<any>('/runs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: payload
      })

      if (response) {
        if (response.session_id && agent.value) {
          setSessionId(agent.value.id, response.session_id)
          currentSessionId.value = response.session_id
        }

        const hasTokens = response.prompt_tokens !== null && response.prompt_tokens !== undefined
          || response.completion_tokens !== null && response.completion_tokens !== undefined
          || response.total_tokens !== null && response.total_tokens !== undefined

        const tokens = hasTokens ? {
          prompt: response.prompt_tokens ?? null,
          completion: response.completion_tokens ?? null,
          total: response.total_tokens ?? null
        } : undefined

        const toolsCalled = filterToolsCalledForCurrentTurn(response)

        if (response.status === 'succeeded' && response.output_message) {
          let content = response.output_message
          const match = content.match(/AgentRunResult\(output=['"]([\s\S]*)['"]\)/)
          if (match && match[1]) {
            content = match[1]
          }
          messages.value.push({ role: 'agent', content, run_id: response.run_id ?? null, tokens, tools_called: toolsCalled })
        } else if (response.status === 'failed' && response.error_message) {
          messages.value.push({
            role: 'agent',
            content: `Ошибка: ${response.error_message}`,
            run_id: response.run_id ?? null,
            tokens,
            tools_called: toolsCalled
          })
          toastError('Ошибка выполнения агента', getReadableErrorMessage({ message: response.error_message }, 'Агент не смог обработать запрос'))
        } else {
          messages.value.push({
            role: 'agent',
            content: 'Извините, возникла ошибка при получении ответа.',
            tokens,
            tools_called: toolsCalled
          })
        }
      } else {
        messages.value.push({
          role: 'agent',
          content: 'Извините, возникла ошибка при получении ответа.',
          tokens: undefined,
          tools_called: undefined
        })
      }
    } catch (err: any) {
      console.error('Chat error:', err)
      if (err.statusCode === 400 && currentSessionId.value && agent.value) {
        clearSessionId(agent.value.id)
        currentSessionId.value = null
      }
      messages.value.push({
        role: 'agent',
        content: 'Произошла ошибка при связи с агентом.',
        tokens: undefined,
        tools_called: undefined
      })
    } finally {
      isTyping.value = false
    }

    return true
  }

  const clearChat = async () => {
    if (!agent.value) return
    if (currentSessionId.value) {
      try {
        await apiFetch(`/runs/session/${currentSessionId.value}`, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token.value}`
          }
        })
      } catch (err) {
        console.error('Failed to clear session on backend:', err)
      }
    }
    messages.value = []
    saveChatMessages()
    clearSessionId(agent.value.id)
    currentSessionId.value = null
  }

  const sqnsToolsList = computed(() => {
    const tools = sqnsStatus.value?.sqnsTools ?? []
    const nameMap: Record<string, string> = {
      'sqns_list_resources': 'Сотрудники',
      'sqns_list_services': 'Услуги',
      'sqns_find_client': 'Поиск клиента',
      'sqns_list_slots': 'Поиск слотов'
    }
    return tools.map(tool => ({
      ...tool,
      displayName: nameMap[tool.name] || tool.name
    }))
  })

  const isSqnsEnabled = computed(() => sqnsStatus.value?.sqnsEnabled ?? false)

  const sqnsStatusLabel = computed(() => {
    if (!sqnsStatus.value?.sqnsEnabled) return 'SQNS не подключён'
    if (sqnsStatus.value?.sqnsStatus === 'error') return 'Обнаружена ошибка'
    return 'Интеграция активна'
  })

  const sqnsHostLabel = computed(() => sqnsStatus.value?.sqnsHost ?? 'не указан')
  const sqnsErrorMessage = computed(() => sqnsStatus.value?.sqnsError ?? '')

  const formattedSqnsSyncAt = computed(() => {
    const raw = sqnsStatus.value?.sqnsLastSyncAt
    if (!raw) return 'нет синхронизаций'
    const parsed = new Date(raw)
    if (Number.isNaN(parsed.getTime())) return raw
    return parsed.toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
  })

  const promptSidebarToolGroups = computed<PromptSidebarToolGroup[]>(() => {
    const sqnsTools: PromptSidebarTool[] = isSqnsEnabled.value
      ? sqnsToolsList.value.map(tool => ({
          name: tool.name,
          description: tool.description || '',
          source: 'sqns',
        }))
      : []

    const knowledgeToolNames = new Set(
      (directoriesComposable.value?.directories ?? [])
        .map(directory => String(directory.tool_name || '').trim())
        .filter(Boolean)
    )

    const knowledgeToolDescriptions = new Map<string, string>(
      (directoriesComposable.value?.directories ?? [])
        .map(directory => [
          String(directory.tool_name || '').trim(),
          String(directory.tool_description || '').trim(),
        ] as const)
        .filter(([toolName]) => Boolean(toolName))
    )

    const classifyCustomToolSource = (binding: ToolBinding): PromptSidebarToolSource => {
      const toolName = String(binding.tool?.name || '').trim()
      if (toolName && knowledgeToolNames.has(toolName)) return 'knowledge'

      const scope = binding.tool?.webhook_scope
      const executionType = binding.tool?.execution_type

      if (scope === 'function_only') return 'functions'
      if (executionType === 'http_webhook') return 'webhook'
      return 'functions'
    }

    const customTools: PromptSidebarTool[] = boundTools.value
      .filter(binding => Boolean(binding.tool?.name))
      .map(binding => ({
        name: binding.tool?.name || 'Инструмент',
        description: (() => {
          const toolName = String(binding.tool?.name || '').trim()
          const apiDescription = String(binding.tool?.description || '').trim()
          if (apiDescription) return apiDescription
          return knowledgeToolDescriptions.get(toolName) || ''
        })(),
        source: classifyCustomToolSource(binding),
      }))

    const dedupeByName = (tools: PromptSidebarTool[]) => {
      const uniqueByName = new Map<string, PromptSidebarTool>()
      tools.forEach(tool => {
        if (!uniqueByName.has(tool.name)) uniqueByName.set(tool.name, tool)
      })
      return Array.from(uniqueByName.values())
    }

    const groups: PromptSidebarToolGroup[] = []
    const uniqueSqnsTools = dedupeByName(sqnsTools)
    const uniqueKnowledgeTools = dedupeByName(customTools.filter(tool => tool.source === 'knowledge'))
    const uniqueFunctionTools = dedupeByName(customTools.filter(tool => tool.source === 'functions'))
    const uniqueWebhookTools = dedupeByName(customTools.filter(tool => tool.source === 'webhook'))

    if (uniqueKnowledgeTools.length) {
      groups.push({
        id: 'knowledge',
        label: 'База знаний',
        tools: uniqueKnowledgeTools,
      })
    }

    if (uniqueFunctionTools.length) {
      groups.push({
        id: 'functions',
        label: 'Функции',
        tools: uniqueFunctionTools,
      })
    }

    if (uniqueWebhookTools.length) {
      groups.push({
        id: 'webhook',
        label: 'Webhook',
        tools: uniqueWebhookTools,
      })
    }

    if (uniqueSqnsTools.length) {
      groups.push({
        id: 'sqns',
        label: 'SQNS',
        tools: uniqueSqnsTools,
      })
    }

    return groups
  })

  const promptSidebarTools = computed(() =>
    promptSidebarToolGroups.value.flatMap(group =>
      group.tools.map(tool => ({ name: tool.name, description: tool.description }))
    )
  )

  const chatContextLabel = computed(() => {
    const count = messages.value.length
    return count > 0 ? `контекст: ${count} сообщений` : ''
  })

  if (typeof window !== 'undefined') {
    watch(messages, () => {
      saveChatMessages()
    }, { deep: true })

    // Auto-save prompt with debounce (backup mechanism)
    // Saves 5 seconds after last change if still focused
    watchDebounced(
      () => form.value.system_prompt,
      async (newPrompt, oldPrompt) => {
        if (!agent.value || !isLoaded.value) return
        if (newPrompt === oldPrompt) return
        if (newPrompt === agent.value.system_prompt) return
        
        // Only auto-save if focused (blur handler will save on focus loss)
        if (isPromptFocused.value) {
          await autoSavePrompt()
        }
      },
      { debounce: 5000 }
    )

    // Auto-save model selection immediately
    watch(
      () => form.value.model,
      async (newModel, oldModel) => {
        if (!agent.value || !isLoaded.value) return
        if (newModel === oldModel) return
        if (newModel === agent.value.model) return
        
        await autoSaveField({ model: newModel })
      }
    )

    // Auto-save agent name with debounce
    watchDebounced(
      () => form.value.name,
      async (newName, oldName) => {
        if (!agent.value || !isLoaded.value) return
        if (newName === oldName) return
        if (newName === agent.value.name) return
        
        await autoSaveField({ name: newName })
      },
      { debounce: 2000 }
    )

    // Auto-save status immediately
    watch(
      () => form.value.status,
      async (newStatus, oldStatus) => {
        if (!agent.value || !isLoaded.value) return
        if (newStatus === oldStatus) return
        if (newStatus === agent.value.status) return
        
        await autoSaveField({ status: newStatus })
      }
    )

    // Auto-save timezone immediately
    watch(
      () => form.value.timezone,
      async (newTimezone, oldTimezone) => {
        if (!agent.value || !isLoaded.value) return
        if (newTimezone === oldTimezone) return
        if (newTimezone === (agent.value.timezone ?? 'Europe/Moscow')) return
        
        await autoSaveField({ timezone: newTimezone })
      }
    )

    // Auto-save disabled state immediately
    watch(
      () => form.value.is_disabled,
      async (newIsDisabled, oldIsDisabled) => {
        if (!agent.value || !isLoaded.value) return
        if (newIsDisabled === oldIsDisabled) return
        if (newIsDisabled === Boolean(agent.value.is_disabled)) return

        await autoSaveField({ is_disabled: newIsDisabled })
      }
    )

    // Auto-save LLM params with debounce
    watchDebounced(
      () => form.value.llm_params,
      async (newParams, oldParams) => {
        if (!agent.value || !isLoaded.value) return
        if (JSON.stringify(newParams) === JSON.stringify(oldParams)) return
        if (JSON.stringify(newParams) === JSON.stringify(agent.value.llm_params)) return
        
        await autoSaveField({ llm_params: newParams })
      },
      { debounce: 1000, deep: true }
    )
  }

  return {
    agentId,
    agent,
    form,
    isLoaded,
    isLoading,
    isSaving,
    isDeleting,
    error,
    isPromptFullscreen,
    isAutoSaving,
    lastAutoSavedAt,
    isPromptFocused,
    boundTools,
    isLoadingTools,
    toolsLoaded,
    channels,
    telegramChannel,
    telegramPhoneChannel,
    whatsappPhoneChannel,
    maxPhoneChannel,
    isLoadingChannels,
    channelsLoaded,
    directoriesComposable,
    directoriesLoaded,
    promptHistory,
    promptHistoryLoaded,
    sqnsStatus,
    sqnsResources,
    sqnsServices,
    sqnsError,
    sqnsStatusLoaded,
    sqnsHintsLoaded,
    messages,
    userInput,
    isTyping,
    currentSessionId,
    chatLoaded,
    sqnsToolsList,
    isSqnsEnabled,
    sqnsStatusLabel,
    sqnsHostLabel,
    sqnsErrorMessage,
    formattedSqnsSyncAt,
    promptSidebarToolGroups,
    promptSidebarTools,
    chatContextLabel,
    setAgentId,
    ensureAgentLoaded,
    saveAgent,
    autoSavePrompt,
    autoSaveField,
    removeAgent,
    resetForm,
    resetPrompt,
    fetchToolsData,
    ensureToolsLoaded,
    toggleTool,
    fetchChannels,
    ensureChannelsLoaded,
    connectChannel,
    disconnectChannel,
    fetchChannelAuthQr,
    ensureDirectoriesLoaded,
    loadSqnsStatusForAgent,
    ensureSqnsStatusLoaded,
    ensureSqnsHints,
    enableSqnsIntegration,
    disableSqnsIntegration,
    ensurePromptHistoryLoaded,
    ensureChatLoaded,
    sendMessage,
    clearChat
  }
})
