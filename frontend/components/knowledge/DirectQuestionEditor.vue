<template>
  <KnowledgeSheetShell
    :open="open"
    :dismiss-emits-close="false"
    :title="question ? 'Редактирование прямого вопроса' : 'Добавление прямого вопроса'"
    :tabs="tabs"
    v-model:active-tab="activeTab"
    :loading="saving"
    :submit-disabled="!isValid"
    size="lg"
    @update:open="onSheetOpenChange"
    @cancel="emit('close')"
    @submit="handleSave"
  >
    <template #header-actions>
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <span class="text-xs text-slate-500">Уведомления в Telegram</span>
          <Switch v-model="form.notify_telegram" />
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-slate-500">Использовать</span>
          <Switch v-model="form.is_enabled" />
        </div>
      </div>
    </template>

    <div class="p-6">
      <!-- Tab: Content -->
      <div v-if="activeTab === 'content'" class="space-y-6">
        <div>
          <label class="text-sm font-medium text-slate-700 flex items-center gap-1">
            Название
            <TooltipProvider :delay-duration="300">
              <Tooltip>
                <TooltipTrigger as-child>
                  <HelpCircle class="w-3.5 h-3.5 text-slate-400 cursor-help" />
                </TooltipTrigger>
                <TooltipContent side="right">
                  <p class="text-xs">Внутреннее название для списка</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </label>
          <input
            v-model="form.title"
            type="text"
            placeholder="Позвать менеджера"
            class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
          />
        </div>

        <div>
          <label class="text-sm font-medium text-slate-700 flex items-center gap-1">
            Содержание файла
            <TooltipProvider :delay-duration="300">
              <Tooltip>
                <TooltipTrigger as-child>
                  <HelpCircle class="w-3.5 h-3.5 text-slate-400 cursor-help" />
                </TooltipTrigger>
                <TooltipContent side="right">
                  <p class="text-xs">Инструкция или ответ. Используйте &lt;system&gt; для системных команд.</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </label>
          <div class="mt-1.5 flex items-center justify-between gap-3">
            <button
              type="button"
              @click="insertSystemTag"
              class="inline-flex items-center rounded-md border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition-colors"
            >
              Вставить &lt;system&gt;...&lt;/system&gt;
            </button>
            <p class="text-[11px] text-slate-500">
              Инструкция внутри тега <code>&lt;system&gt;</code> будет выполнена как системная.
            </p>
          </div>
          <textarea
            ref="contentTextareaRef"
            v-model="form.content"
            rows="12"
            placeholder="Введите текст ответа или инструкцию..."
            class="mt-2 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 resize-none font-sans outline-none"
          ></textarea>
        </div>

        <div>
          <label class="text-sm font-medium text-slate-700">#Теги</label>
          <input
            v-model="tagInput"
            @keydown="handleTagInputKeydown"
            @blur="commitTagInput"
            type="text"
            placeholder="Добавить тег..."
            class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
          />
          <p class="mt-1 text-[11px] text-slate-500">
            Добавление: Enter, пробел, запятая или ;
          </p>
          <div v-if="form.tags.length" class="mt-2 flex flex-wrap gap-2">
            <span
              v-for="tag in form.tags"
              :key="tag"
              class="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 border border-indigo-100"
            >
              #{{ tag }}
              <button
                type="button"
                @click="removeTag(tag)"
                class="rounded-full p-0.5 text-indigo-500 hover:bg-indigo-100 hover:text-indigo-700 transition-colors"
                aria-label="Удалить тег"
              >
                <X class="h-3 w-3" />
              </button>
            </span>
          </div>
        </div>

        <div class="flex items-center gap-3 pt-4 border-t border-slate-100">
          <Switch v-model="form.interrupt_dialog" />
          <span class="text-sm text-slate-700">Прерывать диалог</span>
        </div>
      </div>

      <!-- Tab: Files -->
      <div v-if="activeTab === 'files'" class="space-y-6">
        <div class="border-2 border-dashed border-slate-200 rounded-xl p-12 text-center">
          <Upload class="w-10 h-10 text-slate-300 mx-auto mb-4" />
          <p class="text-sm font-medium text-slate-900">Перетащите файлы сюда</p>
          <p class="text-xs text-slate-500 mt-1 mb-4">Или выберите на компьютере</p>
          <button class="px-4 py-2 bg-white border border-slate-200 rounded-md text-sm font-medium hover:bg-slate-50 transition-colors">
            Выбрать файлы
          </button>
        </div>
        
        <div v-if="form.files.length > 0" class="grid gap-2">
          <div v-for="file in form.files" :key="file.id" class="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
            <div class="flex items-center gap-3">
              <FileText class="w-5 h-5 text-indigo-500" />
              <div>
                <p class="text-sm font-medium text-slate-900">{{ file.name }}</p>
                <p class="text-[10px] text-slate-500 uppercase">{{ file.type || 'FILE' }}</p>
              </div>
            </div>
            <button @click="removeFile(file.id)" class="p-1.5 text-slate-400 hover:text-red-600 transition-colors">
              <X class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <!-- Tab: Follow-up -->
      <div v-if="activeTab === 'followup'" class="space-y-6">
        <div class="flex items-center justify-between p-4 bg-indigo-50 rounded-lg border border-indigo-100">
          <div class="flex items-center gap-3">
            <Clock class="w-5 h-5 text-indigo-600" />
            <div>
              <p class="text-sm font-bold text-indigo-900">Отложенное сообщение</p>
              <p class="text-xs text-indigo-700">Будет отправлено через заданное время после срабатывания вопроса</p>
            </div>
          </div>
          <Switch v-model="followupEnabled" />
        </div>

        <div v-if="followupEnabled" class="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div>
            <label class="text-sm font-medium text-slate-700">Текст сообщения</label>
            <textarea
              v-model="followupContent"
              rows="4"
              placeholder="Например: Удалось ли вам связаться с менеджером?"
              class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 resize-none outline-none"
            ></textarea>
          </div>
          <div>
            <label class="text-sm font-medium text-slate-700">Задержка (в минутах)</label>
            <input
              v-model.number="followupDelay"
              type="number"
              min="1"
              class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
            />
          </div>
        </div>
      </div>
    </div>
  </KnowledgeSheetShell>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { 
  HelpCircle, 
  Upload, 
  FileText, 
  X, 
  Clock,
} from 'lucide-vue-next'
import { Switch } from '~/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '~/components/ui/tooltip'
import type { DirectQuestion, CreateDirectQuestionPayload } from '~/types/knowledge'
import { useToast } from '~/composables/useToast'
import KnowledgeSheetShell from './KnowledgeSheetShell.vue'

const props = defineProps<{
  open: boolean
  question: DirectQuestion | null
  saving?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: CreateDirectQuestionPayload): void
}>()

const baselinePayloadJson = ref('')

const buildPayload = (): CreateDirectQuestionPayload => ({
  ...form.value,
  followup: {
    enabled: followupEnabled.value,
    content: followupContent.value,
    delay_minutes: followupDelay.value
  }
})

const isDirty = computed(() => {
  if (!props.open || baselinePayloadJson.value === '') return false
  try {
    return JSON.stringify(buildPayload()) !== baselinePayloadJson.value
  } catch {
    return true
  }
})

const onSheetOpenChange = (nextOpen: boolean) => {
  if (nextOpen || !props.open) return
  if (props.saving) return

  if (isDirty.value && isValid.value) {
    handleSave()
    return
  }
  if (isDirty.value && !isValid.value) {
    toastInfo(
      'Нельзя сохранить',
      'Заполните название и содержание — или нажмите «Отменить», чтобы закрыть без сохранения.'
    )
    return
  }
  emit('close')
}

const { info: toastInfo } = useToast()

const activeTab = ref('content')
const tabs = [
  { id: 'content', label: 'Содержание вопроса' },
  { id: 'followup', label: 'Отправить фоллоу-ап' },
  { id: 'files', label: 'Отправка файлов', disabled: true }
]

const form = ref<CreateDirectQuestionPayload>({
  title: '',
  content: '',
  tags: [],
  is_enabled: true,
  interrupt_dialog: false,
  notify_telegram: false,
  files: []
})

const followupEnabled = ref(false)
const followupContent = ref('')
const followupDelay = ref(60)
const contentTextareaRef = ref<HTMLTextAreaElement | null>(null)
const isSyncingForm = ref(false)
const tagInput = ref('')

const isValid = computed(() => {
  return form.value.title.trim() && form.value.content.trim()
})

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      isSyncingForm.value = true
      baselinePayloadJson.value = ''
      if (props.question) {
        form.value = {
          title: props.question.title,
          content: props.question.content,
          tags: [...props.question.tags],
          is_enabled: props.question.is_enabled,
          interrupt_dialog: props.question.interrupt_dialog,
          notify_telegram: props.question.notify_telegram,
          files: [...props.question.files]
        }
        followupEnabled.value = props.question.followup?.enabled ?? false
        followupContent.value = props.question.followup?.content ?? ''
        followupDelay.value = props.question.followup?.delay_minutes ?? 60
      } else {
        form.value = {
          title: '',
          content: '',
          tags: [],
          is_enabled: true,
          interrupt_dialog: false,
          notify_telegram: false,
          files: []
        }
        followupEnabled.value = false
        followupContent.value = ''
        followupDelay.value = 60
      }
      tagInput.value = ''
      isSyncingForm.value = false
      activeTab.value = 'content'
      await nextTick()
      baselinePayloadJson.value = JSON.stringify(buildPayload())
    } else {
      baselinePayloadJson.value = ''
    }
  }
)

const normalizeTags = (raw: string): string[] => raw
  .split(/[\s,;]+/)
  .map(tag => tag.replace(/^#+/, '').trim())
  .filter(Boolean)

const appendTagsFromText = (raw: string) => {
  const parsedTags = normalizeTags(raw)
  if (!parsedTags.length) return
  const uniqueTags = new Set(form.value.tags)
  parsedTags.forEach(tag => uniqueTags.add(tag))
  form.value.tags = Array.from(uniqueTags)
}

const commitTagInput = () => {
  if (!tagInput.value.trim()) return
  appendTagsFromText(tagInput.value)
  tagInput.value = ''
}

const handleTagInputKeydown = (event: KeyboardEvent) => {
  if (['Enter', ',', ';', ' '].includes(event.key)) {
    event.preventDefault()
    commitTagInput()
    return
  }

  if (event.key === 'Backspace' && !tagInput.value && form.value.tags.length > 0) {
    form.value.tags = form.value.tags.slice(0, -1)
  }
}

const removeTag = (tagToRemove: string) => {
  form.value.tags = form.value.tags.filter(tag => tag !== tagToRemove)
}

const removeFile = (id: string) => {
  form.value.files = form.value.files.filter(f => f.id !== id)
}

const insertSystemTag = async () => {
  const snippet = '<system>\n\n</system>'
  const textarea = contentTextareaRef.value

  if (!textarea) {
    form.value.content = form.value.content ? `${form.value.content}\n${snippet}` : snippet
    return
  }

  const start = textarea.selectionStart ?? 0
  const end = textarea.selectionEnd ?? start
  const before = form.value.content.slice(0, start)
  const after = form.value.content.slice(end)
  form.value.content = `${before}${snippet}${after}`

  await nextTick()
  const cursorPos = start + '<system>\n'.length
  textarea.focus()
  textarea.setSelectionRange(cursorPos, cursorPos)
}

const handleSave = () => {
  if (!isValid.value) return
  emit('save', buildPayload())
}
</script>
