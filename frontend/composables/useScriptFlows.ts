import { ref } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useAuth } from './useAuth'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type {
  ScriptFlow,
  ScriptFlowCoverageResult,
  ScriptFlowCreatePayload,
  ScriptFlowSearchTestResult,
  ScriptFlowUpdatePayload,
  ScriptFlowSuggestKeywordsResult,
} from '~/types/scriptFlow'

export const useScriptFlows = (agentId: string) => {
  const apiFetch = useApiFetch()
  const { token } = useAuth()

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

  const updateFlow = async (flowId: string, payload: ScriptFlowUpdatePayload): Promise<ScriptFlow> => {
    return await apiFetch<ScriptFlow>(`/agents/${agentId}/script-flows/${flowId}`, {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
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

  const suggestKeywords = async (flowId: string): Promise<ScriptFlowSuggestKeywordsResult> => {
    return await apiFetch<ScriptFlowSuggestKeywordsResult>(
      `/agents/${agentId}/script-flows/${flowId}/suggest-keywords`,
      { method: 'POST', headers: authHeaders() },
    )
  }

  const testSearch = async (query: string, limit = 5): Promise<ScriptFlowSearchTestResult> => {
    return await apiFetch<ScriptFlowSearchTestResult>(
      `/agents/${agentId}/script-flows/test-search`,
      {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: { query, limit },
      },
    )
  }

  const getFlowCoverage = async (flowId: string): Promise<ScriptFlowCoverageResult> => {
    return await apiFetch<ScriptFlowCoverageResult>(
      `/agents/${agentId}/script-flows/${flowId}/coverage`,
      { headers: authHeaders() },
    )
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
    suggestKeywords,
    testSearch,
    getFlowCoverage,
  }
}
