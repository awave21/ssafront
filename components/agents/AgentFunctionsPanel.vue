<template>
  <div
    ref="editorRootRef"
    class="flex flex-col h-full bg-white overflow-hidden"
    @focusout="onEditorFocusOut"
  >
    <div class="flex flex-1 min-h-0 overflow-hidden">
      <!-- Sidebar -->
      <FunctionsList
        :functions="functions"
        :selected-id="selectedFunction?.id || null"
        :unsaved-changes="unsavedChanges"
        @select="selectFunction"
        @create="createFunction"
        @import-curl="showCurlImport = true"
      />

      <!-- Main Editor -->
      <div v-if="selectedFunction" class="flex-1 flex flex-col bg-white">
        <!-- Header -->
        <FunctionEditorHeader
          :display-name="displayName"
          :function-name="selectedFunction.name"
          :function-id="selectedFunction.id || ''"
          :description="selectedFunction.description || ''"
          @update:display-name="onDisplayNameUpdate"
          @update:description="onDescriptionUpdate"
        />

        <!-- Scrollable Content -->
        <div class="flex-1 overflow-y-auto p-6">
          <div class="bg-white rounded-lg p-3 mb-6">
            <div class="text-sm font-semibold mb-4 text-slate-900 flex items-center gap-2">
              <Server class="w-4 h-4 text-indigo-600" />
              Настройка Endpoint
            </div>

            <!-- Endpoint URL + Method -->
            <FunctionEndpointConfig
              :endpoint="selectedFunction.endpoint"
              :http-method="selectedFunction.http_method"
              :credential-id="selectedBindingCredentialId"
              :credentials="(credentialsList as any[])"
              :variables="variables"
              :has-secret-headers="hasSecretHeaders"
              @update:endpoint="onEndpointUpdate"
              @update:http-method="onHttpMethodUpdate"
              @update:credential-id="onCredentialUpdate"
              @insert-variable="onInsertUrlVariable"
              @remove-secret-headers="removeSecretHeaders"
              @register-url-ref="urlInputRef = $event"
            />

            <!-- Tabs -->
            <div class="flex gap-6 border-b border-slate-200 mb-6 mt-6">
              <button 
                v-for="tab in [
                  { id: 'Body', label: 'Параметры' },
                  { id: 'Headers', label: 'Заголовки' },
                  { id: 'Vars', label: 'Переменные', count: variables.length },
                  { id: 'Response', label: 'Фильтр ответа' }
                ]" 
                :key="tab.id"
                class="pb-2.5 text-[13px] font-medium relative transition-colors"
                :class="activeTab === tab.id ? 'text-slate-900' : 'text-slate-500 hover:text-slate-700'"
                @click="activeTab = tab.id"
              >
                {{ tab.label }}
                <span 
                  v-if="tab.count" 
                  class="ml-1 px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-indigo-100 text-indigo-600"
                >{{ tab.count }}</span>
                <div v-if="activeTab === tab.id" class="absolute bottom-0 left-0 w-full h-0.5 bg-indigo-600"></div>
              </button>
            </div>

            <!-- Headers Tab -->
            <div v-if="activeTab === 'Headers'">
              <FunctionHeadersTable
                :headers="headers"
                @add-header="addHeader"
                @remove-header="removeHeader"
                @update-header="onUpdateHeader"
              />
            </div>

            <!-- Body/Parameters Tab -->
            <div v-if="activeTab === 'Body'">
              <FunctionParametersTable
                :parameters="bodyParameters"
                :variables="variables"
                :view-mode="bodyViewMode"
                :json-value="bodyJson"
                @update:view-mode="onBodyViewModeUpdate"
                @update:json-value="onBodyJsonUpdate"
                @update-parameter="onUpdateParameter"
                @add-parameter="addBodyParameter"
                @remove-parameter="removeBodyParameter"
              />
            </div>

            <!-- Variables Tab -->
            <div v-if="activeTab === 'Vars'">
              <FunctionVariablesPanel
                :variables="variables"
                @add-variable="addVariable"
                @remove-variable="removeVariable"
                @update-variable="onUpdateVariable"
                @copy-variable="copyVariableToken"
              />
            </div>

            <!-- Response Filter Tab -->
            <div v-if="activeTab === 'Response'">
              <FunctionResponseFilter
                :field-tree="fieldTree"
                :preview-data="previewTransformed"
              >
                <template #field-tree>
                  <FieldNode 
                    v-for="field in fieldTree" 
                    :key="field.path"
                    :field="field"
                    @toggle="handleToggle"
                  />
                </template>
              </FunctionResponseFilter>
            </div>
          </div>
          
          <!-- AI Instructions -->
          <div class="bg-white border border-slate-200 rounded-lg p-5 shadow-sm">
            <div class="text-sm font-semibold mb-4 text-slate-900 flex items-center gap-2">
              <BrainCircuit class="w-4 h-4 text-indigo-600" />
              Инструкции для AI
            </div>
            <div class="text-[13px] text-slate-500 mb-3">
              Укажите, когда и как AI должен использовать эту функцию.
            </div>
            <textarea
              :value="selectedFunction.description"
              @input="onDescriptionUpdate(($event.target as HTMLTextAreaElement).value)"
              class="w-full border border-slate-200 rounded-md p-3 text-[13px] min-h-[80px] focus:border-indigo-500 outline-none resize-y"
              placeholder="Используй эту функцию когда пользователь хочет..."
            ></textarea>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="flex-1 flex items-center justify-center text-slate-400 flex-col gap-4">
        <div class="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center">
          <Code class="h-8 w-8 text-slate-400" />
        </div>
        <p>Выберите функцию для редактирования</p>
        <div class="flex items-center gap-3 mt-2">
          <button 
            @click="createFunction"
            class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
          >
            <Plus class="w-4 h-4" />
            Создать вручную
          </button>
          <button 
            @click="showCurlImport = true"
            class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Terminal class="w-4 h-4" />
            Импорт из cURL
          </button>
        </div>
      </div>

      <!-- Toggle Response Panel -->
      <button 
        v-if="selectedFunction && !showResponsePanel"
        @click="showResponsePanel = true"
        class="w-8 bg-slate-50 border-l border-slate-200 hover:bg-slate-100 transition-colors flex items-center justify-center text-slate-400 hover:text-slate-600"
        title="Показать ответ"
      >
        <ChevronLeft class="w-4 h-4" />
      </button>

      <!-- Right Panel: Response Output -->
      <div class="w-[420px] bg-white border-l border-slate-200 flex flex-col" v-if="selectedFunction && showResponsePanel">
        <div 
          class="h-10 flex items-center justify-between px-4 text-[11px] shrink-0 border-b border-slate-200"
          :class="testResult 
            ? (testResult.status_code >= 200 && testResult.status_code < 300 ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700') 
            : 'bg-slate-50 text-slate-500'"
        >
          <template v-if="testResult">
            <div class="flex items-center gap-2 flex-1 min-w-0">
              <span class="font-bold">{{ testResult.status_code }}</span>
              <span>{{ testResult.latency_ms }}ms</span>
              <span v-if="Array.isArray(testResult.raw_body)" class="opacity-75">
                {{ testResult.raw_body.length }} эл.
              </span>
            </div>
            <button @click="testResult = null; fieldTree = []" class="hover:opacity-70 ml-2">
              <X class="w-3 h-3" />
            </button>
          </template>
          <template v-else>
            <div class="flex items-center justify-between flex-1">
              <span class="font-semibold uppercase">Ответ</span>
              <button 
                @click="showResponsePanel = false"
                class="hover:bg-slate-200 p-1 rounded transition-colors"
                title="Скрыть"
              >
                <ChevronRight class="w-3.5 h-3.5" />
              </button>
            </div>
          </template>
        </div>
        <div
          class="flex-1 min-h-0 overflow-auto"
          :class="testResult ? 'bg-slate-900' : 'bg-white'"
        >
          <pre 
            v-if="testResult" 
            class="m-0 min-h-full p-3 text-slate-50 text-xs font-mono"
          >{{ JSON.stringify(testResult.raw_body, null, 2) }}</pre>
          <div v-else class="h-full flex items-center justify-center text-xs text-slate-400">
            Нажмите «Запустить» для выполнения запроса
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Status notification -->
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0 translate-y-2"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 translate-y-2"
  >
    <div 
      v-if="statusMessage" 
      class="fixed bottom-4 right-4 z-50 px-4 py-2.5 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2"
      :class="statusMessage.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'"
    >
      <Check v-if="statusMessage.type === 'success'" class="w-4 h-4" />
      <X v-else class="w-4 h-4" />
      {{ statusMessage.text }}
    </div>
  </Transition>

  <!-- cURL Import Dialog -->
  <CurlImportDialog
    :open="showCurlImport"
    :curl-input="curlInput"
    :error="curlError"
    @update:open="onCurlDialogToggle"
    @update:curl-input="(v: string) => curlInput = v"
    @import="importFromCurl"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, toRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Plus, Server, BrainCircuit, Code, X, Check, Terminal, ChevronLeft, ChevronRight
} from 'lucide-vue-next'
import type { Tool } from '~/types/tool'
import FieldNode from './FieldNode.vue'
import { parseCurl } from '~/utils/parse-curl'
import type { BodyParameter, ParameterType } from '~/utils/function-schema'

// Sub-components
import FunctionsList from './functions/FunctionsList.vue'
import FunctionEditorHeader from './functions/FunctionEditorHeader.vue'
import FunctionEndpointConfig from './functions/FunctionEndpointConfig.vue'
import FunctionParametersTable from './functions/FunctionParametersTable.vue'
import FunctionHeadersTable from './functions/FunctionHeadersTable.vue'
import FunctionVariablesPanel from './functions/FunctionVariablesPanel.vue'
import FunctionResponseFilter from './functions/FunctionResponseFilter.vue'
import CurlImportDialog from './functions/CurlImportDialog.vue'

// Composables
import { useFunctionsCrud, toSnakeSlug } from '~/composables/useFunctionsCrud'
import { useFunctionParameters, generateParameterId } from '~/composables/useFunctionParameters'
import { useVariables } from '~/composables/useVariables'
import { useResponseFilter } from '~/composables/useResponseFilter'

// Props
const props = defineProps<{ agentId: string }>()
const route = useRoute()
const router = useRouter()

// ── CRUD composable ──
const crud = useFunctionsCrud(toRef(props, 'agentId'))
const {
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
  showStatus,
  markAsChanged,
  loadFunctions,
  toggleFunctionStatus,
} = crud

// ── Variables composable (needs forward-ref to generateInputSchema) ──
let generateInputSchemaFn: () => void = () => {}
const vars = useVariables(
  selectedFunction,
  markAsChanged,
  showStatus,
  () => generateInputSchemaFn(),
)
const {
  variables,
  urlInputRef,
  addVariable,
  removeVariable,
  onVariableInput,
  copyVariableToken,
  insertVariableAtCursor,
  buildVariableMap,
} = vars

// ── Parameters composable ──
let isSelecting = false
const isAutoSaving = ref(false)
const pendingAutoSave = ref(false)

const hasUnsavedForSelected = () => {
  const id = selectedFunction.value?.id
  if (!id) return false
  return unsavedChanges.value.has(id)
}

const runAutoSave = async () => {
  if (isSelecting) return
  if (!hasUnsavedForSelected()) return
  if (!canSave.value) return
  if (isAutoSaving.value) {
    pendingAutoSave.value = true
    return
  }

  isAutoSaving.value = true
  try {
    await saveFunction()
  } finally {
    isAutoSaving.value = false
    if (pendingAutoSave.value) {
      pendingAutoSave.value = false
      await runAutoSave()
    }
  }
}

const autoSave = () => {
  void runAutoSave()
}

const params = useFunctionParameters(
  selectedFunction,
  variables,
  testPayload,
  markAsChanged,
  autoSave,
)
const {
  bodyParameters,
  bodyJson,
  bodyViewMode,
  addBodyParameter,
  removeBodyParameter,
  updateBodyParameter,
  onBodyParameterInput,
  syncFieldsToJson,
  syncJsonToFields,
  generateTestPayload,
  loadBodyParametersFromSchema,
  generateInputSchema,
} = params

// Wire forward-ref now that params is initialized
generateInputSchemaFn = generateInputSchema

// ── Response filter composable ──
const filter = useResponseFilter(selectedFunction, testResult, markAsChanged)
const {
  fieldTree,
  showResponsePanel,
  handleToggle,
  previewTransformed,
  onTestComplete,
} = filter

// ── Local state ──
const activeTab = ref('Body')
type Header = { key: string; value: string }
const headers = ref<Header[]>([])
const showCurlImport = ref(false)
const curlInput = ref('')
const curlError = ref('')

// Secret headers
const SECRET_HEADER_NAMES = new Set(['apikey', 'authorization', 'x-api-key', 'x-auth-token'])
const hasSecretHeaders = computed(() => {
  if (!selectedBindingCredentialId.value) return false
  return headers.value.some(h => SECRET_HEADER_NAMES.has(h.key.toLowerCase()))
})
const removeSecretHeaders = () => {
  headers.value = headers.value.filter(h => !SECRET_HEADER_NAMES.has(h.key.toLowerCase()))
  markAsChanged()
  showStatus('success', 'Секретные заголовки удалены')
}

// Headers management
const addHeader = () => { headers.value.push({ key: '', value: '' }); markAsChanged() }
const removeHeader = (index: number) => { headers.value.splice(index, 1); markAsChanged(); autoSave() }
const onHeaderInput = () => { markAsChanged() }

// ── Bridge methods for sub-component emits ──
const onDisplayNameUpdate = (value: string) => {
  displayName.value = value
  if (!selectedFunction.value) return
  selectedFunction.value.name = toSnakeSlug(value)
  if (selectedFunction.value.input_schema) selectedFunction.value.input_schema._displayName = value
  markAsChanged()
}

const onDescriptionUpdate = (value: string) => {
  if (!selectedFunction.value) return
  selectedFunction.value.description = value
  markAsChanged()
}

const onEndpointUpdate = (value: string) => {
  if (!selectedFunction.value) return
  selectedFunction.value.endpoint = value
  markAsChanged()
}

const onHttpMethodUpdate = (value: string) => {
  if (!selectedFunction.value) return
  selectedFunction.value.http_method = value as Tool['http_method']
  markAsChanged()
}

const onCredentialUpdate = (value: string | null) => {
  selectedBindingCredentialId.value = value
}

const onInsertUrlVariable = (name: string) => {
  insertVariableAtCursor('url', -1, name)
}

const onBodyViewModeUpdate = (mode: 'fields' | 'json') => {
  bodyViewMode.value = mode
}

const onBodyJsonUpdate = (value: string) => {
  bodyJson.value = value
  markAsChanged()
}

const onCurlDialogToggle = (open: boolean) => {
  showCurlImport.value = open
  if (!open) { curlInput.value = ''; curlError.value = '' }
}

const onUpdateHeader = (index: number, field: 'key' | 'value', value: string) => {
  headers.value[index][field] = value
  onHeaderInput()
}

const onUpdateParameter = (index: number, field: keyof BodyParameter, value: any) => {
  updateBodyParameter(index, field, value)
}

const onUpdateVariable = (index: number, field: 'name' | 'value' | 'description', value: string) => {
  variables.value[index][field] = value
  onVariableInput()
}

const editorRootRef = ref<HTMLElement | null>(null)

const onEditorFocusOut = (event: FocusEvent) => {
  const root = editorRootRef.value
  if (!root) return
  const source = event.target as Node | null
  if (!source || !root.contains(source)) return
  void runAutoSave()
}

const onWindowBlur = () => { void runAutoSave() }
const onVisibilityChange = () => {
  if (document.visibilityState === 'hidden') void runAutoSave()
}

// ── Select function (orchestrator) ──
const selectFunction = async (func: Tool) => {
  if (selectedFunction.value?.id && selectedFunction.value.id !== func.id) {
    await runAutoSave()
  }

  isSelecting = true
  selectedFunction.value = func

  if (func.id && !func.id.startsWith('new_')) {
    router.replace({ query: { ...route.query, functionId: func.id } })
  }

  displayName.value = func.input_schema?._displayName || func.name || ''

  // Load headers
  const headersData = (func as any).custom_headers || func.headers
  headers.value = headersData && typeof headersData === 'object'
    ? Object.entries(headersData).map(([key, value]) => ({ key, value: value as string }))
    : []

  // Restore field tree
  const savedTree = (func.response_transform as any)?._fieldTree
  fieldTree.value = Array.isArray(savedTree) ? savedTree : []
  testResult.value = null
  variables.value = []

  if (func.id?.startsWith('new_')) {
    bodyParameters.value = []
    bodyJson.value = '{}'
    testPayload.value = '{}'
  } else {
    loadBodyParametersFromSchema(func)
    generateTestPayload()
  }
  isSelecting = false
}

// ── Create function ──
const createFunction = () => {
  const newTool = crud.createFunction()
  bodyParameters.value = []
  bodyJson.value = '{}'
  variables.value = []
  headers.value = []
  fieldTree.value = []
  testResult.value = null
  testPayload.value = '{}'
  return newTool
}

// ── Save function ──
const saveFunction = async () => {
  await crud.saveFunction(headers, bodyParameters)
}

// ── Delete function ──
const deleteFunction = async () => {
  // Save current selected for re-select after deletion
  const wasSelected = selectedFunction.value
  await crud.deleteFunction()

  // If crud deleted successfully and reset selectedFunction, re-select first
  if (selectedFunction.value && selectedFunction.value !== wasSelected) {
    selectFunction(selectedFunction.value)
  }
}

// ── Test tool ──
const testTool = async () => {
  await crud.testTool(headers, bodyParameters, buildVariableMap, onTestComplete)
}

// ── Import from cURL ──
const importFromCurl = () => {
  curlError.value = ''
  const raw = curlInput.value.trim()
  if (!raw) { curlError.value = 'Вставьте cURL команду'; return }

  try {
    const parsed = parseCurl(raw)
    if (!parsed.url) { curlError.value = 'Не удалось извлечь URL из команды'; return }

    createFunction()
    if (!selectedFunction.value) return

    selectedFunction.value.endpoint = parsed.url
    selectedFunction.value.http_method = parsed.method
    selectedFunction.value.auth_type = parsed.authType
    if (parsed.authType !== 'none' && parsed.authValue) selectedFunction.value.credential_id = parsed.authValue

    const skipHeaders = new Set(['content-type', 'authorization'])
    const importedHeaders: Header[] = Object.entries(parsed.headers)
      .filter(([key]) => !skipHeaders.has(key.toLowerCase()))
      .map(([key, value]) => ({ key, value }))
    const authEntry = Object.entries(parsed.headers).find(([k]) => k.toLowerCase() === 'authorization')
    if (authEntry) importedHeaders.unshift({ key: authEntry[0], value: authEntry[1] })
    headers.value = importedHeaders

    const toBodyParam = (p: { key: string; value: string }, loc: 'body' | 'query'): BodyParameter => ({
      id: generateParameterId(), key: p.key, location: loc, type: 'string',
      value: p.value, fromAI: false, aiDescription: '', aiDefaultValue: ''
    })
    const allParams: BodyParameter[] = []
    parsed.queryParams.forEach(p => allParams.push(toBodyParam(p, 'query')))
    parsed.bodyParams.forEach(p => allParams.push(toBodyParam(p, 'body')))

    if (parsed.bodyJson && typeof parsed.bodyJson === 'object' && !Array.isArray(parsed.bodyJson)) {
      Object.entries(parsed.bodyJson).forEach(([key, value]) => {
        let type: ParameterType = 'string'
        let strValue = String(value)
        if (typeof value === 'number') type = 'number'
        else if (typeof value === 'boolean') type = 'boolean'
        else if (Array.isArray(value)) { type = 'array'; strValue = JSON.stringify(value) }
        else if (typeof value === 'object' && value !== null) { type = 'object'; strValue = JSON.stringify(value) }
        allParams.push({ id: generateParameterId(), key, location: 'body', type, value: strValue, fromAI: false, aiDescription: '', aiDefaultValue: '' })
      })
    }

    if (allParams.length > 0) {
      bodyParameters.value = allParams
      generateInputSchema()
      generateTestPayload()
      syncFieldsToJson()
    } else if (parsed.body && !parsed.bodyJson) {
      bodyJson.value = parsed.body
      bodyViewMode.value = 'json'
    }

    try {
      const urlObj = new URL(parsed.url)
      const pathParts = urlObj.pathname.split('/').filter(Boolean)
      if (pathParts.length > 0) {
        const lastPart = pathParts[pathParts.length - 1].replace(/[^a-zA-Z0-9]/g, '_').replace(/_+/g, '_').toLowerCase()
        const suggestedName = `${parsed.method.toLowerCase()}_${lastPart}`
        displayName.value = suggestedName
        selectedFunction.value.name = suggestedName
        if (selectedFunction.value.input_schema) selectedFunction.value.input_schema._displayName = suggestedName
      }
    } catch { /* skip */ }

    markAsChanged()
    showCurlImport.value = false
    curlInput.value = ''
    showStatus('success', 'Функция импортирована из cURL')
  } catch (e: any) {
    curlError.value = `Ошибка парсинга: ${e.message || 'неверный формат'}`
  }
}

// ── Duplicate function ──
const duplicateFunction = () => {
  if (!selectedFunction.value) return
  const src = selectedFunction.value
  const copyLabel = (src.input_schema?._displayName || src.name || '') + ' (копия)'
  const copySlug = toSnakeSlug(copyLabel)

  const headersCopy: Header[] = headers.value.map(h => ({ ...h }))
  const bodyParamsCopy: BodyParameter[] = bodyParameters.value.map(p => ({ ...p }))
  const customHeadersObj: Record<string, string> = {}
  headersCopy.forEach(h => { if (h.key.trim()) customHeadersObj[h.key] = h.value })

  const cloned: Tool = {
    id: `new_${Date.now()}`, name: copySlug, description: src.description || '',
    endpoint: src.endpoint || '', http_method: src.http_method || 'POST',
    execution_type: src.execution_type || 'http_webhook', auth_type: src.auth_type || 'none',
    credential_id: src.credential_id,
    input_schema: src.input_schema ? JSON.parse(JSON.stringify({ ...src.input_schema, _displayName: copyLabel })) : { type: 'object', properties: {} },
    parameter_mapping: src.parameter_mapping ? JSON.parse(JSON.stringify(src.parameter_mapping)) : null,
    response_transform: src.response_transform ? JSON.parse(JSON.stringify(src.response_transform)) : null,
    headers: Object.keys(customHeadersObj).length > 0 ? customHeadersObj : null,
    status: 'active', version: 1
  }
  if (Object.keys(customHeadersObj).length > 0) (cloned as any).custom_headers = customHeadersObj

  functions.value.unshift(cloned)
  unsavedChanges.value.add(cloned.id!)

  isSelecting = true
  selectedFunction.value = cloned
  displayName.value = copyLabel
  headers.value = headersCopy
  bodyParameters.value = bodyParamsCopy
  syncFieldsToJson()
  generateTestPayload()

  const savedTree = (cloned.response_transform as any)?._fieldTree
  fieldTree.value = Array.isArray(savedTree) ? savedTree : []
  testResult.value = null

  const clonedVars: { name: string; value: string; description: string }[] = []
  if (cloned.input_schema?.properties) {
    Object.entries(cloned.input_schema.properties).forEach(([key, prop]: [string, any]) => {
      if (prop['x-variable'] === true) {
        clonedVars.push({ name: key, value: prop.default !== undefined ? String(prop.default) : '', description: (prop.description || '').replace(/^Variable: /, '') })
      }
    })
  }
  variables.value = clonedVars
  isSelecting = false
  showStatus('success', 'Функция дублирована — сохраните для подтверждения')
}

// ── Sync body view mode ──
watch(bodyViewMode, (newMode, oldMode) => {
  if (oldMode === 'fields' && newMode === 'json') syncFieldsToJson()
  else if (oldMode === 'json' && newMode === 'fields') syncJsonToFields()
})

// ── Init ──
onMounted(async () => {
  window.addEventListener('blur', onWindowBlur)
  document.addEventListener('visibilitychange', onVisibilityChange)

  await Promise.all([loadFunctions(), fetchCredentials()])
  // Restore selection from URL or select first
  if (functions.value.length > 0) {
    const idFromUrl = route.query.functionId as string | undefined
    const target = (idFromUrl && functions.value.find(f => f.id === idFromUrl)) || functions.value[0]
    await selectFunction(target)
  }

})

onBeforeUnmount(() => {
  window.removeEventListener('blur', onWindowBlur)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

// ── Expose to parent ──
defineExpose({
  testTool,
  testing,
  testingRef: testing,
  selectedFunction,
  selectedFunctionRef: selectedFunction,
  deleteFunction,
  duplicateFunction,
  toggleFunctionStatus,
  canSave,
  canSaveRef: canSave,
  saveFunction,
})
</script>
