<template>
  <KnowledgeSheetShell
    :open="open"
    :title="entry ? 'Редактирование записи' : 'Добавление записи'"
    :tabs="tabs"
    v-model:active-tab="activeTab"
    :loading="saving"
    :submit-disabled="!isValid"
    size="lg"
    @close="$emit('close')"
    @cancel="$emit('close')"
    @submit="handleSave"
  >
    <template #header-actions>
      <div class="flex items-center gap-2">
        <span class="text-xs text-slate-500">Использовать</span>
        <Switch v-model="form.is_enabled" />
      </div>
    </template>

    <div class="p-6">
      <div v-if="activeTab === 'content'" class="space-y-6">
        <div>
          <label class="text-sm font-medium text-slate-700">Название (для админа)</label>
          <input
            v-model="form.admin_title"
            type="text"
            placeholder="Например: Уход после процедуры"
            class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none transition-all duration-300 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
          />
        </div>

        <div>
          <label class="text-sm font-medium text-slate-700">Мета-теги</label>
          <input
            v-model="tagInput"
            type="text"
            placeholder="Добавить тег..."
            class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none transition-all duration-300 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
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

        <div>
          <label class="text-sm font-medium text-slate-700">Content</label>
          <textarea
            v-model="form.content"
            rows="12"
            placeholder="Введите большой текст для векторизации..."
            class="mt-1.5 w-full resize-none rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-sans outline-none transition-all duration-300 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
          ></textarea>
        </div>

        <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <p class="text-xs font-semibold text-slate-600">Статус индексации</p>
          <div class="mt-2 flex items-center justify-between gap-3">
            <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold" :class="vectorBadgeClass(form.vector_status)">
              {{ vectorStatusLabel(form.vector_status) }}
            </span>
            <button
              type="button"
              class="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
              @click="requestReindex"
            >
              Переиндексация
            </button>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'documents'" class="space-y-4">
        <div class="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-10 text-center">
          <Upload class="mx-auto mb-3 h-10 w-10 text-slate-300" />
          <p class="text-sm font-semibold text-slate-700">Загрузка документов скоро</p>
          <p class="mt-1 text-xs text-slate-500">Поддержка txt/doc/pdf появится в следующем обновлении.</p>
          <div class="mt-4 inline-flex rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-medium text-slate-500">
            Coming Soon
          </div>
        </div>
      </div>
    </div>
  </KnowledgeSheetShell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Upload, X } from 'lucide-vue-next'
import { Switch } from '~/components/ui/switch'
import KnowledgeSheetShell from './KnowledgeSheetShell.vue'
import {
  knowledgeVectorStatus,
  type CreateKnowledgeEntryPayload,
  type KnowledgeEntry,
  type KnowledgeVectorStatus
} from '~/types/knowledge'

type FormState = {
  node_id: string
  admin_title: string
  meta_tags: string[]
  content: string
  is_enabled: boolean
  vector_status: KnowledgeVectorStatus
}

const props = defineProps<{
  open: boolean
  entry: KnowledgeEntry | null
  nodeId: string | null
  saving?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', value: CreateKnowledgeEntryPayload): void
}>()

const activeTab = ref('content')
const tabs = [
  { id: 'content', label: 'Содержание' },
  { id: 'documents', label: 'Документы (скоро)', disabled: true }
]

const form = ref<FormState>({
  node_id: '',
  admin_title: '',
  meta_tags: [],
  content: '',
  is_enabled: true,
  vector_status: knowledgeVectorStatus.notIndexed
})
const tagInput = ref('')

const isValid = computed(() =>
  form.value.node_id.trim() && form.value.admin_title.trim() && form.value.content.trim()
)

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    activeTab.value = 'content'
    tagInput.value = ''
    if (props.entry) {
      form.value = {
        node_id: props.entry.node_id,
        admin_title: props.entry.admin_title,
        meta_tags: [...props.entry.meta_tags],
        content: props.entry.content,
        is_enabled: props.entry.is_enabled,
        vector_status: props.entry.vector_status
      }
      return
    }
    form.value = {
      node_id: props.nodeId ?? '',
      admin_title: '',
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
    node_id: form.value.node_id,
    admin_title: form.value.admin_title.trim(),
    meta_tags: form.value.meta_tags,
    content: form.value.content.trim(),
    is_enabled: form.value.is_enabled,
    vector_status: form.value.vector_status
  })
}
</script>
