<template>
  <KnowledgeSheetShell
    :open="isOpen"
    title="Добавить справочник"
    :subtitle="step === 'template' ? 'Выберите тип справочника' : (step === 'details' ? selectedTemplateData?.label : form.name)"
    :show-back="step !== 'template'"
    :loading="isSubmitting"
    :submit-disabled="step === 'template' ? !selectedTemplate : (step === 'details' ? !isDetailsValid : !isColumnsValid)"
    :submit-text="step === 'columns' || (step === 'details' && selectedTemplate !== 'custom') ? 'Создать' : 'Далее'"
    :size="step === 'columns' ? 'lg' : 'md'"
    @close="handleClose"
    @back="handleBack"
    @submit="handleNext"
  >
    <div class="p-6">
      <!-- Step 1: Template Selection -->
      <div v-if="step === 'template'" class="grid grid-cols-2 gap-3">
        <button
          v-for="tpl in templates"
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
            />
          </div>
          <p v-if="toolNameError" class="mt-1 text-xs text-red-600">{{ toolNameError }}</p>
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

        <!-- Preview columns for template-based -->
        <div v-if="selectedTemplate !== 'custom'" class="bg-slate-50 rounded-md p-4 border border-slate-100">
          <p class="text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Колонки справочника</p>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="col in selectedTemplateData?.columns"
              :key="col.name"
              class="px-3 py-1 bg-white border border-slate-200 rounded-lg text-xs text-slate-600"
            >
              {{ col.label }}
              <span class="text-slate-400 ml-1">({{ col.type }})</span>
              <span v-if="col.required" class="text-red-400">*</span>
            </span>
          </div>
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
  List
} from 'lucide-vue-next'
import ColumnEditor, { type ColumnDefinition } from './ColumnEditor.vue'
import { generateSlug } from '~/utils/translit'
import { validateToolName } from '~/utils/directory-helpers'
import KnowledgeSheetShell from './KnowledgeSheetShell.vue'

const props = defineProps<{
  isOpen: boolean
  existingToolNames?: string[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submit', data: {
    name: string
    tool_name: string
    tool_description: string
    template: string
    columns: ColumnDefinition[]
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
    defaultDescription: 'Найти ответ на часто задаваемый вопрос'
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
    defaultDescription: 'Найти услугу по названию или описанию'
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
    defaultDescription: 'Найти товар по названию, описанию или характеристикам'
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
    defaultDescription: 'Получить информацию о компании по теме'
  },
  {
    id: 'custom',
    label: 'Произвольный',
    description: 'Задайте свои колонки',
    icon: List,
    columns: [],
    defaultDescription: 'Поиск по справочнику'
  },
  {
    id: 'ai_generate',
    label: 'Создать с ИИ',
    description: 'Опишите — ИИ сгенерирует',
    icon: Sparkles,
    columns: [],
    defaultDescription: ''
  },
]

const step = ref<'template' | 'details' | 'columns'>('template')
const selectedTemplate = ref<string | null>(null)
const isSubmitting = ref(false)
const submitError = ref('')
const toolNameError = ref('')

const form = ref({
  name: '',
  tool_name: '',
  tool_description: ''
})

const customColumns = ref<ColumnDefinition[]>([
  { id: '1', name: '', label: '', type: 'text', required: true, searchable: true }
])

const columnEditorRef = ref<InstanceType<typeof ColumnEditor> | null>(null)

const selectedTemplateData = computed(() => {
  return templates.find(t => t.id === selectedTemplate.value)
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
}

const goToDetails = () => {
  if (!selectedTemplate.value) return
  step.value = 'details'
}

const handleBack = () => {
  if (step.value === 'columns') step.value = 'details'
  else if (step.value === 'details') step.value = 'template'
}

const handleNext = () => {
  if (step.value === 'template') goToDetails()
  else if (step.value === 'details') handleDetailsNext()
  else if (step.value === 'columns') handleSubmit()
}

const generateToolNameFromLabel = () => {
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
  
  if (selectedTemplate.value === 'custom') {
    step.value = 'columns'
  } else {
    handleSubmit()
  }
}

const resetForm = () => {
  step.value = 'template'
  selectedTemplate.value = null
  form.value = { name: '', tool_name: '', tool_description: '' }
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
  if (selectedTemplate.value === 'custom') {
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
    tool_name: form.value.tool_name,
    tool_description: form.value.tool_description || selectedTemplateData.value?.defaultDescription || '',
    template: selectedTemplate.value,
    columns
  })
}

watch(() => props.isOpen, (open) => {
  if (open) {
    resetForm()
  }
})

watch(() => form.value.tool_name, () => {
  checkToolName()
})

defineExpose({
  setSubmitting: (value: boolean) => { isSubmitting.value = value },
  setError: (error: string) => { submitError.value = error },
  close: handleClose
})
</script>
