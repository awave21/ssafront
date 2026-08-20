import { ref } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useAuth } from './useAuth'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type {
  ReviewCorrectionPayload,
  ReviewDialog,
  ScriptFlow,
  ScriptFlowCoverageResult,
  ScriptFlowCreatePayload,
  ScriptFlowGraphPreview,
  ScriptFlowKgCoverageResult,
  ScriptFlowSearchTestResult,
  ScriptFlowSuggestKeywordsResult,
  ScriptFlowUpdatePayload,
  SkillDoc,
  SkillGap,
  SkillObjection,
} from '~/types/scriptFlow'

export const useScriptFlows = (agentId: string) => {
  const apiFetch = useApiFetch()
  const { token } = useAuth()
  // @ts-ignore - Nuxt auto-import
  const { public: { apiBase } } = useRuntimeConfig()

  const flows = ref<ScriptFlow[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const authHeaders = () => ({
    Authorization: `Bearer ${token.value}`,
  })

  const fetchFlows = async () => {
    isLoading.value = true
    error.value = null
    try {
      const data = await apiFetch<ScriptFlow[]>(`/agents/${agentId}/script-flows`, {
        headers: authHeaders(),
      })
      flows.value = data || []
    } catch (err: unknown) {
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить потоки')
    } finally {
      isLoading.value = false
    }
  }

  const createFlow = async (payload: ScriptFlowCreatePayload): Promise<ScriptFlow> => {
    return await apiFetch<ScriptFlow>(`/agents/${agentId}/script-flows`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
    })
  }

  const getFlow = async (flowId: string): Promise<ScriptFlow> => {
    return await apiFetch<ScriptFlow>(`/agents/${agentId}/script-flows/${flowId}`, {
      headers: authHeaders(),
    })
  }

  const updateFlow = async (
    flowId: string,
    payload: ScriptFlowUpdatePayload,
    opts?: { definitionVersion?: number },
  ): Promise<ScriptFlow> => {
    const headers: Record<string, string> = {
      ...authHeaders(),
      'Content-Type': 'application/json',
    }
    if (opts?.definitionVersion != null)
      headers['X-Definition-Version'] = String(opts.definitionVersion)

    return await apiFetch<ScriptFlow>(`/agents/${agentId}/script-flows/${flowId}`, {
      method: 'PATCH',
      headers,
      body: payload,
    })
  }

  const deleteFlow = async (flowId: string): Promise<void> => {
    await apiFetch(`/agents/${agentId}/script-flows/${flowId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
  }

  const previewFlow = async (flowId: string): Promise<string> => {
    const res = await apiFetch<{ compiled_text: string }>(
      `/agents/${agentId}/script-flows/${flowId}/preview`,
      { headers: authHeaders() },
    )
    return res?.compiled_text || ''
  }

  const publishFlow = async (
    flowId: string,
  ): Promise<{ id: string; flow_status: string; published_version: number; index_status: string }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/publish`, {
      method: 'POST',
      headers: authHeaders(),
    })
  }

  const unpublishFlow = async (
    flowId: string,
  ): Promise<{ id: string; flow_status: string; published_version: number; index_status: string }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/unpublish`, {
      method: 'POST',
      headers: authHeaders(),
    })
  }

  const distillSkill = async (
    flowId: string,
  ): Promise<{ id: string; skill_doc: SkillDoc; objections: number; gaps: number }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/distill-skill`, {
      method: 'POST',
      headers: authHeaders(),
    })
  }

  const updateSkillDoc = async (
    flowId: string,
    skillDoc: SkillDoc,
  ): Promise<{ id: string; skill_doc: SkillDoc; objections: number; gaps: number }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/skill-doc`, {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: { skill_doc: skillDoc },
    })
  }

  const skillChatStream = async (
    flowId: string,
    payload: {
      messages: Array<{ role: string; content: string }>
      attachments?: Array<{ name: string; text: string }>
      skill_doc?: SkillDoc | null
      model?: string
    },
    opts: {
      onDelta: (text: string) => void
      signal?: AbortSignal
    },
  ): Promise<{ reply: string; additions: { objections: SkillObjection[]; gaps: SkillGap[] } } | null> => {
    const res = await fetch(`${apiBase}/agents/${agentId}/script-flows/${flowId}/skill-chat/stream`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(payload),
      signal: opts.signal,
    })
    if (!res.ok || !res.body) throw new Error(`Стрим недоступен (${res.status})`)
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let done: { reply: string; additions: { objections: SkillObjection[]; gaps: SkillGap[] } } | null = null
    for (;;) {
      const { value, done: rdDone } = await reader.read()
      if (rdDone) break
      buffer += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const rawEvent = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        let event = 'message'
        let data = ''
        for (const line of rawEvent.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (!data) continue
        const parsed = JSON.parse(data)
        if (event === 'delta') opts.onDelta(parsed.text as string)
        else if (event === 'done') done = parsed
        else if (event === 'error') throw new Error(parsed.error || 'Ошибка стрима')
      }
    }
    return done
  }

  const getSkillChatModels = async (): Promise<{
    models: Array<{ id: string; label: string; hint: string }>
    default: string
  }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/skill-chat/models`, {
      headers: authHeaders(),
    })
  }

  const skillChat = async (
    flowId: string,
    payload: {
      messages: Array<{ role: string; content: string }>
      attachments?: Array<{ name: string; text: string }>
      skill_doc?: SkillDoc | null
      model?: string
    },
    signal?: AbortSignal,
  ): Promise<{
    reply: string
    additions: { objections: SkillObjection[]; gaps: SkillGap[] }
    added_objections: number
    added_gaps: number
  }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/skill-chat`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
      signal,
    })
  }

  const getReviewDialogs = async (
    flowId: string,
    limit = 30,
  ): Promise<{ dialogs: ReviewDialog[]; has_service_link: boolean }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/review-dialogs?limit=${limit}`, {
      headers: authHeaders(),
    })
  }

  const addReviewCorrection = async (
    flowId: string,
    payload: ReviewCorrectionPayload,
  ): Promise<{ id: string; skill_doc: SkillDoc; objections: number; gaps: number }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/review-correction`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
    })
  }

  const suggestKeywords = async (flowId: string): Promise<ScriptFlowSuggestKeywordsResult> => {
    return await apiFetch<ScriptFlowSuggestKeywordsResult>(
      `/agents/${agentId}/script-flows/${flowId}/suggest-keywords`,
      { method: 'POST', headers: authHeaders() },
    )
  }

  const testSearch = async (query: string): Promise<ScriptFlowSearchTestResult> => {
    return await apiFetch<ScriptFlowSearchTestResult>(
      `/agents/${agentId}/script-flows/test-search`,
      {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: { query },
      },
    )
  }

  const getFlowCoverage = async (flowId: string): Promise<ScriptFlowCoverageResult> => {
    return await apiFetch<ScriptFlowCoverageResult>(
      `/agents/${agentId}/script-flows/${flowId}/coverage`,
      { headers: authHeaders() },
    )
  }

  const getKgCoverage = async (): Promise<ScriptFlowKgCoverageResult> => {
    return await apiFetch<ScriptFlowKgCoverageResult>(
      `/agents/${agentId}/script-flows/kg-coverage`,
      { headers: authHeaders() },
    )
  }

  const compileDraft = async (
    flowId: string,
    body: { flow_definition?: Record<string, unknown>; flow_metadata?: Record<string, unknown> },
  ): Promise<{ compiled_text: string | null }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/compile-draft`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body,
    })
  }

  const getGraphRagPreview = async (flowId: string): Promise<ScriptFlowGraphPreview> => {
    return await apiFetch<ScriptFlowGraphPreview>(
      `/agents/${agentId}/script-flows/${flowId}/graphrag-preview`,
      { headers: authHeaders() },
    )
  }

  const getGraphRagPreviewDraft = async (
    flowId: string,
    flow_definition?: Record<string, unknown>,
    flow_metadata?: Record<string, unknown>,
  ): Promise<ScriptFlowGraphPreview> => {
    return await apiFetch<ScriptFlowGraphPreview>(
      `/agents/${agentId}/script-flows/${flowId}/graphrag-preview-draft`,
      {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: {
          flow_definition: flow_definition ?? {},
          flow_metadata: flow_metadata ?? {},
        },
      },
    )
  }

  const retryFlowIndex = async (
    flowId: string,
  ): Promise<{ id: string; index_status: string; published_version: number }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/retry-index`, {
      method: 'POST',
      headers: authHeaders(),
    })
  }

  const listFlowVersions = async (
    flowId: string,
  ): Promise<Array<{ id: string; version: number; created_at: string }>> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/versions`, {
      headers: authHeaders(),
    })
  }

  const restoreFlowVersion = async (
    flowId: string,
    publishedVersion: number,
  ): Promise<ScriptFlow> => {
    return await apiFetch<ScriptFlow>(
      `/agents/${agentId}/script-flows/${flowId}/versions/${publishedVersion}/restore`,
      {
        method: 'POST',
        headers: authHeaders(),
      },
    )
  }

  const cancelFlowIndex = async (
    flowId: string,
  ): Promise<{ id: string; index_cancel_requested: boolean }> => {
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/cancel-index`, {
      method: 'POST',
      headers: authHeaders(),
    })
  }

  const getFlowToolUsage = async (
    flowId: string,
    days?: number,
  ): Promise<{
    approximate_flow_tool_calls: number
    days?: number
    disclaimer?: string
    daily_series?: Array<{ date: string; count: number }>
    top_node_refs?: Array<{
      node_ref: string
      tactic_title?: string | null
      count: number
      last_invoked_at?: string | null
    }>
    by_node_id?: Record<string, {
      node_ref: string
      tactic_title?: string | null
      count: number
      last_invoked_at?: string | null
    }>
  }> => {
    const q = typeof days === 'number' ? `?days=${days}` : ''
    return await apiFetch(`/agents/${agentId}/script-flows/${flowId}/tool-usage${q}`, {
      headers: authHeaders(),
    })
  }

  return {
    flows,
    isLoading,
    error,
    fetchFlows,
    createFlow,
    getFlow,
    updateFlow,
    deleteFlow,
    previewFlow,
    publishFlow,
    unpublishFlow,
    distillSkill,
    updateSkillDoc,
    skillChat,
    skillChatStream,
    getSkillChatModels,
    getReviewDialogs,
    addReviewCorrection,
    suggestKeywords,
    testSearch,
    getFlowCoverage,
    getKgCoverage,
    compileDraft,
    getGraphRagPreview,
    getGraphRagPreviewDraft,
    retryFlowIndex,
    listFlowVersions,
    restoreFlowVersion,
    cancelFlowIndex,
    getFlowToolUsage,
  }
}
