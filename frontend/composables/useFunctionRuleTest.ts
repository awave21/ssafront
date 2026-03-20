import { ref } from 'vue'
import { useApiFetch } from '~/composables/useApiFetch'
import { getReadableErrorMessage } from '~/utils/api-errors'
import {
  mapFunctionRuleTestRequestToBackend,
  mapFunctionRuleTestResponseFromBackend,
  type BackendFunctionRuleTestResponse,
  type FunctionRuleTestRequest,
  type FunctionRuleTestResponse,
} from '~/types/functionRuleTest'

export const useFunctionRuleTest = (agentId: string) => {
  const apiFetch = useApiFetch()
  const loading = ref(false)
  const error = ref<string | null>(null)
  const result = ref<FunctionRuleTestResponse | null>(null)

  const runTest = async (payload: FunctionRuleTestRequest) => {
    loading.value = true
    error.value = null
    try {
      const response = await apiFetch<BackendFunctionRuleTestResponse>(`/agents/${agentId}/function-rules/test`, {
        method: 'POST',
        body: mapFunctionRuleTestRequestToBackend(payload),
      })
      result.value = mapFunctionRuleTestResponseFromBackend(response)
      return result.value
    } catch (err: any) {
      error.value = getReadableErrorMessage(err, 'Не удалось выполнить тест сценария')
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    result,
    runTest,
  }
}
