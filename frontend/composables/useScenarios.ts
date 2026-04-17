import { ref, computed } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useAuth } from './useAuth'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { Scenario, ScenarioUpsertPayload, BackendScenario } from '~/types/scenario'
import { mapScenarioFromBackend } from '~/types/scenario'
import type { BackendFunctionRuleActionPayload } from '~/types/ruleAction'

const defaultToolArgsSchema = {
  type: 'object',
  properties: {},
  required: [],
} as const

const normalizeConditionConfig = (conditionConfig: Record<string, any> | undefined): Record<string, any> => {
  const cfg = { ...(conditionConfig || {}) }
  const schema = cfg.tool_args_schema
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) {
    cfg.tool_args_schema = defaultToolArgsSchema
  }
  return cfg
}

const mapActionsToBackend = (actions: ScenarioUpsertPayload['actions']): BackendFunctionRuleActionPayload[] => {
  return (actions || []).map((action, index) => ({
    action_type: action.action_type as any,
    action_config: action.config || {},
    on_status: action.on_status || 'always',
    order_index: Number.isFinite(action.order_index) ? action.order_index : index,
    enabled: action.enabled ?? true,
  }))
}

const buildRulePayload = (payload: ScenarioUpsertPayload) => ({
  name: payload.name,
  enabled: payload.enabled,
  dry_run: false,
  stop_on_match: false,
  allow_semantic: true,
  priority: payload.priority,
  trigger_mode: payload.trigger_mode,
  condition_type: payload.condition_type,
  condition_config: normalizeConditionConfig(payload.condition_config),
  tool_id: null,
  // Must not be "silent": runtime sets silent_reaction → execute_agent_run skips the LLM entirely
  // (empty output in test chat). Post-actions (augment_prompt, send_message, …) still run first.
  reaction_to_execution: 'ai_self_reply' as const,
  behavior_after_execution: 'continue' as const,
  actions: mapActionsToBackend(payload.actions),
})

export const useScenarios = (agentId: string) => {
  const apiFetch = useApiFetch()
  const { token } = useAuth()

  const scenarios = ref<Scenario[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const fetchScenarios = async () => {
    isLoading.value = true
    error.value = null
    try {
      const data = await apiFetch<BackendScenario[]>(`/agents/${agentId}/function-rules`, {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      // Фильтруем только те, что относятся к сценариям (в нашей реализации это все function-rules агента)
      scenarios.value = (data || []).map(mapScenarioFromBackend)
    } catch (err: any) {
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить сценарии')
    } finally {
      isLoading.value = false
    }
  }

  const createScenario = async (payload: ScenarioUpsertPayload): Promise<Scenario | null> => {
    try {
      const created = await apiFetch<BackendScenario>(`/agents/${agentId}/function-rules`, {
        method: 'POST',
        headers: { 
          Authorization: `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        },
        body: buildRulePayload(payload)
      })
      const scenario = mapScenarioFromBackend(created)
      scenarios.value.push(scenario)
      return scenario
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось создать сценарий'))
    }
  }

  const updateScenario = async (id: string, payload: ScenarioUpsertPayload): Promise<Scenario | null> => {
    try {
      const updated = await apiFetch<BackendScenario>(`/agents/${agentId}/function-rules/${id}`, {
        method: 'PUT',
        headers: { 
          Authorization: `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        },
        body: buildRulePayload(payload)
      })
      const scenario = mapScenarioFromBackend(updated)
      const index = scenarios.value.findIndex(s => s.id === id)
      if (index !== -1) {
        scenarios.value[index] = scenario
      }
      return scenario
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось обновить сценарий'))
    }
  }

  const deleteScenario = async (id: string): Promise<void> => {
    try {
      await apiFetch(`/agents/${agentId}/function-rules/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token.value}` }
      })
      scenarios.value = scenarios.value.filter(s => s.id !== id)
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось удалить сценарий'))
    }
  }

  const toggleScenario = async (id: string, enabled: boolean): Promise<void> => {
    try {
      await apiFetch(`/agents/${agentId}/function-rules/${id}`, {
        method: 'PUT',
        headers: { 
          Authorization: `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        },
        body: { enabled }
      })
      const index = scenarios.value.findIndex(s => s.id === id)
      if (index !== -1) {
        scenarios.value[index].enabled = enabled
      }
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось изменить статус сценария'))
    }
  }

  return {
    scenarios,
    isLoading,
    error,
    fetchScenarios,
    createScenario,
    updateScenario,
    deleteScenario,
    toggleScenario
  }
}
