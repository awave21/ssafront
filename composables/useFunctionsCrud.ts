/**
 * Composable: CRUD operations for agent functions (tools)
 * Handles: load, save, create, delete, duplicate, import from cURL, toggle status
 */
import { ref, computed, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApiFetch } from '~/composables/useApiFetch'
import { useCredentials } from '~/composables/useCredentials'
import type { Tool, ToolTestResponse } from '~/types/tool'
import type { BodyParameter } from '~/utils/function-schema'
import { resolveVariableTokens, resolveVariablesDeep } from '~/utils/function-schema'
import { getReadableErrorMessage } from '~/utils/api-errors'

// Transliteration map
const cyrToLat: Record<string, string> = {
  'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
  'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
  'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
  'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
  'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}

export const toSnakeSlug = (input: string): string =>
  input
    .toLowerCase()
    .split('')
    .map(ch => cyrToLat[ch] ?? ch)
    .join('')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_')

type Header = { key: string; value: string }

type FunctionVariable = { name: string; value: string; description: string }

export const useFunctionsCrud = (agentId: Ref<string>) => {
  const apiFetch = useApiFetch()
  const route = useRoute()
  const router = useRouter()
  const { credentials: credentialsList, fetchCredentials } = useCredentials()

  // State
  const functions = ref<Tool[]>([])
  const selectedFunction = ref<Tool | null>(null)
  const displayName = ref('')
  const unsavedChanges = ref<Set<string>>(new Set())
  const statusMessage = ref<{ type: 'success' | 'error'; text: string } | null>(null)
  const testing = ref(false)
  const testResult = ref<ToolTestResponse | null>(null)
  const testPayload = ref('{}')

  // Binding-level credential tracking
  const bindingCredentials = ref<Record<string, string | null>>({})

  const selectedBindingCredentialId = computed({
    get: () => {
      const toolId = selectedFunction.value?.id
      if (!toolId) return null
      return bindingCredentials.value[toolId] ?? null
    },
    set: (val: string | null) => {
      const toolId = selectedFunction.value?.id
      if (!toolId) return
      bindingCredentials.value[toolId] = val || null
      markAsChanged()
    },
  })

  const canSave = computed(() => {
    if (!selectedFunction.value?.id) return false
    const func = selectedFunction.value
    const funcId = func.id!
    return unsavedChanges.value.has(funcId) && func.name.trim() !== '' && func.endpoint.trim() !== ''
  })

  // Utility
  const showStatus = (type: 'success' | 'error', text: string) => {
    statusMessage.value = { type, text }
    setTimeout(() => { statusMessage.value = null }, 4000)
  }

  const markAsChanged = () => {
    if (selectedFunction.value?.id) {
      unsavedChanges.value.add(selectedFunction.value.id)
    }
  }

  // Load
  const loadFunctions = async () => {
    try {
      const bindings = await apiFetch<any[]>(`/agents/${agentId.value}/tools/details`)
      functions.value = bindings
        .map(binding => binding.tool)
        .filter((tool): tool is Tool => tool !== null && tool !== undefined)

      const credMap: Record<string, string | null> = {}
      bindings.forEach((binding) => {
        if (binding.tool?.id) credMap[binding.tool.id] = binding.credential_id ?? null
      })
      bindingCredentials.value = credMap
    } catch (e) {
      console.error('Failed to load functions', e)
      functions.value = []
    }
  }

  // Create
  const createFunction = (): Tool => {
    const newTool: Tool = {
      id: `new_${Date.now()}`,
      name: '',
      description: '',
      endpoint: '',
      http_method: 'POST',
      execution_type: 'http_webhook',
      auth_type: 'none',
      input_schema: { type: 'object', properties: {} },
      parameter_mapping: null,
      response_transform: null,
      headers: null,
      status: 'active',
      version: 1
    }
    functions.value.unshift(newTool)
    selectedFunction.value = newTool
    displayName.value = ''
    unsavedChanges.value.add(newTool.id!)
    return newTool
  }

  // Save
  const saveFunction = async (
    headers: Ref<Header[]>,
    bodyParameters: Ref<BodyParameter[]>
  ) => {
    if (!selectedFunction.value || !canSave.value) return

    try {
      let shouldShowSuccess = true
      const isNew = selectedFunction.value.id?.startsWith('new_')
      const credentialId = selectedBindingCredentialId.value || null

      const payload: Record<string, any> = {
        name: selectedFunction.value.name,
        description: selectedFunction.value.description || '',
        input_schema: selectedFunction.value.input_schema || { type: 'object', properties: {} },
        execution_type: 'http_webhook',
        endpoint: selectedFunction.value.endpoint,
        auth_type: selectedFunction.value.auth_type || 'none',
        status: selectedFunction.value.status || 'active',
      }

      if (selectedFunction.value.http_method) payload.http_method = selectedFunction.value.http_method

      payload.custom_headers = headers.value.reduce((obj, h) => {
        if (h.key.trim()) obj[h.key] = h.value
        return obj
      }, {} as Record<string, string>)

      if (selectedFunction.value.response_transform) payload.response_transform = selectedFunction.value.response_transform
      if (selectedFunction.value.parameter_mapping) payload.parameter_mapping = selectedFunction.value.parameter_mapping

      if (isNew) {
        const toolResponse = await apiFetch<Tool>('/tools', { method: 'POST', body: payload })
        await apiFetch(`/agents/${agentId.value}/tools/${toolResponse.id}`, {
          method: 'POST',
          body: { permission_scope: 'write', credential_id: credentialId }
        })
        bindingCredentials.value[toolResponse.id!] = credentialId

        const oldId = selectedFunction.value.id
        const index = functions.value.findIndex(f => f.id === oldId)
        if (index !== -1) {
          functions.value.splice(index, 1, toolResponse)
          selectedFunction.value = toolResponse
        }
        if (toolResponse.id) router.replace({ query: { ...route.query, functionId: toolResponse.id } })
        if (oldId && oldId !== toolResponse.id) delete bindingCredentials.value[oldId]
        unsavedChanges.value.delete(oldId!)
      } else {
        const toolId = selectedFunction.value.id!
        const previousCredentialId = bindingCredentials.value[toolId] ?? null
        const credentialChanged = previousCredentialId !== credentialId
        const response = await apiFetch<Tool>(`/tools/${toolId}`, { method: 'PUT', body: payload })
        const index = functions.value.findIndex(f => f.id === toolId)
        if (index !== -1) {
          functions.value.splice(index, 1, response)
          selectedFunction.value = response
        }

        // Tool update is already persisted. Credential rebind is optional and only needed on change.
        unsavedChanges.value.delete(toolId)

        if (credentialChanged) {
          // Rebind: DELETE old binding, then POST new one.
          // If POST fails after DELETE, try to restore previous binding.
          try {
            await apiFetch(`/agents/${agentId.value}/tools/${toolId}`, { method: 'DELETE' })
            try {
              await apiFetch(`/agents/${agentId.value}/tools/${toolId}`, {
                method: 'POST',
                body: { permission_scope: 'write', credential_id: credentialId }
              })
              bindingCredentials.value[toolId] = credentialId
            } catch (postErr: any) {
              console.error('Rebind POST failed, attempting rollback:', postErr)
              try {
                await apiFetch(`/agents/${agentId.value}/tools/${toolId}`, {
                  method: 'POST',
                  body: { permission_scope: 'write', credential_id: previousCredentialId }
                })
              } catch (rollbackErr: any) {
                console.error('Rollback also failed, tool may be unbound:', rollbackErr)
              }
              shouldShowSuccess = false
              showStatus('error', 'Функция сохранена, но не удалось обновить привязку credential')
            }
          } catch (deleteErr: any) {
            console.error('Rebind DELETE failed (binding unchanged):', deleteErr)
            shouldShowSuccess = false
            showStatus('error', 'Функция сохранена, но не удалось обновить привязку credential')
          }
        }
      }
      if (shouldShowSuccess) showStatus('success', 'Функция сохранена')
    } catch (e: any) {
      console.error('Failed to save function', e)
      showStatus('error', `Ошибка сохранения: ${getReadableErrorMessage(e, 'не удалось сохранить функцию')}`)
    }
  }

  // Delete
  const deleteFunction = async () => {
    if (!selectedFunction.value) return
    const funcName = selectedFunction.value.name || 'Новая функция'
    if (!confirm(`Вы уверены, что хотите удалить функцию "${funcName}"?`)) return

    const index = functions.value.findIndex(f => f.id === selectedFunction.value?.id)
    if (index === -1) return
    const deletedId = selectedFunction.value.id!
    const isNew = deletedId.startsWith('new_')

    try {
      if (!isNew) await apiFetch(`/agents/${agentId.value}/tools/${deletedId}`, { method: 'DELETE' })
      functions.value.splice(index, 1)
      if (functions.value.length > 0) {
        selectedFunction.value = functions.value[0]
      } else {
        selectedFunction.value = null
        router.replace({ query: { ...route.query, functionId: undefined } })
      }
      unsavedChanges.value.delete(deletedId)
      showStatus('success', 'Функция удалена')
    } catch (e: any) {
      console.error('Failed to delete function', e)
      showStatus('error', `Ошибка удаления: ${getReadableErrorMessage(e, 'не удалось удалить функцию')}`)
    }
  }

  // Toggle status
  const toggleFunctionStatus = async (isActive: boolean) => {
    if (!selectedFunction.value || selectedFunction.value.id?.startsWith('new_')) return
    try {
      await apiFetch(`/tools/${selectedFunction.value.id}`, {
        method: 'PUT',
        body: { status: isActive ? 'active' : 'deprecated' }
      })
      selectedFunction.value.status = isActive ? 'active' : 'deprecated'
      showStatus('success', isActive ? 'Функция активирована' : 'Функция деактивирована')
    } catch {
      showStatus('error', 'Не удалось изменить статус')
    }
  }

  // Test
  const testTool = async (
    headers: Ref<Header[]>,
    bodyParameters: Ref<BodyParameter[]>,
    buildVariableMap: () => Record<string, string>,
    onTestComplete: (response: ToolTestResponse) => void
  ) => {
    if (!selectedFunction.value) return
    testing.value = true
    try {
      const variableMap = buildVariableMap()
      let args = {}
      try { args = JSON.parse(testPayload.value) } catch {
        testResult.value = {
          status_code: 0, latency_ms: 0, raw_body: { error: 'Invalid JSON in payload' },
          transformed_body: null, raw_size_bytes: 0, transformed_size_bytes: null,
          error: 'Invalid JSON', request_url: selectedFunction.value?.endpoint || '',
          request_method: selectedFunction.value?.http_method || 'POST'
        }
        testing.value = false
        return
      }
      args = resolveVariablesDeep(args, variableMap)

      const customHeaders: Record<string, string> = {}
      headers.value.forEach(h => {
        const headerKey = resolveVariableTokens(h.key, variableMap).trim()
        if (headerKey) customHeaders[headerKey] = resolveVariableTokens(h.value, variableMap)
      })

      let mapping = selectedFunction.value.parameter_mapping
      if (!mapping && bodyParameters.value.length > 0) {
        mapping = {}
        bodyParameters.value.forEach(p => { if (p.key) mapping![p.key] = p.location })
      }

      const credentialId = selectedBindingCredentialId.value || null
      const response = await apiFetch<ToolTestResponse>('/tools/test', {
        method: 'POST',
        body: {
          endpoint: resolveVariableTokens(selectedFunction.value.endpoint, variableMap),
          http_method: selectedFunction.value.http_method,
          args, parameter_mapping: mapping,
          custom_headers: Object.keys(customHeaders).length > 0 ? customHeaders : undefined,
          auth_type: selectedFunction.value.auth_type || 'none',
          credential_id: credentialId,
          response_transform: selectedFunction.value.response_transform
        }
      })
      testResult.value = response
      onTestComplete(response)
    } catch (error: any) {
      testResult.value = {
        status_code: 500, latency_ms: 0, raw_body: { error: error.message || 'Request failed' },
        transformed_body: null, raw_size_bytes: 0, transformed_size_bytes: null,
        error: error.message,
        request_url: selectedFunction.value.endpoint, request_method: selectedFunction.value.http_method
      }
    } finally {
      testing.value = false
    }
  }

  return {
    // State
    functions,
    selectedFunction,
    displayName,
    unsavedChanges,
    statusMessage,
    testing,
    testResult,
    testPayload,
    credentialsList,
    fetchCredentials,
    bindingCredentials,
    selectedBindingCredentialId,
    canSave,

    // Methods
    showStatus,
    markAsChanged,
    loadFunctions,
    createFunction,
    saveFunction,
    deleteFunction,
    toggleFunctionStatus,
    testTool,
  }
}
