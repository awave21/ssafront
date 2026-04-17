import { ref, readonly } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useToast } from './useToast'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type {
  TenantLLMConfigSet,
  TenantLLMConfigRead,
  TenantLLMConfigStatus,
} from '~/types/tenantLlmConfig'

const PROVIDER_PATTERN = /^[a-z0-9_-]+$/

const ANTHROPIC_KEY_ALLOWED = /^[a-zA-Z0-9._-]+$/

const validatePayload = (payload: TenantLLMConfigSet): string | null => {
  const key = payload.api_key
  if (!key || key.length < 10 || key.length > 512)
    return 'API-ключ должен быть от 10 до 512 символов'

  const provider = payload.provider ?? 'openai'
  if (!PROVIDER_PATTERN.test(provider))
    return 'Провайдер может содержать только строчные буквы, цифры, дефис и подчёркивание'

  if (provider === 'openai' && !key.startsWith('sk-'))
    return 'OpenAI ключ должен начинаться с «sk-»'

  if (provider === 'anthropic' && !ANTHROPIC_KEY_ALLOWED.test(key))
    return 'Ключ Anthropic содержит недопустимые символы'

  return null
}

export const useTenantLlmConfig = () => {
  const apiFetch = useApiFetch()
  const { success: toastSuccess, error: toastError } = useToast()

  const keyStatus = ref<TenantLLMConfigStatus | null>(null)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const isDeleting = ref(false)

  const fetchKeyStatus = async (provider = 'openai') => {
    try {
      isLoading.value = true
      const data = await apiFetch<TenantLLMConfigStatus>(
        '/tenant-settings/llm-key',
        { query: { provider } },
      )
      keyStatus.value = data
      return data
    } catch (err: any) {
      toastError('Ошибка загрузки', getReadableErrorMessage(err, 'Не удалось получить статус ключа'))
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const saveKey = async (payload: TenantLLMConfigSet): Promise<TenantLLMConfigRead | null> => {
    const validationError = validatePayload(payload)
    if (validationError) {
      toastError('Ошибка валидации', validationError)
      return null
    }

    try {
      isSaving.value = true
      const data = await apiFetch<TenantLLMConfigRead>(
        '/tenant-settings/llm-key',
        { method: 'PUT', body: payload },
      )
      keyStatus.value = {
        has_key: true,
        provider: data.provider,
        last4: data.last4,
        is_active: data.is_active,
      }
      toastSuccess('Ключ сохранён', 'API-ключ успешно установлен')
      return data
    } catch (err: any) {
      toastError('Ошибка сохранения', getReadableErrorMessage(err, 'Не удалось сохранить API-ключ'))
      throw err
    } finally {
      isSaving.value = false
    }
  }

  const deleteKey = async (provider = 'openai') => {
    try {
      isDeleting.value = true
      await apiFetch('/tenant-settings/llm-key', {
        method: 'DELETE',
        query: { provider },
      })
      keyStatus.value = {
        has_key: false,
        provider,
        last4: null,
        is_active: false,
      }
      toastSuccess('Ключ удалён', 'Запросы с этим провайдером будут недоступны до установки нового ключа')
    } catch (err: any) {
      if (err?.statusCode === 404) {
        keyStatus.value = { has_key: false, provider, last4: null, is_active: false }
        return
      }
      toastError('Ошибка удаления', getReadableErrorMessage(err, 'Не удалось удалить API-ключ'))
      throw err
    } finally {
      isDeleting.value = false
    }
  }

  return {
    keyStatus: readonly(keyStatus),
    isLoading: readonly(isLoading),
    isSaving: readonly(isSaving),
    isDeleting: readonly(isDeleting),
    fetchKeyStatus,
    saveKey,
    deleteKey,
  }
}
