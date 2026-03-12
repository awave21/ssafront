<template>
  <Sheet :open="isOpen" @update:open="(v) => !v && handleClose()">
    <SheetContent side="right" class-name="max-w-4xl flex flex-col">
      <!-- Header -->
      <SheetHeader>
        <div class="flex items-center justify-between">
          <SheetTitle>Настройки справочника</SheetTitle>
          <SheetClose />
        </div>
      </SheetHeader>

      <!-- Content (scrollable) -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <!-- Basic Info -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-sm font-medium text-slate-700">Название</label>
            <input
              v-model.trim="form.name"
              type="text"
              class="mt-1 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all"
            />
          </div>
          <div>
            <label class="text-sm font-medium text-slate-700">Имя функции</label>
            <input
              v-model.trim="form.tool_name"
              type="text"
              class="mt-1 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 font-mono focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all"
              :class="{ 'border-yellow-300 bg-yellow-50': toolNameChanged }"
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
            class="mt-1 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all resize-none"
          ></textarea>
        </div>

        <!-- Columns Section -->
        <div class="border-t border-slate-100 pt-5">
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

        <!-- Settings Columns -->
        <div class="border-t border-slate-100 pt-5">
          <div class="flex items-start gap-6">
            <!-- Response Mode -->
            <div class="flex-1">
              <label class="text-xs font-medium text-slate-500 mb-1.5 block">Режим ответа</label>
              <select
                v-model="form.response_mode"
                class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all"
              >
                <option value="function_result">Результат функции</option>
                <option value="direct_message">Прямое сообщение</option>
              </select>
              <p class="mt-1 text-xs text-slate-400">
                {{ form.response_mode === 'function_result' ? 'Агент сформулирует ответ сам' : 'Без обработки агентом' }}
              </p>
            </div>

            <!-- Search Type -->
            <div class="flex-1">
              <label class="text-xs font-medium text-slate-500 mb-1.5 block">Тип поиска</label>
              <select
                v-model="form.search_type"
                class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all"
              >
                <option value="exact">Точный</option>
                <option value="fuzzy">Нечёткий</option>
                <option value="semantic">Семантический</option>
              </select>
            </div>

            <!-- Enabled Toggle -->
            <div class="w-40 shrink-0">
              <label class="text-xs font-medium text-slate-500 mb-1.5 block">Статус</label>
              <label class="flex items-center gap-3 cursor-pointer px-3 py-2 rounded-md border border-slate-200 hover:border-slate-300 transition-all">
                <Switch v-model="form.is_enabled" />
                <span class="text-sm text-slate-700">{{ form.is_enabled ? 'Активен' : 'Выключен' }}</span>
              </label>
            </div>
          </div>
        </div>

        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      </div>

      <!-- Sticky Footer -->
      <div class="relative z-10 flex-shrink-0 border-t border-slate-200 bg-white px-6 py-3 pointer-events-auto">
        <div class="flex items-center justify-between">
          <button
            @click="showDeleteConfirm = true"
            class="px-3 py-1.5 text-sm text-red-500 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
          >
            Удалить
          </button>
          <div class="flex items-center gap-2">
            <button
              @click="handleClose"
              class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors"
            >
              Отмена
            </button>
            <button
              @click="handleSave"
              class="px-5 py-2 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
              :disabled="isSaving || !isValid"
            >
              <Loader2 v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
              {{ isSaving ? 'Сохранение...' : 'Сохранить' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Delete Confirmation Dialog -->
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
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import type { Directory, DirectoryColumn } from '~/types/directories'
import { Switch } from '~/components/ui/switch'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetClose,
} from '~/components/ui/sheet'
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogHeader
} from '~/components/ui/dialog'
import { isValidSlugName, validateToolName } from '~/utils/directory-helpers'
import ColumnEditor, { type ColumnDefinition } from './ColumnEditor.vue'

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
  response_mode: 'function_result' as 'function_result' | 'direct_message',
  search_type: 'fuzzy' as 'exact' | 'fuzzy' | 'semantic',
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
      tool_name: props.directory.tool_name,
      tool_description: props.directory.tool_description || '',
      response_mode: props.directory.response_mode || 'function_result',
      search_type: props.directory.search_type || 'fuzzy',
      is_enabled: props.directory.is_enabled,
      columns: cols
    }
    originalToolName.value = props.directory.tool_name
    originalColumns.value = JSON.parse(JSON.stringify(cols))
  }
}

const checkToolName = () => {
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
    tool_name: form.value.tool_name,
    tool_description: form.value.tool_description,
    response_mode: form.value.response_mode,
    search_type: form.value.search_type,
    is_enabled: form.value.is_enabled,
    columns: form.value.columns
  })
}

const handleDelete = () => {
  if (!props.directory) return
  isDeleting.value = true
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

  // When parent closes the sheet (e.g. after successful delete),
  // force-close nested confirm dialog so its overlay can't block UI.
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
