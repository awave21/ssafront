<template>
  <div class="max-w-full space-y-6 overflow-hidden">
    <!-- Header with Create Button -->
    <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div class="flex flex-wrap items-center gap-2">
        <input
          ref="fileInputRef"
          type="file"
          accept=".csv,.xlsx,.xls"
          class="hidden"
          @change="handleFileSelect"
        />
        <button
          @click="$emit('create')"
          class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl bg-indigo-600 px-5 text-sm font-bold text-white transition-colors hover:bg-indigo-700"
        >
          <Plus class="w-4 h-4" />
          Добавить
        </button>
        <button
          type="button"
          :disabled="isImporting"
          @click="openFilePicker"
          class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
          :class="isImporting ? 'opacity-60 cursor-not-allowed' : ''"
        >
          <Loader2 v-if="isImporting" class="w-4 h-4 animate-spin" />
          <Upload v-else class="w-4 h-4" />
          {{ isImporting ? 'Импорт...' : 'Загрузить' }}
        </button>
        <button
          type="button"
          :disabled="isImporting"
          @click="openFilePicker"
          class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
          :class="isImporting ? 'opacity-60 cursor-not-allowed' : ''"
        >
          <FileSpreadsheet class="w-4 h-4" />
          Загрузить из Excel
        </button>
        <button
          type="button"
          @click="handleExport"
          class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
        >
          <Download class="w-4 h-4" />
          Выгрузить в Excel
        </button>
      </div>

      <div v-if="questions.length > 0" class="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
        <div class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
          <span class="font-medium text-slate-900">Всего:</span>
          <span>{{ totalQuestionsCount }}</span>
        </div>
        <div class="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
          <span class="font-medium">Активных:</span>
          <span>{{ activeQuestionsCount }}</span>
        </div>
        <div class="relative min-w-0 grow sm:grow-0">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Поиск..."
            class="h-10 w-full min-w-0 rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm transition-all duration-300 outline-none focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 sm:w-64"
          />
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-12">
      <Loader2 class="w-8 h-8 animate-spin text-indigo-600" />
    </div>

    <!-- Empty State -->
    <div 
      v-else-if="questions.length === 0" 
      class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center"
    >
      <div class="max-w-md mx-auto">
        <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <MessageSquare class="h-8 w-8 text-slate-400" />
        </div>
        <h3 class="text-lg font-bold text-slate-900">Прямых вопросов пока нет</h3>
        <p class="text-slate-500 mt-2 mb-6">
          Создайте сценарии ответов на конкретные вопросы пользователей
        </p>
        <button
          @click="$emit('create')"
          class="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-bold text-white transition-colors hover:bg-indigo-700"
        >
          Добавить первый вопрос
        </button>
      </div>
    </div>

    <!-- No Results -->
    <div 
      v-else-if="filteredQuestions.length === 0" 
      class="rounded-3xl border border-slate-100 bg-white p-8 text-center"
    >
      <p class="text-slate-500">Ничего не найдено по запросу "{{ searchQuery }}"</p>
    </div>

    <!-- Questions List -->
    <Draggable
      v-else-if="canReorder"
      v-model="orderedQuestionsState"
      item-key="id"
      handle=".direct-question-drag-handle"
      class="grid max-w-full gap-4"
      ghost-class="opacity-40"
      chosen-class="z-10"
      drag-class="rotate-[0.5deg]"
      :animation="180"
      @end="handleDragEnd"
    >
      <template #item="{ element }">
        <div class="min-w-0 max-w-full rounded-xl transition-colors">
          <DirectQuestionCard
            :question="element"
            reorderable
            @click="$emit('select', element)"
            @toggle="(enabled: boolean) => $emit('toggle', element.id, enabled)"
            @delete="$emit('delete', element.id)"
          />
        </div>
      </template>
    </Draggable>

    <div v-else class="grid max-w-full gap-4">
      <DirectQuestionCard
        v-for="q in filteredQuestions"
        :key="q.id"
        :question="q"
        :reorderable="false"
        @click="$emit('select', q)"
        @toggle="(enabled: boolean) => $emit('toggle', q.id, enabled)"
        @delete="$emit('delete', q.id)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Plus, Search, Loader2, MessageSquare, Upload, FileSpreadsheet, Download } from 'lucide-vue-next'
import Draggable from 'vuedraggable'
import DirectQuestionCard from './DirectQuestionCard.vue'
import type { DirectQuestion } from '~/types/knowledge'

const props = defineProps<{
  questions: DirectQuestion[]
  loading?: boolean
  isImporting?: boolean
}>()

const emit = defineEmits<{
  (e: 'create'): void
  (e: 'select', question: DirectQuestion): void
  (e: 'toggle', id: string, enabled: boolean): void
  (e: 'delete', id: string): void
  (e: 'import-excel', file: File): void
  (e: 'reorder', ids: string[]): void
}>()

const searchQuery = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const orderedQuestionsState = ref<DirectQuestion[]>([])

watch(
  () => props.questions,
  (questions) => {
    const previousOrder = orderedQuestionsState.value.map((question) => question.id)
    const mapById = new Map(questions.map((question) => [question.id, question]))
    const ordered = previousOrder
      .map((id) => mapById.get(id))
      .filter((question): question is DirectQuestion => Boolean(question))
    const missing = questions.filter((question) => !previousOrder.includes(question.id))
    orderedQuestionsState.value = [...ordered, ...missing]
  },
  { immediate: true }
)

const openFilePicker = () => {
  if (props.isImporting) return
  fileInputRef.value?.click()
}

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  emit('import-excel', file)
  input.value = ''
}

const filteredQuestions = computed(() => {
  if (!searchQuery.value.trim()) return orderedQuestionsState.value
  const query = searchQuery.value.toLowerCase()
  return orderedQuestionsState.value.filter(q => 
    q.title.toLowerCase().includes(query) ||
    q.search_title.toLowerCase().includes(query) ||
    q.tags.some(t => t.toLowerCase().includes(query))
  )
})

const totalQuestionsCount = computed(() => props.questions.length)
const activeQuestionsCount = computed(() => props.questions.filter((question) => question.is_enabled).length)

const canReorder = computed(() => !searchQuery.value.trim() && orderedQuestionsState.value.length > 1)
const handleDragEnd = () => {
  emit('reorder', orderedQuestionsState.value.map((question) => question.id))
}

const exportColumns = ['title', 'description']

const downloadXlsx = async (rows: string[][], filename: string) => {
  const XLSX = await import('xlsx')
  const worksheet = XLSX.utils.aoa_to_sheet(rows)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'DirectQuestions')
  XLSX.writeFile(workbook, filename)
}

const createTemplateRows = (): string[][] => [
  exportColumns,
  [
    'Позвать менеджера',
    'Сейчас передам ваш запрос менеджеру. Ожидайте ответ.'
  ]
]

const createQuestionsRows = (): string[][] => {
  const dataRows = props.questions.map(question => [
    question.title,
    question.content
  ])

  return [exportColumns, ...dataRows]
}

const handleExport = async () => {
  if (!props.questions.length) {
    await downloadXlsx(createTemplateRows(), 'direct-questions-template.xlsx')
    return
  }

  await downloadXlsx(createQuestionsRows(), 'direct-questions-export.xlsx')
}
</script>
