import { ref } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useAuth } from './useAuth'
import { useToast } from './useToast'

export interface GenerateFieldParams {
  agentId: string
  flowId: string
  nodeId: string
  nodeType: string
  fieldKey: string
  currentNodeData: Record<string, unknown>
}

export interface GenerateFieldResponse {
  field_key: string
  generated_text: string
  model: string
  tokens_in: number
  tokens_out: number
}

export const useScriptFlowFieldGenerator = () => {
  const apiFetch = useApiFetch()
  const { token } = useAuth()
  const { error: toastError } = useToast()

  const isGenerating = ref(false)

  const generateField = async (params: GenerateFieldParams): Promise<string | null> => {
    isGenerating.value = true
    try {
      const res = await apiFetch<GenerateFieldResponse>(
        `/agents/${params.agentId}/script-flows/${params.flowId}/nodes/generate-field`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token.value}`,
            'Content-Type': 'application/json',
          },
          body: {
            node_id: params.nodeId,
            node_type: params.nodeType,
            field_key: params.fieldKey,
            current_node_data: params.currentNodeData,
          },
        },
      )
      return res?.generated_text || null
    } catch (err: unknown) {
      const e = err as { data?: { detail?: { error?: string; message?: string } }; statusCode?: number }
      const code = e?.data?.detail?.error
      const message = e?.data?.detail?.message
      if (code === 'no_openai_key') {
        toastError(message || 'Подключите OpenAI ключ в настройках LLM-провайдеров')
      } else if (code === 'openai_unavailable' || e?.statusCode === 502) {
        toastError('OpenAI временно недоступен, повторите попытку позже')
      } else if (code === 'unknown_field_key' || code === 'node_type_mismatch') {
        toastError(message || 'Это поле не поддерживает AI-заполнение')
      } else if (code === 'node_not_found') {
        toastError('Сначала сохраните поток — нода ещё не зафиксирована')
      } else {
        toastError(message || 'Не удалось сгенерировать значение')
      }
      return null
    } finally {
      isGenerating.value = false
    }
  }

  return {
    generateField,
    isGenerating,
  }
}
