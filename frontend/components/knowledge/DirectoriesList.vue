<template>
  <div class="max-w-full space-y-6 overflow-hidden">
    <!-- Header with Create Button -->
    <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <button
        @click="$emit('create')"
        class="inline-flex h-10 shrink-0 self-start items-center gap-2 whitespace-nowrap rounded-xl bg-indigo-600 px-5 text-sm font-bold text-white transition-colors hover:bg-indigo-700"
      >
        <Plus class="w-4 h-4" />
        {{ createButtonLabel }}
      </button>

      <div v-if="directories.length > 0" class="relative min-w-0 grow sm:grow-0">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Поиск..."
          class="h-10 w-full min-w-0 rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm transition-all duration-300 outline-none focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 sm:w-64"
        />
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-12">
      <Loader2 class="w-8 h-8 animate-spin text-indigo-600" />
    </div>

    <!-- Error State -->
    <div 
      v-else-if="error"
      class="rounded-3xl border border-red-200 bg-red-50 p-8 text-center"
    >
      <div class="max-w-md mx-auto">
        <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <AlertCircle class="h-8 w-8 text-red-500" />
        </div>
        <h3 class="text-lg font-bold text-red-900">Ошибка загрузки</h3>
        <p class="text-red-600 mt-2 mb-4">{{ error }}</p>
        <p class="text-sm text-red-500 mb-4">
          {{ mode === 'table' ? 'Убедитесь, что API таблиц реализован на бэкенде' : 'Убедитесь, что API справочников реализован на бэкенде' }}
        </p>
        <button
          @click="$emit('retry')"
          class="rounded-xl bg-red-600 px-5 py-2.5 text-sm font-bold text-white transition-colors hover:bg-red-700"
        >
          Повторить
        </button>
      </div>
    </div>

    <!-- Empty State -->
    <div 
      v-else-if="directories.length === 0" 
      class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center"
    >
      <div class="max-w-md mx-auto">
        <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <component :is="emptyIcon" class="h-8 w-8 text-slate-400" />
        </div>
        <h3 class="text-lg font-bold text-slate-900">{{ emptyTitle }}</h3>
        <p class="text-slate-500 mt-2">
          {{ emptyDescription }}
        </p>
      </div>
    </div>

    <!-- No Results -->
    <div 
      v-else-if="filteredDirectories.length === 0" 
      class="rounded-3xl border border-slate-100 bg-white p-8 text-center"
    >
      <p class="text-slate-500">Ничего не найдено по запросу "{{ searchQuery }}"</p>
    </div>

    <!-- Directories Grid -->
    <div v-else class="flex w-full min-w-0 flex-col gap-4">
      <DirectoryCard
        v-for="dir in filteredDirectories"
        :key="dir.id"
        :directory="dir"
        @click="$emit('select', dir)"
        @toggle="(enabled) => $emit('toggle', dir.id, enabled)"
        @settings="$emit('settings', dir)"
        @delete="$emit('delete', dir)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Plus, Search, Loader2, BookOpen, AlertCircle, Table2 } from 'lucide-vue-next'
import DirectoryCard from './DirectoryCard.vue'
import type { Directory } from '~/types/directories'

const props = defineProps<{
  directories: Directory[]
  mode?: 'directory' | 'table'
  loading?: boolean
  error?: string | null
}>()

defineEmits<{
  (e: 'create'): void
  (e: 'select', directory: Directory): void
  (e: 'toggle', id: string, enabled: boolean): void
  (e: 'settings', directory: Directory): void
  (e: 'delete', directory: Directory): void
  (e: 'retry'): void
}>()

const searchQuery = ref('')
const mode = computed(() => props.mode ?? 'directory')
const createButtonLabel = computed(() => (mode.value === 'table' ? 'Добавить таблицу' : 'Добавить'))
const emptyIcon = computed(() => (mode.value === 'table' ? Table2 : BookOpen))
const emptyTitle = computed(() => (mode.value === 'table' ? 'Таблиц пока нет' : 'Справочников пока нет'))
const emptyDescription = computed(() => (
  mode.value === 'table'
    ? 'Создайте таблицу с атрибутами и записями для работы функций поиска, создания и обновления данных.'
    : 'Создайте справочник для хранения FAQ, каталога услуг или другой структурированной информации.'
))

const filteredDirectories = computed(() => {
  if (!searchQuery.value.trim()) {
    return props.directories
  }
  const query = searchQuery.value.toLowerCase()
  return props.directories.filter(dir => 
    dir.name.toLowerCase().includes(query) ||
    dir.tool_name.toLowerCase().includes(query)
  )
})
</script>
