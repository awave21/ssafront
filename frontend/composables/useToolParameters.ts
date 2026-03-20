import { ref } from 'vue'
import { useApiFetch } from '~/composables/useApiFetch'
import type {
  BackendToolParameter,
  BackendToolParametersResponse,
  BackendToolParametersUpdateRequest,
  BackendToolParametersPreviewRequest,
  BackendToolParametersPreviewResponse,
  ToolParameter,
} from '~/types/toolParameter'

const mapParameterFromBackend = (parameter: BackendToolParameter): ToolParameter => ({
  id: parameter.id,
  name: parameter.name,
  type: parameter.type,
  instruction: parameter.instruction,
  required: parameter.required,
  optional: parameter.is_optional,
  enum_values: parameter.enum_values,
  default_value: parameter.default_value,
  x_from_ai: parameter.x_from_ai,
  order_index: parameter.order_index,
})

const mapParameterToBackend = (parameter: ToolParameter): BackendToolParameter => ({
  id: parameter.id,
  name: parameter.name,
  type: parameter.type,
  instruction: parameter.instruction,
  required: parameter.required,
  is_optional: parameter.optional,
  enum_values: parameter.enum_values,
  default_value: parameter.default_value,
  x_from_ai: parameter.x_from_ai,
  order_index: parameter.order_index,
})

export const useToolParameters = () => {
  const apiFetch = useApiFetch()
  const loading = ref(false)
  const saving = ref(false)
  const previewLoading = ref(false)

  const parameters = ref<ToolParameter[]>([])
  const previewSchema = ref<Record<string, any> | null>(null)

  const fetchParameters = async (toolId: string) => {
    loading.value = true
    try {
      const response = await apiFetch<BackendToolParametersResponse>(`/tools/${toolId}/parameters`)
      parameters.value = (response.parameters || []).map(mapParameterFromBackend)
      previewSchema.value = response.generated_input_schema || null
      return parameters.value
    } finally {
      loading.value = false
    }
  }

  const saveParameters = async (toolId: string, payload: ToolParameter[]) => {
    saving.value = true
    try {
      const body: BackendToolParametersUpdateRequest = {
        parameters: payload.map(mapParameterToBackend),
      }
      const response = await apiFetch<BackendToolParametersResponse>(`/tools/${toolId}/parameters`, {
        method: 'PUT',
        body,
      })
      parameters.value = (response.parameters || []).map(mapParameterFromBackend)
      previewSchema.value = response.generated_input_schema || null
      return parameters.value
    } finally {
      saving.value = false
    }
  }

  const previewParametersSchema = async (payload: ToolParameter[]) => {
    previewLoading.value = true
    try {
      const body: BackendToolParametersPreviewRequest = {
        parameters: payload.map(mapParameterToBackend),
      }
      const response = await apiFetch<BackendToolParametersPreviewResponse>('/tools/parameters/preview-schema', {
        method: 'POST',
        body,
      })
      previewSchema.value = response.input_schema
      return response.input_schema
    } finally {
      previewLoading.value = false
    }
  }

  return {
    loading,
    saving,
    previewLoading,
    parameters,
    previewSchema,
    fetchParameters,
    saveParameters,
    previewParametersSchema,
  }
}
