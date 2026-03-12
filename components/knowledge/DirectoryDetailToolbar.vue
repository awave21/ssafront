<template>
  <div class="flex flex-wrap items-center justify-between gap-3 bg-background rounded-md border border-border p-3">
    <div class="flex items-center gap-2">
      <button
        @click="$emit('addRow')"
        :disabled="addDisabled"
        class="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-bold hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Plus class="w-4 h-4" />
        Добавить
      </button>
      <button
        disabled
        class="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-lg text-sm font-medium transition-colors opacity-50 cursor-not-allowed"
      >
        <Upload class="w-4 h-4" />
        Загрузить CSV
      </button>
      <button
        @click="$emit('export')"
        class="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
        :disabled="!hasItems"
        :class="{ 'opacity-50 cursor-not-allowed': !hasItems }"
        title="Выгрузить в CSV"
      >
        <Download class="w-4 h-4" />
        Выгрузить CSV
      </button>
    </div>

    <div class="flex items-center gap-2">
      <button
        v-if="selectedCount > 0"
        @click="$emit('deleteSelected')"
        class="flex items-center gap-2 px-4 py-2 bg-red-50 border border-red-200 text-red-600 rounded-lg text-sm font-medium hover:bg-red-100 transition-colors"
      >
        <Trash2 class="w-4 h-4" />
        Удалить ({{ selectedCount }})
      </button>
      <div class="relative">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          :value="searchQuery"
          @input="$emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
          type="text"
          placeholder="Поиск..."
          class="pl-9 pr-4 py-2 w-48 text-sm border border-slate-200 rounded-lg bg-slate-50 focus:bg-white focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 transition-all"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Plus, Upload, Download, Search, Trash2 } from 'lucide-vue-next'

defineProps<{
  addDisabled: boolean
  hasItems: boolean
  selectedCount: number
  searchQuery: string
}>()

defineEmits<{
  (e: 'addRow'): void
  (e: 'import'): void
  (e: 'export'): void
  (e: 'deleteSelected'): void
  (e: 'update:searchQuery', value: string): void
}>()
</script>
