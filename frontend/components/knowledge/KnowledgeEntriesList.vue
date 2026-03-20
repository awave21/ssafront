<template>
  <div class="space-y-4 max-w-full overflow-hidden">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          :disabled="!selectedNodeId"
          class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-md bg-indigo-600 px-5 text-sm font-bold text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          @click="$emit('create')"
        >
          <Plus class="h-4 w-4" />
          Добавить запись
        </button>
        <div v-if="selectedNodeTitle" class="inline-flex h-10 items-center rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-600">
          Папка:
          <span class="ml-1 font-semibold text-slate-900">{{ selectedNodeTitle }}</span>
        </div>
      </div>

      <div class="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
        <div class="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
          <span class="font-medium text-slate-900">Всего:</span>
          <span>{{ filteredEntries.length }}</span>
        </div>
        <div class="inline-flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
          <span class="font-medium">Активных:</span>
          <span>{{ activeEntriesCount }}</span>
        </div>
        <div class="relative min-w-0 grow sm:grow-0">
          <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Поиск..."
            class="h-10 w-full min-w-0 rounded-md border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm transition-all duration-300 outline-none focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 sm:w-64"
          />
        </div>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-12">
      <Loader2 class="h-8 w-8 animate-spin text-indigo-600" />
    </div>

    <div
      v-else-if="!selectedNodeId"
      class="rounded-md border border-dashed border-slate-200 bg-slate-50 p-10 text-center"
    >
      <p class="text-sm font-medium text-slate-700">Выберите папку слева, чтобы увидеть записи</p>
    </div>

    <div
      v-else-if="entries.length === 0"
      class="rounded-md border border-border bg-background p-12 text-center"
    >
      <div class="mx-auto max-w-md">
        <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-slate-100">
          <FileText class="h-8 w-8 text-slate-400" />
        </div>
        <h3 class="text-lg font-bold text-slate-900">Записей пока нет</h3>
        <p class="mt-2 mb-6 text-slate-500">Создайте первую текстовую запись для выбранной папки</p>
        <button
          type="button"
          class="rounded-md bg-indigo-600 px-6 py-3 text-sm font-bold text-white transition-colors hover:bg-indigo-700"
          @click="$emit('create')"
        >
          Добавить запись
        </button>
      </div>
    </div>

    <div
      v-else-if="filteredEntries.length === 0"
      class="rounded-md border border-border bg-background p-8 text-center"
    >
      <p class="text-slate-500">Ничего не найдено по запросу "{{ searchQuery }}"</p>
    </div>

    <div v-else class="grid gap-2 max-w-full">
      <button
        v-for="entry in filteredEntries"
        :key="entry.id"
        type="button"
        class="group w-full rounded-md border border-slate-200 bg-white p-4 text-left transition-colors hover:border-indigo-200 hover:bg-indigo-50/20"
        @click="$emit('select', entry)"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="truncate text-sm font-bold text-slate-900">{{ entry.admin_title }}</p>
            <p class="mt-1 line-clamp-2 text-xs text-slate-500">{{ entry.content }}</p>
            <div v-if="entry.meta_tags.length" class="mt-2 flex flex-wrap gap-1.5">
              <span
                v-for="tag in entry.meta_tags"
                :key="tag"
                class="inline-flex items-center rounded-full border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700"
              >
                #{{ tag }}
              </span>
            </div>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold" :class="vectorBadgeClass(entry.vector_status)">
              {{ vectorStatusLabel(entry.vector_status) }}
            </span>
            <button
              type="button"
              class="rounded p-1.5 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
              @click.stop="$emit('delete', entry.id)"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { FileText, Loader2, Plus, Search, Trash2 } from 'lucide-vue-next'
import { knowledgeVectorStatus, type KnowledgeEntry, type KnowledgeVectorStatus } from '~/types/knowledge'

const props = defineProps<{
  selectedNodeId: string | null
  selectedNodeTitle?: string | null
  entries: KnowledgeEntry[]
  loading?: boolean
}>()

defineEmits<{
  (e: 'create'): void
  (e: 'select', entry: KnowledgeEntry): void
  (e: 'delete', id: string): void
}>()

const searchQuery = ref('')

const filteredEntries = computed(() => {
  if (!searchQuery.value.trim()) return props.entries
  const query = searchQuery.value.toLowerCase()
  return props.entries.filter((entry) =>
    entry.admin_title.toLowerCase().includes(query)
    || entry.content.toLowerCase().includes(query)
    || entry.meta_tags.some((tag) => tag.toLowerCase().includes(query))
  )
})

const activeEntriesCount = computed(() => filteredEntries.value.filter((entry) => entry.is_enabled).length)

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
</script>
