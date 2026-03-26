<template>
  <KnowledgeSheetShell
    :open="open"
    :title="file ? 'Редактирование файла' : 'Добавление файла'"
    :tabs="editorTabs"
    v-model:active-tab="activeTab"
    size="lg"
    @close="$emit('close')"
    @cancel="$emit('close')"
  >
    <template #header-actions>
      <div class="flex items-center gap-2">
        <span class="text-xs text-slate-500">Использовать</span>
        <Switch v-model="form.is_enabled" />
      </div>
    </template>

    <div class="p-6">
      <div v-if="activeTab === 'content'" class="space-y-5">
        <div class="rounded-xl bg-white p-4">
          <div>
            <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Название</label>
            <input
              v-model="form.title"
              type="text"
              placeholder="Например: Уход после процедуры"
              class="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none transition-all duration-300 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
            />
          </div>
        </div>

        <div class="rounded-xl bg-white p-4">
          <div>
            <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Мета-теги</label>
            <input
              v-model="tagInput"
              type="text"
              placeholder="Добавить тег..."
              class="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none transition-all duration-300 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
              @blur="commitTagInput"
              @keydown="handleTagInputKeydown"
            />
            <p class="mt-1 text-[11px] text-slate-500">Добавление: Enter, пробел, запятая или ;</p>
            <div v-if="form.meta_tags.length" class="mt-2 flex flex-wrap gap-2">
              <span
                v-for="tag in form.meta_tags"
                :key="tag"
                class="inline-flex items-center gap-1 rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700"
              >
                #{{ tag }}
                <button
                  type="button"
                  class="rounded-full p-0.5 text-indigo-500 transition-colors hover:bg-indigo-100 hover:text-indigo-700"
                  @click="removeTag(tag)"
                >
                  <X class="h-3 w-3" />
                </button>
              </span>
            </div>
          </div>
        </div>

        <div class="rounded-xl bg-white p-4">
          <div>
            <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Простой текст</label>
            <textarea
              v-model="form.content"
              rows="12"
              placeholder="Введите большой текст для векторизации..."
              class="mt-2 w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-sans outline-none transition-all duration-300 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
            ></textarea>
          </div>
        </div>

        <div v-if="file" class="rounded-xl bg-white p-4">
          <div>
            <p class="text-[10px] font-black uppercase tracking-widest text-slate-400">Статус индексации</p>
            <div class="mt-3 flex items-center justify-between gap-3">
              <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold" :class="vectorBadgeClass(form.vector_status)">
                {{ vectorStatusLabel(form.vector_status) }}
              </span>
              <button
                type="button"
                class="inline-flex h-9 items-center rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50"
                @click="requestReindex"
              >
                Переиндексация
              </button>
            </div>
            <p
              v-if="file && form.vector_status === knowledgeVectorStatus.indexed && indexedAtLabel"
              class="mt-2 text-[11px] text-slate-500"
            >
              Дата индексации: {{ indexedAtLabel }}
            </p>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'documents'" class="space-y-4">
        <p v-if="!documentUploadEnabled" class="rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-xs text-amber-900">
          Чтобы загрузить CSV, PDF, DOCX или TXT, сначала откройте папку в дереве базы знаний — настройки чанкинга действуют на файлы внутри папки.
        </p>
        <template v-else>
          <input
            ref="docInputRef"
            type="file"
            multiple
            accept=".csv,.pdf,.docx,.txt"
            class="hidden"
            @change="onDocInputChange"
          />
          <div
            role="button"
            tabindex="0"
            class="rounded-3xl border-2 border-dashed p-10 text-center transition-colors outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            :class="
              isDocDragOver
                ? 'border-indigo-400 bg-indigo-50/60'
                : 'border-slate-200 bg-slate-50/40 hover:border-slate-300 hover:bg-slate-50'
            "
            @click="triggerDocPicker"
            @keydown.enter.prevent="triggerDocPicker"
            @keydown.space.prevent="triggerDocPicker"
            @dragover.prevent="isDocDragOver = true"
            @dragleave.prevent="isDocDragOver = false"
            @drop.prevent="onDocDrop"
          >
            <Upload class="mx-auto mb-3 h-10 w-10 text-indigo-400" />
            <p class="text-sm font-semibold text-slate-800">Перетащите файлы сюда</p>
            <p class="mt-1 text-xs text-slate-500">
              CSV, PDF, DOCX или TXT — можно несколько штук; появятся в текущей папке и уйдут в индексацию
            </p>
            <button
              type="button"
              class="mt-5 inline-flex h-9 items-center rounded-xl bg-indigo-600 px-4 text-xs font-semibold text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="saving"
              @click.stop="triggerDocPicker"
            >
              {{ saving ? 'Загрузка…' : 'Выбрать файлы' }}
            </button>
          </div>
        </template>
      </div>
    </div>

    <template #footer>
      <div class="flex w-full items-center justify-between gap-3">
        <button
          type="button"
          class="rounded-md border border-slate-200 bg-white px-6 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100"
          @click="emit('close')"
        >
          Отменить
        </button>
        <button
          v-if="activeTab === 'content'"
          type="button"
          :disabled="!isValid || saving"
          class="flex items-center gap-2 rounded-md bg-indigo-600 px-8 py-2.5 text-sm font-bold text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          @click="handleSave"
        >
          <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
          <span>Сохранить</span>
        </button>
        <p v-else class="max-w-sm text-right text-xs text-slate-500">
          <template v-if="documentUploadEnabled">
            Сохранение не требуется — загрузка сразу создаёт файлы в папке.
          </template>
          <template v-else> Откройте папку в дереве слева — тогда здесь появится область загрузки. </template>
        </p>
      </div>
    </template>
  </KnowledgeSheetShell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { formatKnowledgeIndexedAt } from '~/utils/formatKnowledgeIndexedAt'
import { Loader2, Upload, X } from 'lucide-vue-next'
import { Switch } from '~/components/ui/switch'
import KnowledgeSheetShell from './KnowledgeSheetShell.vue'
import {
  knowledgeVectorStatus,
  type CreateKnowledgeTextPayload,
  type KnowledgeFileItem,
  type KnowledgeVectorStatus
} from '~/types/knowledge'

type FormState = {
  title: string
  meta_tags: string[]
  content: string
  is_enabled: boolean
  vector_status: KnowledgeVectorStatus
}

const DOC_EXTENSIONS = ['.csv', '.pdf', '.docx', '.txt'] as const

const props = withDefaults(
  defineProps<{
    open: boolean
    file: KnowledgeFileItem | null
    saving?: boolean
    /** Разрешить вкладку «Документы» (нужна открытая папка в дереве). */
    documentUploadEnabled?: boolean
  }>(),
  { saving: false, documentUploadEnabled: false }
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', value: CreateKnowledgeTextPayload): void
  (e: 'reindex'): void
  (e: 'upload-documents', files: File[]): void
}>()

const editorTabs = [
  { id: 'content', label: 'Простой текст' },
  { id: 'documents', label: 'Документы' }
]

const activeTab = ref('content')

const docInputRef = ref<HTMLInputElement | null>(null)
const isDocDragOver = ref(false)

const isAllowedDocument = (file: File) => {
  const name = file.name.toLowerCase()
  return DOC_EXTENSIONS.some((ext) => name.endsWith(ext))
}

const triggerDocPicker = () => {
  if (props.saving || !props.documentUploadEnabled) return
  docInputRef.value?.click()
}

const collectAllowedFiles = (list: FileList | File[] | null | undefined): File[] => {
  const arr = Array.from(list ?? [])
  return arr.filter((f) => isAllowedDocument(f))
}

const forwardDocumentFiles = (files: File[]) => {
  if (!files.length) return
  emit('upload-documents', files)
}

const onDocInputChange = (e: Event) => {
  const input = e.target as HTMLInputElement
  const picked = collectAllowedFiles(input.files)
  forwardDocumentFiles(picked)
  input.value = ''
}

const onDocDrop = (e: DragEvent) => {
  isDocDragOver.value = false
  if (props.saving || !props.documentUploadEnabled) return
  const dropped = collectAllowedFiles(e.dataTransfer?.files ?? null)
  forwardDocumentFiles(dropped)
}

const form = ref<FormState>({
  title: '',
  meta_tags: [],
  content: '',
  is_enabled: true,
  vector_status: knowledgeVectorStatus.notIndexed
})
const tagInput = ref('')

const isValid = computed(() => form.value.title.trim() && form.value.content.trim())

const indexedAtLabel = computed(() =>
  formatKnowledgeIndexedAt(props.file?.indexed_at)
)

watch(
  [() => props.open, () => props.file?.id ?? ''],
  () => {
    if (!props.open) return
    isDocDragOver.value = false
    tagInput.value = ''
    if (props.file) {
      activeTab.value = 'content'
      form.value = {
        title: props.file.title,
        meta_tags: [...props.file.meta_tags],
        content: props.file.content,
        is_enabled: props.file.is_enabled,
        vector_status: props.file.vector_status
      }
      return
    }
    activeTab.value = 'content'
    form.value = {
      title: '',
      meta_tags: [],
      content: '',
      is_enabled: true,
      vector_status: knowledgeVectorStatus.notIndexed
    }
  }
)

const normalizeTags = (raw: string): string[] => raw
  .split(/[\s,;]+/)
  .map((tag) => tag.replace(/^#+/, '').trim())
  .filter(Boolean)

const commitTagInput = () => {
  if (!tagInput.value.trim()) return
  const parsed = normalizeTags(tagInput.value)
  const unique = new Set(form.value.meta_tags)
  parsed.forEach((tag) => unique.add(tag))
  form.value.meta_tags = Array.from(unique)
  tagInput.value = ''
}

const handleTagInputKeydown = (event: KeyboardEvent) => {
  if (['Enter', ',', ';', ' '].includes(event.key)) {
    event.preventDefault()
    commitTagInput()
    return
  }
  if (event.key === 'Backspace' && !tagInput.value && form.value.meta_tags.length > 0) {
    form.value.meta_tags = form.value.meta_tags.slice(0, -1)
  }
}

const removeTag = (tagToRemove: string) => {
  form.value.meta_tags = form.value.meta_tags.filter((tag) => tag !== tagToRemove)
}

const requestReindex = () => {
  form.value.vector_status = knowledgeVectorStatus.indexing
  emit('reindex')
}

const vectorStatusLabel = (status: KnowledgeVectorStatus) => {
  if (status === knowledgeVectorStatus.indexed) return 'Индексировано'
  if (status === knowledgeVectorStatus.indexing) return 'Индексация'
  if (status === knowledgeVectorStatus.failed) return 'Ошибка'
  return 'Не индексировано'
}

const vectorBadgeClass = (status: KnowledgeVectorStatus) => {
  if (status === knowledgeVectorStatus.indexed) return 'bg-emerald-50 text-emerald-700 border border-emerald-200'
  if (status === knowledgeVectorStatus.indexing) return 'bg-amber-50 text-amber-700 border border-amber-200'
  if (status === knowledgeVectorStatus.failed) return 'bg-rose-50 text-rose-700 border border-rose-200'
  return 'bg-slate-100 text-slate-600 border border-slate-200'
}

const handleSave = () => {
  if (!isValid.value) return
  emit('save', {
    title: form.value.title.trim(),
    meta_tags: form.value.meta_tags,
    content: form.value.content.trim(),
    is_enabled: form.value.is_enabled,
    vector_status: form.value.vector_status
  })
}
</script>
