import { ref } from 'vue'
import { useApiFetch } from './useApiFetch'

export type ActiveModelOption = {
  value: string
  provider: string
  model_name: string
  label: string
}

export type ActiveModelGroup = {
  group: string
  options: ActiveModelOption[]
}

// Временно скрываем проблемные модели из UI выбора.
const HIDDEN_MODEL_VALUES = new Set<string>(['5'])

const isValidOption = (option: any): option is ActiveModelOption =>
  option &&
  typeof option.value === 'string' &&
  typeof option.provider === 'string' &&
  typeof option.model_name === 'string' &&
  typeof option.label === 'string'

const isVisibleOption = (option: ActiveModelOption): boolean =>
  !HIDDEN_MODEL_VALUES.has(option.value)

const normalizeGroups = (payload: any): ActiveModelGroup[] => {
  if (!Array.isArray(payload)) return []

  return payload
    .filter((group: any) => group && typeof group.group === 'string' && Array.isArray(group.options))
    .map((group: any) => ({
      group: group.group,
      options: group.options.filter(isValidOption).filter(isVisibleOption)
    }))
    .filter((group: ActiveModelGroup) => group.options.length > 0)
}

export const useActiveModels = () => {
  const apiFetch = useApiFetch()

  const modelGroups = ref<ActiveModelGroup[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const fetchActiveModels = async () => {
    isLoading.value = true
    error.value = null

    try {
      const response = await apiFetch<any>('/model-pricing/active-models')
      modelGroups.value = normalizeGroups(response)
    } catch (err: any) {
      error.value = err?.message || 'Не удалось загрузить доступные модели'
      modelGroups.value = []
    } finally {
      isLoading.value = false
    }
  }

  const hasModelValue = (value: string) =>
    modelGroups.value.some(group => group.options.some(option => option.value === value))

  const getFirstModelValue = () => {
    const firstGroup = modelGroups.value.find(group => group.options.length > 0)
    return firstGroup?.options[0]?.value || ''
  }

  return {
    modelGroups,
    isLoading,
    error,
    fetchActiveModels,
    hasModelValue,
    getFirstModelValue
  }
}
