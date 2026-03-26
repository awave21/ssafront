<template>
  <KnowledgeSheetShell
    :open="isOpen"
    title="Добавить справочник"
    :subtitle="sheetSubtitle"
    :show-back="showBackButton"
    :loading="isSubmitting"
    :submit-disabled="isSubmitDisabled"
    :submit-text="submitText"
    :size="step === 'columns' ? 'lg' : 'md'"
    @close="handleClose"
    @cancel="handleClose"
    @back="handleBack"
    @submit="handleNext"
  >
    <div class="p-6">
      <!-- Step 1: Template Selection -->
      <div v-if="step === 'template'" class="grid grid-cols-2 gap-3">
        <button
          v-for="tpl in visibleTemplates"
          :key="tpl.id"
          @click="selectTemplate(tpl.id)"
          class="flex flex-col items-start p-4 rounded-md border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/50 transition-all text-left group"
          :class="[
            selectedTemplate === tpl.id ? 'border-indigo-400 bg-indigo-50' : '',
            tpl.id === 'ai_generate' ? 'opacity-50 cursor-not-allowed' : ''
          ]"
          :disabled="tpl.id === 'ai_generate'"
        >
          <div class="w-10 h-10 rounded-lg flex items-center justify-center mb-3"
            :class="[
              selectedTemplate === tpl.id 
                ? 'bg-indigo-600 text-white' 
                : 'bg-slate-100 text-slate-500 group-hover:bg-indigo-100 group-hover:text-indigo-600'
            ]"
          >
            <component :is="tpl.icon" class="w-5 h-5" />
          </div>
          <span class="font-bold text-slate-900 text-sm">{{ tpl.label }}</span>
          <span class="text-xs text-slate-500 mt-1">{{ tpl.description }}</span>
          <span v-if="tpl.id === 'ai_generate'" class="text-[10px] text-slate-400 mt-1">Скоро</span>
        </button>
      </div>

      <!-- Step 2: Details Form -->
      <div v-else-if="step === 'details'" class="space-y-5">
        <div>
          <label class="text-sm font-medium text-slate-700">
            Название справочника <span class="text-red-500">*</span>
          </label>
          <input
            v-model.trim="form.name"
            type="text"
            required
            placeholder="Услуги клиники"
            class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
            @input="generateToolNameFromLabel"
          />
        </div>

        <div>
          <label class="text-sm font-medium text-slate-700">
            Имя функции для агента <span class="text-red-500">*</span>
          </label>
          <div class="relative mt-1.5">
            <input
              v-model.trim="form.tool_name"
              type="text"
              required
              placeholder="get_services"
              pattern="^[a-z][a-z0-9_]*$"
              class="w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 font-mono focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
              :class="{ 'border-red-300 bg-red-50': toolNameError }"
              :readonly="isToolNameReadonly"
              :disabled="isToolNameReadonly"
            />
          </div>
          <p v-if="toolNameError" class="mt-1 text-xs text-red-600">{{ toolNameError }}</p>
          <p v-else-if="isToolNameReadonly" class="mt-1 text-xs text-slate-500">
            Значение фиксируется шаблоном.
          </p>
          <p v-else class="mt-1 text-xs text-slate-500">
            Латиница, цифры и _ • Уникальное в рамках агента
          </p>
        </div>

        <div>
          <label class="text-sm font-medium text-slate-700">Описание для агента</label>
          <textarea
            v-model.trim="form.tool_description"
            rows="3"
            :placeholder="selectedTemplateData?.defaultDescription"
            class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none resize-none"
          ></textarea>
          <p class="mt-1 text-xs text-slate-500">
            Помогает агенту понять когда использовать этот справочник
          </p>
        </div>

        <div>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <label class="text-sm font-medium text-slate-700">Текст для системного промпта</label>
            <button
              type="button"
              class="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              @click="copyCreatePromptSnippet"
            >
              <ClipboardCopy class="w-3.5 h-3.5" />
              {{ createPromptSnippetCopied ? 'Скопировано' : 'Копировать' }}
            </button>
          </div>
          <textarea
            v-model.trim="form.prompt_usage_snippet"
            rows="2"
            class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none resize-none"
            :placeholder="createPromptSnippetPlaceholder"
          ></textarea>
        </div>

        <p v-if="submitError" class="text-sm text-red-600">{{ submitError }}</p>
      </div>

      <!-- Step 3: Custom Columns Editor -->
      <div v-else-if="step === 'columns'">
        <ColumnEditor
          v-model="customColumns"
          :max-columns="15"
          ref="columnEditorRef"
        />
      </div>
    </div>
  </KnowledgeSheetShell>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  HelpCircle,
  Tag,
  Package,
  Building2,
  Sparkles,
  List,
  ClipboardCopy
} from 'lucide-vue-next'
import ColumnEditor, { type ColumnDefinition } from './ColumnEditor.vue'
import { generateSlug } from '~/utils/translit'
import { validateToolName } from '~/utils/directory-helpers'
import KnowledgeSheetShell from './KnowledgeSheetShell.vue'

const props = defineProps<{
  isOpen: boolean
  existingToolNames?: string[]
  mode?: 'directory' | 'table'
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submit', data: {
    name: string
    tool_name?: string
    tool_description: string
    prompt_usage_snippet?: string
    template: string
    columns: ColumnDefinition[]
    create_tool?: boolean
  }): void
}>()

type TemplateColumn = {
  name: string
  label: string
  type: string
  required: boolean
  searchable?: boolean
}

type Template = {
  id: string
  label: string
  description: string
  icon: any
  columns: TemplateColumn[]
  defaultDescription: string
  promptUsageSnippet: string
}

const templates: Template[] = [
  {
    id: 'qa',
    label: 'Вопрос-ответ',
    description: 'Пары вопросов и ответов',
    icon: HelpCircle,
    columns: [
      { name: 'question', label: 'Вопрос', type: 'text', required: true, searchable: true },
      { name: 'answer', label: 'Ответ', type: 'text', required: true, searchable: false },
    ],
    defaultDescription:
      'Инструмент `get_question_answer`. Вызывай, когда нужен короткий точный ответ из базы FAQ (вопрос–ответ). Параметр `query` — формулировка вопроса пользователя или ключевые слова для поиска по справочнику.',
    promptUsageSnippet:
      'Вызывай get_question_answer, когда пользователю нужен короткий ответ из базы типовых вопросов и ответов (FAQ).'
  },
  {
    id: 'service_catalog',
    label: 'Каталог услуг',
    description: 'Название, описание, цена',
    icon: Tag,
    columns: [
      { name: 'name', label: 'Название', type: 'text', required: true, searchable: true },
      { name: 'description', label: 'Описание', type: 'text', required: false, searchable: true },
      { name: 'price', label: 'Цена', type: 'number', required: false, searchable: false },
    ],
    defaultDescription:
      'Инструмент `get_service_info`. Вызывай для вопросов об услугах: название, описание, стоимость. Параметр `query` — формулировка вопроса пользователя или ключевые слова для поиска по справочнику.',
    promptUsageSnippet:
      'Вызывай get_service_info, когда спрашивают об услугах: название, описание, стоимость или подбор услуги.'
  },
  {
    id: 'product_catalog',
    label: 'Каталог товаров',
    description: 'С ценами и характеристиками',
    icon: Package,
    columns: [
      { name: 'name', label: 'Название', type: 'text', required: true, searchable: true },
      { name: 'description', label: 'Описание', type: 'text', required: false, searchable: true },
      { name: 'price', label: 'Цена', type: 'number', required: false, searchable: false },
      { name: 'specs', label: 'Характеристики', type: 'text', required: false, searchable: true },
    ],
    defaultDescription:
      'Инструмент `get_product_info`. Вызывай для вопросов о товарах: название, характеристики, цена. Параметр `query` — формулировка вопроса пользователя или ключевые слова для поиска по справочнику.',
    promptUsageSnippet:
      'Вызывай get_product_info, когда спрашивают о товарах: название, характеристики, цена или наличие.'
  },
  {
    id: 'theme_catalog',
    label: 'Каталог тем',
    description: 'Тема, краткая информация',
    icon: Tag,
    columns: [
      { name: 'topic', label: 'Тема', type: 'text', required: true, searchable: true },
      { name: 'summary', label: 'Краткая информация', type: 'text', required: true, searchable: true },
      { name: 'link', label: 'Ссылка', type: 'text', required: false, searchable: false },
    ],
    defaultDescription:
      'Инструмент `get_topic_info`. Вызывай для вопросов по тематическому каталогу (тема, краткая информация, ссылки). Параметр `query` — формулировка вопроса пользователя или ключевые слова для поиска по справочнику.',
    promptUsageSnippet:
      'Вызывай get_topic_info, когда нужна информация по тематическому каталогу: тема, краткое содержание, ссылки.'
  },
  {
    id: 'company_info',
    label: 'О компании',
    description: 'Тема → информация',
    icon: Building2,
    columns: [
      { name: 'topic', label: 'Тема', type: 'text', required: true, searchable: true },
      { name: 'info', label: 'Информация', type: 'text', required: true, searchable: true },
    ],
    defaultDescription:
      'Инструмент `get_company_info`. Вызывай для вопросов о компании: контакты, адрес, доставка, правила, цены. Параметр `query` — формулировка вопроса пользователя или ключевые слова для поиска по справочнику.',
    promptUsageSnippet:
      'Вызывай get_company_info, когда спрашивают о клинике или компании: контакты, адрес, режим работы, доставка, правила.'
  },
  {
    id: 'medical_course_catalog',
    label: 'Каталог мед. курсов',
    description: 'Образовательные программы',
    icon: Package,
    columns: [
      { name: 'name', label: 'Название курса', type: 'text', required: true, searchable: true },
      { name: 'description', label: 'Описание', type: 'text', required: false, searchable: true },
      { name: 'price', label: 'Стоимость', type: 'number', required: false, searchable: false },
    ],
    defaultDescription:
      'Инструмент `get_medical_course_info`. Вызывай для вопросов о медицинских курсах: программа, длительность, стоимость. Параметр `query` — формулировка вопроса пользователя или ключевые слова для поиска по справочнику.',
    promptUsageSnippet:
      'Вызывай get_medical_course_info, когда спрашивают о медицинских курсах: программа, длительность, стоимость, запись.'
  },
  {
    id: 'custom',
    label: 'Произвольный',
    description: 'Задайте свои колонки',
    icon: List,
    columns: [],
    defaultDescription:
      'Укажи имя функции (поле выше) и когда её вызывать. Параметр `query` — формулировка вопроса пользователя или ключевые слова для поиска по справочнику.',
    promptUsageSnippet: ''
  },
  {
    id: 'clipboard_import',
    label: 'Вставить из буфера',
    description: 'Вставьте код справочника из буфера обмена',
    icon: List,
    columns: [],
    defaultDescription:
      'Инструмент `get_clipboard_import`. Вызывай для поиска по данным, импортированным из буфера обмена. Параметр `query` — формулировка вопроса пользователя или ключевые слова для поиска по справочнику.',
    promptUsageSnippet:
      'Вызывай get_clipboard_import, когда нужно найти данные из справочника, импортированного из буфера обмена или файла.'
  },
  {
    id: 'ai_generate',
    label: 'Создать с ИИ',
    description: 'Опишите — ИИ сгенерирует',
    icon: Sparkles,
    columns: [],
    defaultDescription: '',
    promptUsageSnippet: ''
  },
]

const fixedToolNameByTemplate: Record<string, string> = {
  qa: 'get_question_answer',
  service_catalog: 'get_service_info',
  product_catalog: 'get_product_info',
  company_info: 'get_company_info',
  theme_catalog: 'get_topic_info',
  medical_course_catalog: 'get_medical_course_info',
  clipboard_import: 'get_clipboard_import',
}

const qaColumns: ColumnDefinition[] = [
  { id: 'question', name: 'question', label: 'Вопрос', type: 'text', required: true, searchable: true },
  { id: 'answer', name: 'answer', label: 'Ответ', type: 'text', required: true, searchable: false },
]

const step = ref<'template' | 'details' | 'columns'>('template')
const selectedTemplate = ref<string | null>(null)
const isSubmitting = ref(false)
const submitError = ref('')
const toolNameError = ref('')

const form = ref({
  name: '',
  tool_name: '',
  tool_description: '',
  prompt_usage_snippet: ''
})

const customColumns = ref<ColumnDefinition[]>([
  { id: '1', name: '', label: '', type: 'text', required: true, searchable: true }
])

const columnEditorRef = ref<InstanceType<typeof ColumnEditor> | null>(null)

const selectedTemplateData = computed(() => {
  return templates.find(t => t.id === selectedTemplate.value)
})

const customPromptUsageLine = (fn: string) =>
  `Вызывай ${fn}, когда нужна информация из этого справочника.`

/** Подсказка в пустом поле и запасной текст для «Копировать» / отправки формы. */
const createPromptSnippetPlaceholder = computed(() => {
  if (selectedTemplate.value === 'custom') {
    const fn = form.value.tool_name?.trim()
    return fn ? customPromptUsageLine(fn) : ''
  }
  return selectedTemplateData.value?.promptUsageSnippet || ''
})

const createPromptSnippetCopied = ref(false)
let createPromptSnippetCopiedTimer: ReturnType<typeof setTimeout> | null = null

const copyCreatePromptSnippet = async () => {
  const text =
    form.value.prompt_usage_snippet.trim() || createPromptSnippetPlaceholder.value
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    if (createPromptSnippetCopiedTimer) clearTimeout(createPromptSnippetCopiedTimer)
    createPromptSnippetCopied.value = true
    createPromptSnippetCopiedTimer = setTimeout(() => {
      createPromptSnippetCopied.value = false
      createPromptSnippetCopiedTimer = null
    }, 2000)
  } catch {
    submitError.value = 'Не удалось скопировать в буфер обмена'
  }
}

const currentMode = computed(() => props.mode ?? 'directory')

const visibleTemplates = computed(() => {
  if (currentMode.value === 'directory') return templates.filter((template) => template.id !== 'custom')
  return []
})

const isToolNameReadonly = computed(() => {
  if (!selectedTemplate.value) return false
  return selectedTemplate.value in fixedToolNameByTemplate
})

const showTemplateStep = computed(() => currentMode.value === 'directory')

const sheetSubtitle = computed(() => {
  if (step.value === 'template') return 'Выберите тип справочника'
  if (step.value === 'details') return selectedTemplateData.value?.label || 'Создание'
  return form.value.name
})

const showBackButton = computed(() => step.value !== 'template' && showTemplateStep.value)

const isSubmitDisabled = computed(() => {
  if (step.value === 'template') return !selectedTemplate.value
  if (step.value === 'details') return !isDetailsValid.value
  return !isColumnsValid.value
})

const submitText = computed(() => {
  if (step.value === 'columns') return 'Создать'
  const needsColumnsStep =
    selectedTemplate.value === 'custom' || selectedTemplate.value === 'clipboard_import'
  if (step.value === 'details' && !needsColumnsStep) return 'Создать'
  return 'Далее'
})

const isDetailsValid = computed(() => {
  return form.value.name.trim() && 
         form.value.tool_name.trim() && 
         /^[a-z][a-z0-9_]*$/.test(form.value.tool_name) &&
         !toolNameError.value
})

const isColumnsValid = computed(() => {
  if (customColumns.value.length === 0) return false
  return customColumns.value.every(col => 
    col.name && 
    col.label && 
    /^[a-z][a-z0-9_]*$/.test(col.name)
  )
})

const selectTemplate = (id: string) => {
  if (id === 'ai_generate') return
  selectedTemplate.value = id
  const tpl = templates.find((template) => template.id === id)
  if (tpl) {
    form.value.name = tpl.label
    form.value.tool_description = tpl.defaultDescription
  }
  if (id in fixedToolNameByTemplate) {
    form.value.tool_name = fixedToolNameByTemplate[id]
    checkToolName()
  } else {
    generateToolNameFromLabel()
  }
  if (id === 'custom') {
    const fn = form.value.tool_name?.trim()
    form.value.prompt_usage_snippet = fn ? customPromptUsageLine(fn) : ''
  } else if (tpl) {
    form.value.prompt_usage_snippet = tpl.promptUsageSnippet
  }
}

const goToDetails = () => {
  if (!selectedTemplate.value) return
  step.value = 'details'
}

const handleBack = () => {
  if (step.value === 'columns') {
    step.value = 'details'
    return
  }
  if (step.value === 'details' && showTemplateStep.value) step.value = 'template'
}

const handleNext = () => {
  if (step.value === 'template') goToDetails()
  else if (step.value === 'details') handleDetailsNext()
  else if (step.value === 'columns') handleSubmit()
}

const generateToolNameFromLabel = () => {
  if (isToolNameReadonly.value) return
  form.value.tool_name = generateSlug(form.value.name, 'get_')
  checkToolName()
}

const checkToolName = () => {
  toolNameError.value = validateToolName(
    form.value.tool_name,
    props.existingToolNames || []
  )
}

const handleDetailsNext = () => {
  if (!isDetailsValid.value) return

  if (
    selectedTemplate.value === 'custom' ||
    selectedTemplate.value === 'clipboard_import'
  ) {
    step.value = 'columns'
  } else {
    handleSubmit()
  }
}

const resetForm = () => {
  if (currentMode.value === 'table') {
    step.value = 'details'
    selectedTemplate.value = 'custom'
  } else {
    step.value = 'template'
    selectedTemplate.value = null
  }
  form.value = { name: '', tool_name: '', tool_description: '', prompt_usage_snippet: '' }
  customColumns.value = [{ id: '1', name: '', label: '', type: 'text', required: true, searchable: true }]
  submitError.value = ''
  toolNameError.value = ''
  isSubmitting.value = false
}

const handleClose = () => {
  resetForm()
  emit('close')
}

const handleSubmit = () => {
  if (!selectedTemplate.value) return
  
  submitError.value = ''
  isSubmitting.value = true
  
  let columns: ColumnDefinition[]
  const tpl = selectedTemplate.value
  if (tpl === 'qa') {
    columns = qaColumns
  } else if (tpl === 'custom' || tpl === 'clipboard_import') {
    if (!isColumnsValid.value) {
      submitError.value = 'Заполните все колонки корректно'
      isSubmitting.value = false
      return
    }
    columns = customColumns.value.map(({ id, ...rest }) => rest) as ColumnDefinition[]
  } else {
    columns = (selectedTemplateData.value?.columns || []).map(col => ({
      ...col,
      searchable: col.searchable ?? false
    })) as ColumnDefinition[]
  }
  
  emit('submit', {
    name: form.value.name,
    tool_name: form.value.tool_name || undefined,
    tool_description: form.value.tool_description.trim(),
    prompt_usage_snippet:
      form.value.prompt_usage_snippet.trim() ||
      createPromptSnippetPlaceholder.value.trim(),
    template: selectedTemplate.value,
    columns,
    create_tool: currentMode.value === 'directory'
  })
}

watch(() => props.isOpen, (open) => {
  if (open) {
    resetForm()
  }
})

watch(() => form.value.tool_name, () => {
  if (!isToolNameReadonly.value) checkToolName()
  if (selectedTemplate.value === 'custom') {
    const fn = form.value.tool_name?.trim()
    form.value.prompt_usage_snippet = fn ? customPromptUsageLine(fn) : ''
  }
})

defineExpose({
  setSubmitting: (value: boolean) => { isSubmitting.value = value },
  setError: (error: string) => { submitError.value = error },
  close: handleClose
})
</script>
