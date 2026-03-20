import { ref } from 'vue'
import { useApiFetch } from '~/composables/useApiFetch'
import {
  mapRuleActionFromBackend,
  mapRuleActionPayloadToBackend,
  type BackendFunctionRuleAction,
  type FunctionRuleAction,
  type FunctionRuleActionPayload,
} from '~/types/ruleAction'

export const useRuleActions = (agentId: string) => {
  const apiFetch = useApiFetch()
  const actionsByRuleId = ref<Record<string, FunctionRuleAction[]>>({})
  const saving = ref(false)

  const setActions = (ruleId: string, actions: FunctionRuleAction[]) => {
    actionsByRuleId.value = {
      ...actionsByRuleId.value,
      [ruleId]: actions,
    }
  }

  const getActions = (ruleId: string) => actionsByRuleId.value[ruleId] || []

  const addAction = async (ruleId: string, payload: FunctionRuleActionPayload) => {
    saving.value = true
    try {
      const created = await apiFetch<BackendFunctionRuleAction>(
        `/agents/${agentId}/function-rules/${ruleId}/actions`,
        {
          method: 'POST',
          body: mapRuleActionPayloadToBackend(payload),
        },
      )
      const mapped = mapRuleActionFromBackend(created)
      setActions(ruleId, [...getActions(ruleId), mapped].sort((a, b) => a.order_index - b.order_index))
      return mapped
    } finally {
      saving.value = false
    }
  }

  const updateAction = async (ruleId: string, actionId: string, payload: FunctionRuleActionPayload) => {
    saving.value = true
    try {
      const updated = await apiFetch<BackendFunctionRuleAction>(
        `/agents/${agentId}/function-rules/${ruleId}/actions/${actionId}`,
        {
          method: 'PUT',
          body: mapRuleActionPayloadToBackend(payload),
        },
      )
      const mapped = mapRuleActionFromBackend(updated)
      setActions(
        ruleId,
        getActions(ruleId)
          .map(action => (action.id === actionId ? mapped : action))
          .sort((a, b) => a.order_index - b.order_index),
      )
      return mapped
    } finally {
      saving.value = false
    }
  }

  const removeAction = async (ruleId: string, actionId: string) => {
    await apiFetch(`/agents/${agentId}/function-rules/${ruleId}/actions/${actionId}`, {
      method: 'DELETE',
    })
    setActions(
      ruleId,
      getActions(ruleId).filter(action => action.id !== actionId),
    )
  }

  return {
    actionsByRuleId,
    saving,
    setActions,
    getActions,
    addAction,
    updateAction,
    removeAction,
  }
}
