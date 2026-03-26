<template>
  <KnowledgeSheetShell
    :open="isOpen"
    title="Настройки справочника"
    :subtitle="directory?.name"
    :loading="isSaving || isDeleting"
    :submit-disabled="!isValid"
    size="lg"
    @close="handleClose"
    @cancel="handleClose"
    @submit="handleSave"
  >
    <template #header-actions>
      <div class="flex items-center gap-2 mr-2">
        <span class="text-xs text-slate-500">Статус</span>
        <Switch v-model="form.is_enabled" />
      </div>
    </template>

    <div class="p-6 space-y-6">
      <!-- Basic Info -->
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="text-sm font-medium text-slate-700">Название</label>
          <input
            v-model.trim="form.name"
            type="text"
            class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
          />
        </div>
        <div>
          <label class="text-sm font-medium text-slate-700">Имя функции</label>
          <input
            v-model.trim="form.tool_name"
            type="text"
            class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 font-mono focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
            :class="{ 'border-yellow-300 bg-yellow-50': toolNameChanged }"
            :readonly="isToolNameReadonly"
            :disabled="isToolNameReadonly"
          />
          <p v-if="toolNameChanged" class="mt-1 text-xs text-yellow-600">
            Изменение повлияет на промпт агента
          </p>
          <p v-if="toolNameError" class="mt-1 text-xs text-red-600">{{ toolNameError }}</p>
        </div>
      </div>

      <div>
        <label class="text-sm font-medium text-slate-700">Описание для агента</label>
        <textarea
          v-model.trim="form.tool_description"
          rows="2"
          class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none resize-none"
        ></textarea>
      </div>

      <div>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <label class="text-sm font-medium text-slate-700">Текст для системного промпта</label>
          <button
            type="button"
            class="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
            @click="copyPromptSnippet"
          >
            <ClipboardCopy class="w-3.5 h-3.5" />
            {{ promptSnippetCopied ? 'Скопировано' : 'Копировать' }}
          </button>
        </div>
        <textarea
          v-model.trim="form.prompt_usage_snippet"
          rows="2"
          class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none resize-none"
          :placeholder="promptUsageLinePlaceholder"
        ></textarea>
      </div>

      <!-- Columns (only when editable: custom / clipboard_import) -->
      <div v-if="canEditColumns" class="border-t border-slate-100 pt-5">
        <div class="flex items-center justify-between mb-3">
          <label class="text-sm font-medium text-slate-700">Колонки справочника</label>
          <span v-if="hasColumnsChanges" class="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded-lg">
            Изменения не сохранены
          </span>
        </div>

        <ColumnEditor
          v-model="editorColumns"
          :max-columns="15"
          ref="columnEditorRef"
        />
        <p v-if="columnsWarning" class="mt-2 text-xs text-amber-600 bg-amber-50 p-3 rounded-lg">
          {{ columnsWarning }}
        </p>
      </div>

      <!-- Settings -->
      <div class="border-t border-slate-100 pt-5">
        <div>
          <label class="text-xs font-medium text-slate-500 mb-1.5 block">Режим ответа</label>
          <select
            v-model="form.response_mode"
            class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
          >
            <option value="function_result">Результат функции</option>
            <option value="direct_message">Прямое сообщение</option>
          </select>
          <p class="mt-1 text-xs text-slate-400">
            {{ form.response_mode === 'function_result' ? 'Агент сформулирует ответ сам' : 'Без обработки агентом' }}
          </p>
        </div>
      </div>

      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    </div>

    <template #footer>
      <button
        @click="showDeleteConfirm = true"
        class="px-4 py-2 text-sm font-medium text-red-500 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
      >
        Удалить справочник
      </button>
      <div class="flex items-center gap-2">
        <button
          @click="handleClose"
          class="px-6 py-2.5 rounded-md border border-slate-200 bg-white text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          Отмена
        </button>
        <button
          @click="handleSave"
          :disabled="isSaving || !isValid"
          class="px-8 py-2.5 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          <Loader2 v-if="isSaving" class="w-4 h-4 animate-spin" />
          <span>Сохранить</span>
        </button>
      </div>
    </template>

    <!-- Delete Confirmation Dialog (Nested) -->
    <Dialog :open="showDeleteConfirm" @update:open="(v) => showDeleteConfirm = v">
      <DialogContent class-name="max-w-sm">
        <div class="p-6">
          <DialogHeader class="mb-4">
            <DialogTitle>Удалить справочник?</DialogTitle>
            <DialogDescription>
              Справочник "{{ directory?.name }}" и все его записи ({{ directory?.items_count }}) будут удалены безвозвратно.
            </DialogDescription>
          </DialogHeader>
          <div class="flex items-center gap-3 mt-6">
            <button
              @click="showDeleteConfirm = false"
              class="flex-1 px-4 py-2.5 rounded-md border border-slate-200 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
            >
              Отмена
            </button>
            <button
              @click="handleDelete"
              class="flex-1 px-4 py-2.5 bg-red-600 text-white rounded-md text-sm font-bold hover:bg-red-700 transition-colors"
              :disabled="isDeleting"
            >
              {{ isDeleting ? 'Удаление...' : 'Удалить' }}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </KnowledgeSheetShell>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { Loader2, ClipboardCopy } from 'lucide-vue-next'
import type { Directory, DirectoryColumn } from '~/types/directories'
import { Switch } from '~/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogHeader
} from '~/components/ui/dialog'
import { isValidSlugName, validateToolName } from '~/utils/directory-helpers'
import ColumnEditor, { type ColumnDefinition } from './ColumnEditor.vue'
import KnowledgeSheetShell from './KnowledgeSheetShell.vue'

const props = defineProps<{
  isOpen: boolean
  directory: Directory | null
  existingToolNames?: string[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: Partial<Directory>): void
  (e: 'delete', id: string): void
}>()

const form = ref({
  name: '',
  tool_name: '',
  tool_description: '',
  prompt_usage_snippet: '',
  response_mode: 'function_result' as 'function_result' | 'direct_message',
  is_enabled: true,
  columns: [] as DirectoryColumn[]
})

const isSaving = ref(false)
const isDeleting = ref(false)
const error = ref('')
const toolNameError = ref('')
const showDeleteConfirm = ref(false)

const originalToolName = ref('')
const originalColumns = ref<DirectoryColumn[]>([])

const toolNameChanged = computed(() => {
  return form.value.tool_name !== originalToolName.value
})

const fixedToolNameByTemplate: Record<string, string> = {
  qa: 'get_question_answer',
  service_catalog: 'get_service_info',
  product_catalog: 'get_product_info',
  company_info: 'get_company_info',
  theme_catalog: 'get_topic_info',
  medical_course_catalog: 'get_medical_course_info',
  clipboard_import: 'get_clipboard_import',
}

const canEditColumns = computed(() => {
  const t = props.directory?.template ?? ''
  return t === 'custom' || t === 'clipboard_import'
})

const promptUsageLinePlaceholder = computed(() => {
  const fn = form.value.tool_name?.trim() || '…'
  return `Вызывай ${fn}, когда нужна информация из этого справочника.`
})

const displayPromptSnippet = computed(() => {
  const s = form.value.prompt_usage_snippet?.trim()
  if (s) return s
  return promptUsageLinePlaceholder.value
})

const promptSnippetCopied = ref(false)
let promptSnippetCopiedTimer: ReturnType<typeof setTimeout> | null = null

const copyPromptSnippet = async () => {
  const text = displayPromptSnippet.value
  try {
    await navigator.clipboard.writeText(text)
    if (promptSnippetCopiedTimer) clearTimeout(promptSnippetCopiedTimer)
    promptSnippetCopied.value = true
    promptSnippetCopiedTimer = setTimeout(() => {
      promptSnippetCopied.value = false
      promptSnippetCopiedTimer = null
    }, 2000)
  } catch {
    error.value = 'Не удалось скопировать в буфер обмена'
  }
}
const isToolNameReadonly = computed(() => {
  const template = props.directory?.template
  if (!template) return false
  return template !== 'custom' || template in fixedToolNameByTemplate
})

const hasColumnsChanges = computed(() => {
  return JSON.stringify(form.value.columns) !== JSON.stringify(originalColumns.value)
})

const columnsWarning = computed(() => {
  if (!hasColumnsChanges.value) return ''
  
  const currentNames = form.value.columns.map(c => c.name)
  const removedCols = originalColumns.value.filter(c => !currentNames.includes(c.name))
  
  if (removedCols.length > 0 && props.directory && props.directory.items_count > 0) {
    return `Удаление колонок (${removedCols.map(c => c.label).join(', ')}) приведёт к потере данных в ${props.directory.items_count} записях`
  }
  
  return ''
})

const isValid = computed(() => {
  if (!form.value.name.trim()) return false
  if (!form.value.tool_name.trim()) return false
  if (!isValidSlugName(form.value.tool_name)) return false
  if (toolNameError.value) return false
  if (form.value.columns.length === 0) return false

  if (columnEditorRef.value) {
    return columnEditorRef.value.isValid()
  }

  const colNames = form.value.columns.map(c => c.name)
  const hasInvalidCol = form.value.columns.some(col =>
    !col.name || !col.label || !isValidSlugName(col.name)
  )
  const hasDuplicates = colNames.length !== new Set(colNames).size

  return !hasInvalidCol && !hasDuplicates
})

const initForm = () => {
  if (props.directory) {
    const cols = (props.directory.columns || []).map(c => ({
      name: c.name,
      label: c.label,
      type: c.type || 'text',
      required: c.required ?? false,
      searchable: c.searchable ?? false
    }))
    
    form.value = {
      name: props.directory.name,
      tool_name: fixedToolNameByTemplate[props.directory.template] || props.directory.tool_name,
      tool_description: props.directory.tool_description || '',
      prompt_usage_snippet: props.directory.prompt_usage_snippet || '',
      response_mode: props.directory.response_mode || 'function_result',
      is_enabled: props.directory.is_enabled,
      columns: props.directory.template === 'qa'
        ? [
            { name: 'question', label: 'Вопрос', type: 'text', required: true, searchable: true },
            { name: 'answer', label: 'Ответ', type: 'text', required: true, searchable: false },
          ]
        : cols
    }
    originalToolName.value = fixedToolNameByTemplate[props.directory.template] || props.directory.tool_name
    originalColumns.value = JSON.parse(JSON.stringify(cols))
  }
}

const checkToolName = () => {
  if (isToolNameReadonly.value) {
    toolNameError.value = ''
    return
  }
  toolNameError.value = validateToolName(
    form.value.tool_name,
    props.existingToolNames || [],
    originalToolName.value
  )
}

const columnEditorRef = ref<InstanceType<typeof ColumnEditor> | null>(null)

const editorColumns = computed({
  get: () => form.value.columns.map((c, i) => ({
    id: String(i),
    name: c.name,
    label: c.label,
    type: c.type,
    required: c.required,
    searchable: c.searchable ?? false
  })) as ColumnDefinition[],
  set: (cols: ColumnDefinition[]) => {
    form.value.columns = cols.map(({ id, ...rest }) => rest) as DirectoryColumn[]
  }
})

const handleClose = () => {
  error.value = ''
  toolNameError.value = ''
  showDeleteConfirm.value = false
  isSaving.value = false
  isDeleting.value = false
  emit('close')
}

const handleSave = () => {
  if (!isValid.value || !props.directory) return
  
  error.value = ''
  isSaving.value = true
  
  emit('save', {
    id: props.directory.id,
    name: form.value.name,
    tool_name: isToolNameReadonly.value ? undefined : form.value.tool_name,
    tool_description: form.value.tool_description,
    prompt_usage_snippet: form.value.prompt_usage_snippet,
    response_mode: form.value.response_mode,
    search_type: 'semantic',
    is_enabled: form.value.is_enabled,
    columns: canEditColumns.value ? form.value.columns : undefined
  })
}

const handleDelete = async () => {
  if (!props.directory) return
  isDeleting.value = true
  // Закрыть вложенный Dialog до запроса удаления: иначе портал reka-ui (z выше Sheet)
  // может остаться и блокировать клики после закрытия шита (radix-vue + reka-ui).
  showDeleteConfirm.value = false
  await nextTick()
  emit('delete', props.directory.id)
}

watch(() => props.isOpen, (open) => {
  if (open) {
    initForm()
    error.value = ''
    toolNameError.value = ''
    showDeleteConfirm.value = false
    isDeleting.value = false
    isSaving.value = false
    return
  }

  showDeleteConfirm.value = false
  isDeleting.value = false
  isSaving.value = false
})

watch(() => form.value.tool_name, () => {
  checkToolName()
})

defineExpose({
  setSaving: (value: boolean) => { isSaving.value = value },
  setDeleting: (value: boolean) => { isDeleting.value = value },
  setError: (err: string) => { error.value = err },
  close: handleClose
})
</script>
