import { computed, ref } from 'vue'
import { useApiFetch } from '~/composables/useApiFetch'
import { getReadableErrorMessage } from '~/utils/api-errors'
import {
  mapFunctionRuleFromBackend,
  mapFunctionRulePayloadToBackend,
  type BackendFunctionRule,
  type FunctionRule,
  type FunctionRuleUpsertPayload,
} from '~/types/functionRule'

export const useFunctionRules = (agentId: string) => {
  const apiFetch = useApiFetch()

  const rules = ref<FunctionRule[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  const fetchRules = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await apiFetch<BackendFunctionRule[]>(`/agents/${agentId}/function-rules`)
      rules.value = response.map(mapFunctionRuleFromBackend)
    } catch (err: any) {
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить сценарии')
      rules.value = []
    } finally {
      loading.value = false
    }
  }

  const createRule = async (payload: FunctionRuleUpsertPayload) => {
    saving.value = true
    try {
      const created = await apiFetch<BackendFunctionRule>(`/agents/${agentId}/function-rules`, {
        method: 'POST',
        body: mapFunctionRulePayloadToBackend(payload),
      })
      const mapped = mapFunctionRuleFromBackend(created)
      rules.value = [mapped, ...rules.value]
      return mapped
    } finally {
      saving.value = false
    }
  }

  const updateRule = async (ruleId: string, payload: FunctionRuleUpsertPayload) => {
    saving.value = true
    try {
      const updated = await apiFetch<BackendFunctionRule>(`/agents/${agentId}/function-rules/${ruleId}`, {
        method: 'PUT',
        body: mapFunctionRulePayloadToBackend(payload),
      })
      const mapped = mapFunctionRuleFromBackend(updated)
      rules.value = rules.value.map(rule => (rule.id === ruleId ? mapped : rule))
      return mapped
    } finally {
      saving.value = false
    }
  }

  const removeRule = async (ruleId: string) => {
    await apiFetch(`/agents/${agentId}/function-rules/${ruleId}`, {
      method: 'DELETE',
    })
    rules.value = rules.value.filter(rule => rule.id !== ruleId)
  }

  const toggleRule = async (rule: FunctionRule, enabled: boolean) =>
    updateRule(rule.id, {
      ...rule,
      enabled,
    })

  const killSwitch = async () => {
    await apiFetch(`/agents/${agentId}/function-rules/kill-switch`, {
      method: 'POST',
    })
    rules.value = rules.value.map(rule => ({
      ...rule,
      enabled: false,
    }))
  }

  const sortedRules = computed(() =>
    [...rules.value].sort((left, right) => right.priority - left.priority),
  )

  return {
    rules,
    sortedRules,
    loading,
    saving,
    error,
    fetchRules,
    createRule,
    updateRule,
    removeRule,
    toggleRule,
    killSwitch,
  }
}
