import { ref } from 'vue'
import { useApiFetch } from '~/composables/useApiFetch'

export type TenantFunctionRulesSettings = {
  enabled: boolean
}

export const useTenantFunctionRules = () => {
  const apiFetch = useApiFetch()
  const saving = ref(false)

  const patchSettings = async (payload: TenantFunctionRulesSettings) => {
    saving.value = true
    try {
      return await apiFetch<TenantFunctionRulesSettings>('/tenant-settings/function-rules', {
        method: 'PATCH',
        body: payload,
      })
    } finally {
      saving.value = false
    }
  }

  return {
    saving,
    patchSettings,
  }
}
