<template>
  <div class="max-w-full space-y-6 overflow-hidden">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl bg-indigo-600 px-5 text-sm font-bold text-white transition-colors hover:bg-indigo-700"
          @click="$emit('create-folder')"
        >
          <FolderPlus class="h-4 w-4" />
          Папка
        </button>
        <button
          type="button"
          class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
          @click="$emit('create-file')"
        >
          <FilePlus2 class="h-4 w-4" />
          Файл
        </button>
      </div>

      <div class="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
        <div class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
          <span class="font-medium text-slate-900">Элементов:</span>
          <span>{{ filteredItems.length }}</span>
        </div>
        <div class="relative min-w-0 grow sm:grow-0">
          <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Поиск..."
            class="h-10 w-full min-w-0 rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm transition-all duration-300 outline-none focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 sm:w-64"
          />
        </div>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-12">
      <Loader2 class="h-8 w-8 animate-spin text-indigo-600" />
    </div>

    <div
      v-else-if="filteredItems.length === 0"
      class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center"
    >
      <div class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-50 text-slate-300">
        <Folder class="h-6 w-6" />
      </div>
      <p class="text-sm font-medium text-slate-600">Здесь пока пусто</p>
      <p class="mt-1 text-xs text-slate-400">Создайте папку или текстовый файл</p>
    </div>

    <div v-else class="grid max-w-full gap-4 md:grid-cols-2 xl:grid-cols-3">
      <div
        v-for="item in filteredItems"
        :key="item.id"
        class="group relative w-full overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 text-left shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
        :class="item.type === knowledgeItemType.file && item.vector_status === knowledgeVectorStatus.indexing ? 'border-indigo-200 bg-indigo-50/20' : ''"
        :draggable="item.type === knowledgeItemType.file"
        role="button"
        tabindex="0"
        @click="handleCardClick(item)"
        @dragstart="onDragStart(item.id)"
        @dragover.prevent="onFolderDragOver(item)"
        @drop.prevent="onFolderDrop(item)"
      >
        <div class="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150" />
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 text-left">
            <div class="flex items-center gap-2">
              <Folder v-if="item.type === knowledgeItemType.folder" class="h-4 w-4 shrink-0 text-indigo-600" />
              <FileText v-else class="h-4 w-4 shrink-0 text-slate-500" />
              <p class="truncate text-sm font-bold text-slate-900">{{ item.title }}</p>
              <span v-if="item.type === knowledgeItemType.folder" class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">
                {{ folderChildrenCount.get(item.id) ?? 0 }}
              </span>
            </div>

            <p v-if="item.type === knowledgeItemType.file" class="mt-1 line-clamp-2 text-xs text-slate-500">
              {{ item.content }}
            </p>

            <div v-if="item.type === knowledgeItemType.file && item.meta_tags.length" class="mt-2 flex flex-wrap gap-1.5">
              <span
                v-for="tag in item.meta_tags"
                :key="tag"
                class="inline-flex items-center rounded-full border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700"
              >
                #{{ tag }}
              </span>
            </div>
          </div>

          <div class="flex shrink-0 items-center gap-2">
            <span
              v-if="item.type === knowledgeItemType.file"
              class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
              :class="vectorBadgeClass(item.vector_status)"
            >
              {{ vectorStatusLabel(item.vector_status) }}
            </span>

            <button
              v-if="item.type === knowledgeItemType.file"
              type="button"
              class="rounded-xl p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
              @click.stop="$emit('move-click', item.id)"
            >
              <MoveRight class="h-4 w-4" />
            </button>

            <button
              type="button"
              class="rounded-xl p-1.5 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
              @click.stop="$emit('delete', item.id)"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
        </div>

        <div
          v-if="item.type === knowledgeItemType.file && item.vector_status === knowledgeVectorStatus.indexing"
          class="mt-3 rounded-2xl border border-indigo-100 bg-white/80 p-3"
        >
          <div class="mb-2 flex items-center justify-between">
            <span class="text-[10px] font-black uppercase tracking-wider text-indigo-600">Индексация</span>
            <span class="text-[10px] font-medium text-indigo-500 animate-pulse">
              {{ indexStatusLabel(item.id) }} · {{ indexProgress(item.id) }}%
            </span>
          </div>
          <div class="h-2 w-full overflow-hidden rounded-full bg-slate-100 p-0.5">
            <div
              class="h-full rounded-full bg-gradient-to-r from-indigo-500 to-indigo-300 shadow-[0_0_8px_rgba(99,102,241,0.3)] animate-pulse"
              :style="{ width: `${indexProgress(item.id)}%` }"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { FilePlus2, FileText, Folder, FolderPlus, Loader2, MoveRight, Search, Trash2 } from 'lucide-vue-next'
import {
  knowledgeIndexJobStatus,
  knowledgeItemType,
  knowledgeVectorStatus,
  type KnowledgeFileItem,
  type KnowledgeIndexJobStatus,
  type KnowledgeVectorStatus
} from '~/types/knowledge'

const props = defineProps<{
  items: KnowledgeFileItem[]
  folderChildrenCount: Map<string, number>
  indexProgressByItem?: Record<string, number>
  indexStateByItem?: Record<string, KnowledgeIndexJobStatus>
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'open-folder', id: string): void
  (e: 'open-file', id: string): void
  (e: 'create-folder'): void
  (e: 'create-file'): void
  (e: 'delete', id: string): void
  (e: 'move-click', id: string): void
  (e: 'move-drop', itemId: string, targetFolderId: string): void
}>()

const searchQuery = ref('')
const draggingItemId = ref<string | null>(null)

const filteredItems = computed(() => {
  if (!searchQuery.value.trim()) return props.items
  const query = searchQuery.value.toLowerCase()
  return props.items.filter((item) =>
    item.title.toLowerCase().includes(query)
    || item.content.toLowerCase().includes(query)
    || item.meta_tags.some((tag) => tag.toLowerCase().includes(query))
  )
})

const handleCardClick = (item: KnowledgeFileItem) => {
  if (item.type === knowledgeItemType.folder) emit('open-folder', item.id)
  else emit('open-file', item.id)
}

const onDragStart = (itemId: string) => {
  draggingItemId.value = itemId
}

const onFolderDragOver = (target: KnowledgeFileItem) => {
  if (target.type !== knowledgeItemType.folder) return
}

const onFolderDrop = (target: KnowledgeFileItem) => {
  if (target.type !== knowledgeItemType.folder || !draggingItemId.value) return
  emit('move-drop', draggingItemId.value, target.id)
  draggingItemId.value = null
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

const indexProgress = (itemId: string) => {
  const value = props.indexProgressByItem?.[itemId]
  if (typeof value !== 'number' || !Number.isFinite(value)) return 65
  return Math.max(0, Math.min(100, Math.round(value)))
}

const indexStatusLabel = (itemId: string) => {
  const status = props.indexStateByItem?.[itemId]
  if (status === knowledgeIndexJobStatus.queued) return 'В очереди'
  if (status === knowledgeIndexJobStatus.indexing) return 'В процессе'
  if (status === knowledgeIndexJobStatus.indexed) return 'Готово'
  if (status === knowledgeIndexJobStatus.failed) return 'Ошибка'
  return 'В процессе'
}
</script>
