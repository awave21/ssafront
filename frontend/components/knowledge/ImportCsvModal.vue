<template>
  <Dialog :open="isOpen" @update:open="(v) => !v && handleClose()">
    <DialogContent class-name="max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between p-6 border-b border-slate-100">
        <DialogHeader>
          <DialogTitle>Импорт из CSV</DialogTitle>
          <DialogDescription>{{ directoryName }}</DialogDescription>
        </DialogHeader>
        <DialogClose />
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-6">
        <!-- Step 1: File Upload -->
        <div v-if="step === 'upload'">
          <div
            class="border-2 border-dashed border-slate-200 rounded-md p-8 text-center hover:border-indigo-300 hover:bg-indigo-50/30 transition-all cursor-pointer"
            :class="{ 'border-indigo-400 bg-indigo-50': isDragging }"
            @dragover.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
          >
            <input
              ref="fileInputRef"
              type="file"
              accept=".csv,.xlsx,.xls"
              class="hidden"
              @change="handleFileSelect"
            />
            <Upload class="w-12 h-12 text-slate-400 mx-auto mb-4" />
            <p class="text-slate-700 font-medium">Перетащите файл сюда</p>
            <p class="text-slate-500 text-sm mt-1">или нажмите для выбора</p>
            <p class="text-slate-400 text-xs mt-3">Поддерживаются .csv и .xlsx до 10 МБ</p>
          </div>
          
          <p v-if="uploadError" class="mt-4 text-sm text-red-600">{{ uploadError }}</p>
        </div>

        <!-- Step 2: Mapping -->
        <div v-else-if="step === 'mapping'" class="space-y-5">
          <!-- File info -->
          <div class="flex items-center justify-between bg-slate-50 rounded-md p-4">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-white rounded-lg flex items-center justify-center border border-slate-200">
                <FileSpreadsheet class="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <p class="font-medium text-slate-900 text-sm">{{ selectedFile?.name }}</p>
                <p class="text-xs text-slate-500">{{ previewData?.rows_count }} строк</p>
              </div>
            </div>
            <button
              @click="resetFile"
              class="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
              title="Удалить файл"
            >
              <Trash2 class="w-4 h-4" />
            </button>
          </div>

          <!-- Column Mapping -->
          <div>
            <p class="text-sm font-medium text-slate-700 mb-3">Сопоставьте колонки файла с полями справочника</p>
            <div class="space-y-3">
              <div 
                v-for="fileCol in previewData?.columns" 
                :key="fileCol"
                class="flex items-center gap-3"
              >
                <div class="flex-1 px-4 py-2.5 bg-slate-50 rounded-lg text-sm text-slate-700 truncate border border-slate-100">
                  "{{ fileCol }}"
                </div>
                <ArrowRight class="w-4 h-4 text-slate-400 flex-shrink-0" />
                <select
                  v-model="columnMapping[fileCol]"
                  class="flex-1 px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm text-slate-700 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                >
                  <option :value="null">— Пропустить —</option>
                  <option 
                    v-for="col in columns" 
                    :key="col.name" 
                    :value="col.name"
                    :disabled="isMapped(col.name, fileCol)"
                  >
                    {{ col.label }}
                  </option>
                </select>
              </div>
            </div>
          </div>

          <!-- Options -->
          <div class="space-y-3 pt-2">
            <label class="flex items-center gap-3 cursor-pointer">
              <input
                v-model="hasHeader"
                type="checkbox"
                class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span class="text-sm text-slate-700">Первая строка — заголовки</span>
            </label>
            <label class="flex items-center gap-3 cursor-pointer">
              <input
                v-model="replaceAll"
                type="checkbox"
                class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span class="text-sm text-slate-700">Заменить все существующие записи</span>
            </label>
          </div>

          <!-- Preview Table -->
          <div v-if="previewData?.preview?.length" class="pt-2">
            <p class="text-sm font-medium text-slate-700 mb-3">Превью (первые 3 записи)</p>
            <div class="overflow-x-auto rounded-lg border border-slate-200">
              <table class="w-full text-sm">
                <thead>
                  <tr class="bg-slate-50 border-b border-slate-200">
                    <th 
                      v-for="(fileCol, idx) in previewData.columns" 
                      :key="idx"
                      class="px-3 py-2 text-left text-xs font-bold text-slate-500 uppercase whitespace-nowrap"
                    >
                      {{ getMappedLabel(fileCol) || fileCol }}
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="(row, rowIdx) in previewData.preview" :key="rowIdx">
                    <td 
                      v-for="(cell, cellIdx) in row" 
                      :key="cellIdx"
                      class="px-3 py-2 text-slate-600 truncate max-w-[200px]"
                    >
                      {{ cell || '—' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <p v-if="mappingError" class="text-sm text-red-600">{{ mappingError }}</p>
        </div>

        <!-- Step 3: Result -->
        <div v-else-if="step === 'result'" class="text-center py-6">
          <div 
            class="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
            :class="[importResult?.errors?.length ? 'bg-yellow-100' : 'bg-emerald-100']"
          >
            <component 
              :is="importResult?.errors?.length ? AlertCircle : CheckCircle" 
              class="w-8 h-8"
              :class="[importResult?.errors?.length ? 'text-yellow-600' : 'text-emerald-600']"
            />
          </div>
          <h3 class="text-lg font-bold text-slate-900">
            {{ importResult?.errors?.length ? 'Импорт завершён с предупреждениями' : 'Импорт успешно завершён' }}
          </h3>
          <p class="text-slate-500 mt-2">
            Добавлено записей: <span class="font-bold text-slate-700">{{ importResult?.created }}</span>
          </p>
          <p v-if="importResult?.errors?.length" class="text-slate-500">
            Пропущено (ошибки): <span class="font-bold text-yellow-600">{{ importResult.errors.length }}</span>
          </p>
          
          <button
            v-if="importResult?.errors?.length"
            @click="downloadErrorLog"
            class="mt-4 px-4 py-2 text-sm text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50 rounded-lg transition-colors"
          >
            Скачать лог ошибок
          </button>
        </div>
      </div>

      <!-- Footer -->
      <DialogFooter class-name="p-6 border-t border-slate-100 bg-slate-50">
        <button
          v-if="step !== 'result'"
          type="button"
          class="px-5 py-2.5 rounded-md border border-slate-200 bg-white text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
          @click="handleClose"
        >
          Отмена
        </button>
        <button
          v-if="step === 'mapping'"
          @click="handleImport"
          class="px-6 py-2.5 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          :disabled="isImporting || !hasValidMapping"
        >
          <Loader2 v-if="isImporting" class="w-4 h-4 animate-spin" />
          <span>{{ isImporting ? 'Импорт...' : 'Импортировать' }}</span>
        </button>
        <button
          v-if="step === 'result'"
          @click="handleClose"
          class="px-6 py-2.5 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 transition-colors"
        >
          Готово
        </button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { 
  Upload, 
  FileSpreadsheet, 
  Trash2, 
  ArrowRight, 
  Loader2,
  CheckCircle,
  AlertCircle
} from 'lucide-vue-next'
import type { DirectoryColumn, ImportResult } from '~/types/directories'
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogClose,
  DialogHeader,
  DialogFooter
} from '~/components/ui/dialog'

type PreviewData = {
  columns: string[]
  rows_count: number
  preview: string[][]
  suggested_mapping?: Record<string, string | null>
}

const props = defineProps<{
  isOpen: boolean
  directoryName: string
  columns: DirectoryColumn[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'import', file: File, mapping: Record<string, string | null>, options: { hasHeader: boolean; replaceAll: boolean }): void
}>()

const step = ref<'upload' | 'mapping' | 'result'>('upload')
const isDragging = ref(false)
const selectedFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadError = ref('')
const mappingError = ref('')
const isImporting = ref(false)

const previewData = ref<PreviewData | null>(null)
const columnMapping = ref<Record<string, string | null>>({})
const hasHeader = ref(true)
const replaceAll = ref(false)
const importResult = ref<ImportResult | null>(null)

const hasValidMapping = computed(() => {
  const mappedColumns = Object.values(columnMapping.value).filter(v => v !== null)
  const requiredColumns = props.columns.filter(c => c.required).map(c => c.name)
  return requiredColumns.every(name => mappedColumns.includes(name))
})

const isMapped = (colName: string, currentFileCol: string) => {
  return Object.entries(columnMapping.value).some(
    ([fileCol, mapped]) => mapped === colName && fileCol !== currentFileCol
  )
}

const getMappedLabel = (fileCol: string) => {
  const mapped = columnMapping.value[fileCol]
  if (!mapped) return null
  const col = props.columns.find(c => c.name === mapped)
  return col?.label
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleFileSelect = (e: Event) => {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) {
    processFile(input.files[0])
  }
}

const handleDrop = (e: DragEvent) => {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) {
    processFile(file)
  }
}

const processFile = async (file: File) => {
  uploadError.value = ''
  
  const validTypes = ['.csv', '.xlsx', '.xls']
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  if (!validTypes.includes(ext)) {
    uploadError.value = 'Поддерживаются только файлы .csv и .xlsx'
    return
  }
  
  if (file.size > 10 * 1024 * 1024) {
    uploadError.value = 'Файл слишком большой. Максимум 10 МБ'
    return
  }
  
  selectedFile.value = file
  
  try {
    const text = await file.text()
    const lines = text.split('\n').filter(line => line.trim())
    const delimiter = text.includes(';') ? ';' : ','
    
    const columns = lines[0]?.split(delimiter).map(s => s.trim().replace(/^"|"$/g, '')) || []
    const preview = lines.slice(1, 4).map(line => 
      line.split(delimiter).map(s => s.trim().replace(/^"|"$/g, ''))
    )
    
    previewData.value = {
      columns,
      rows_count: lines.length - 1,
      preview
    }
    
    const mapping: Record<string, string | null> = {}
    for (const fileCol of columns) {
      const lowerFileCol = fileCol.toLowerCase()
      const matchedCol = props.columns.find(c => 
        c.label.toLowerCase() === lowerFileCol ||
        c.name.toLowerCase() === lowerFileCol
      )
      mapping[fileCol] = matchedCol?.name || null
    }
    columnMapping.value = mapping
    
    step.value = 'mapping'
  } catch {
    uploadError.value = 'Не удалось прочитать файл'
  }
}

const resetFile = () => {
  selectedFile.value = null
  previewData.value = null
  columnMapping.value = {}
  step.value = 'upload'
}

const handleImport = () => {
  if (!selectedFile.value || !hasValidMapping.value) return
  
  mappingError.value = ''
  isImporting.value = true
  
  emit('import', selectedFile.value, columnMapping.value, {
    hasHeader: hasHeader.value,
    replaceAll: replaceAll.value
  })
}

const downloadErrorLog = () => {
  if (!importResult.value?.errors?.length) return
  
  const content = importResult.value.errors
    .map(e => `Строка ${e.row}: ${e.error}`)
    .join('\n')
  
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'import-errors.txt'
  a.click()
  URL.revokeObjectURL(url)
}

const handleClose = () => {
  step.value = 'upload'
  selectedFile.value = null
  previewData.value = null
  columnMapping.value = {}
  uploadError.value = ''
  mappingError.value = ''
  isImporting.value = false
  importResult.value = null
  hasHeader.value = true
  replaceAll.value = false
  emit('close')
}

const setResult = (result: ImportResult) => {
  importResult.value = result
  isImporting.value = false
  step.value = 'result'
}

const setError = (error: string) => {
  mappingError.value = error
  isImporting.value = false
}

watch(() => props.isOpen, (open) => {
  if (!open) {
    handleClose()
  }
})

defineExpose({
  setResult,
  setError
})
</script>
