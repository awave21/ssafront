<template>
  <div class="max-w-full space-y-6 overflow-hidden">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <button
        type="button"
        class="inline-flex h-10 shrink-0 self-start items-center gap-2 whitespace-nowrap rounded-xl bg-indigo-600 px-5 text-sm font-bold text-white transition-colors hover:bg-indigo-700"
        @click="$emit('create')"
      >
        <Plus class="h-4 w-4" />
        Добавить таблицу
      </button>

      <div v-if="tables.length > 0" class="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
        <div class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
          <span class="font-medium text-slate-900">Таблиц:</span>
          <span>{{ tables.length }}</span>
        </div>
        <div class="inline-flex items-center gap-2 rounded-xl border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs text-cyan-800">
          <span class="font-medium">Записей всего:</span>
          <span>{{ totalRecordsCount }}</span>
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

    <div v-else-if="error" class="rounded-3xl border border-red-200 bg-red-50 p-8 text-center">
      <p class="text-sm text-red-600">{{ error }}</p>
      <button class="mt-4 rounded-xl bg-red-600 px-5 py-2.5 text-sm font-bold text-white transition-colors hover:bg-red-700" @click="$emit('retry')">
        Повторить
      </button>
    </div>

    <div
      v-else-if="tables.length === 0"
      class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center"
    >
      <div class="mx-auto max-w-md">
        <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-cyan-50">
          <Table2 class="h-8 w-8 text-cyan-600" />
        </div>
        <h3 class="text-lg font-bold text-slate-900">Таблиц пока нет</h3>
        <p class="mb-6 mt-2 text-slate-500">
          Создайте таблицу для структурированных данных — как в справочнике, но со своими колонками и типами.
        </p>
        <button
          type="button"
          class="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-bold text-white transition-colors hover:bg-indigo-700"
          @click="$emit('create')"
        >
          Добавить первую таблицу
        </button>
      </div>
    </div>

    <div v-else-if="filteredTables.length === 0" class="rounded-3xl border border-slate-100 bg-white p-8 text-center">
      <p class="text-slate-500">Ничего не найдено по запросу "{{ searchQuery }}"</p>
    </div>

    <div v-else class="w-full min-w-0 space-y-4">
      <button
        v-for="table in filteredTables"
        :key="table.id"
        type="button"
        class="group relative w-full min-w-0 max-w-full cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 text-left shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-shadow duration-500 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
        @click="$emit('select', table.id)"
      >
        <div
          class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-cyan-500/5 transition-transform duration-700 group-hover:scale-150"
        />
        <div class="relative flex items-center justify-between gap-4">
          <div class="flex min-w-0 flex-1 items-center gap-4 sm:gap-4">
            <div
              class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-cyan-50 transition-colors group-hover:bg-cyan-100"
            >
              <Table2 class="h-5 w-5 text-cyan-600" />
            </div>
            <div class="min-w-0">
              <h4 class="truncate font-bold text-slate-900">{{ table.name }}</h4>
              <p v-if="table.description" class="mt-0.5 line-clamp-2 text-xs text-slate-600">
                {{ table.description }}
              </p>
            </div>
          </div>
          <div class="flex shrink-0 items-center gap-3">
            <div class="text-right">
              <p class="text-sm font-bold text-slate-900">{{ table.records_count }}</p>
              <p class="text-xs text-slate-500">записей</p>
            </div>
            <ChevronRight
              class="h-5 w-5 text-slate-300 transition-colors group-hover:text-cyan-500"
              aria-hidden="true"
            />
          </div>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronRight, Loader2, Plus, Search, Table2 } from 'lucide-vue-next'
import type { TableItem } from '~/types/tables'

const props = defineProps<{
  tables: TableItem[]
  loading?: boolean
  error?: string | null
}>()

defineEmits<{
  (e: 'create'): void
  (e: 'retry'): void
  (e: 'select', tableId: string): void
}>()

const searchQuery = ref('')

const filteredTables = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.tables
  return props.tables.filter((table) => {
    const name = table.name.toLowerCase()
    const description = (table.description ?? '').toLowerCase()
    return name.includes(q) || description.includes(q)
  })
})

const totalRecordsCount = computed(() =>
  props.tables.reduce((sum, t) => sum + (t.records_count ?? 0), 0)
)
</script>

