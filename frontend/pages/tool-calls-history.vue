<template>
  <div class="w-full px-4 py-10 flex flex-col gap-8 bg-[#f8fafc] min-h-screen">
    <div class="mx-auto w-full max-w-7xl space-y-8">
      <section class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <h2 class="text-xl font-black text-slate-900">История вызовов инструментов</h2>
          <span class="inline-flex items-center rounded-xl border border-slate-100 bg-white px-3 py-1 text-xs font-bold text-slate-500 shadow-sm">
            Глобальный мониторинг
          </span>
        </div>
      </section>

      <section class="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <article class="rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
          <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">Всего вызовов</p>
          <p class="mt-4 text-3xl font-bold text-slate-900">{{ metrics.total }}</p>
          <p class="mt-2 text-xs text-slate-500">По текущим фильтрам</p>
        </article>

        <article class="rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
          <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">Успешные</p>
          <p class="mt-4 text-3xl font-bold text-emerald-700">{{ metrics.successRate }}%</p>
          <p class="mt-2 text-xs text-slate-500">{{ metrics.successCount }} без ошибок</p>
        </article>

        <article class="rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
          <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">Ошибки</p>
          <p class="mt-4 text-3xl font-bold text-rose-700">{{ metrics.errorCount }}</p>
          <p class="mt-2 text-xs text-slate-500">Требуют проверки</p>
        </article>

        <article class="rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
          <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">Средняя длительность</p>
          <p class="mt-4 text-3xl font-bold text-slate-900">{{ metrics.avgDurationMs }}мс</p>
          <p class="mt-2 text-xs text-slate-500">По записям с duration</p>
        </article>
      </section>

      <section class="rounded-3xl border border-slate-100 bg-white p-3 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="flex flex-col gap-3">
          <div class="flex flex-col gap-2 xl:flex-row xl:items-center">
            <div class="flex w-full flex-wrap items-center gap-2 xl:w-auto">
              <div class="flex items-center gap-2 rounded-2xl border border-slate-100 bg-white px-3 py-1 shadow-sm">
                <input
                  :value="query.dateFrom"
                  type="date"
                  class="h-8 rounded-lg border border-slate-100 px-2 text-xs font-medium text-slate-700 outline-none"
                  :max="query.dateTo || undefined"
                  @change="onDateFromChange"
                >
                <span class="text-xs text-slate-400">—</span>
                <input
                  :value="query.dateTo"
                  type="date"
                  class="h-8 rounded-lg border border-slate-100 px-2 text-xs font-medium text-slate-700 outline-none"
                  :min="query.dateFrom || undefined"
                  @change="onDateToChange"
                >
              </div>

              <div class="flex items-center gap-1">
                <button
                  type="button"
                  class="h-8 rounded-lg border border-slate-100 bg-white px-2.5 text-xs font-semibold text-slate-600 shadow-sm hover:bg-slate-50"
                  @click="applyDaysPreset(7)"
                >
                  7д
                </button>
                <button
                  type="button"
                  class="h-8 rounded-lg border border-slate-100 bg-white px-2.5 text-xs font-semibold text-slate-600 shadow-sm hover:bg-slate-50"
                  @click="applyDaysPreset(30)"
                >
                  30д
                </button>
                <button
                  type="button"
                  class="h-8 rounded-lg border border-slate-100 bg-white px-2.5 text-xs font-semibold text-slate-600 shadow-sm hover:bg-slate-50"
                  @click="applyDaysPreset(90)"
                >
                  90д
                </button>
              </div>
            </div>

            <div class="flex min-w-0 flex-1 items-center gap-2 rounded-2xl border border-slate-100 bg-white px-3 shadow-sm">
              <Search class="h-4 w-4 shrink-0 text-slate-500" />
              <input
                :value="query.search"
                type="text"
                placeholder="Поиск по пользователю, агенту, параметрам..."
                class="h-10 w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
                @input="onSearchInput"
              >
            </div>
          </div>

          <div class="grid grid-cols-1 gap-2 md:grid-cols-3">
            <select
              :value="query.agentId"
              class="h-10 min-w-0 rounded-2xl border border-slate-100 bg-white px-3 text-sm text-slate-700 outline-none shadow-sm"
              @change="updateQuery({ agentId: String(($event.target as HTMLSelectElement).value || '') })"
            >
              <option value="">Все агенты</option>
              <option v-for="agent in agents" :key="agent.id" :value="agent.id">{{ agent.name }}</option>
            </select>

            <select
              :value="query.toolName"
              class="h-10 min-w-0 rounded-2xl border border-slate-100 bg-white px-3 text-sm text-slate-700 outline-none shadow-sm"
              @change="updateQuery({ toolName: String(($event.target as HTMLSelectElement).value || '') })"
            >
              <option value="">Все инструменты</option>
              <option v-for="tool in toolOptions" :key="tool" :value="tool">{{ tool }}</option>
            </select>

            <select
              :value="query.status"
              class="h-10 min-w-0 rounded-2xl border border-slate-100 bg-white px-3 text-sm text-slate-700 outline-none shadow-sm"
              @change="updateQuery({ status: (($event.target as HTMLSelectElement).value || '') as ToolCallHistoryQuery['status'] })"
            >
              <option value="">Любой статус</option>
              <option value="success">Success</option>
              <option value="error">Error</option>
            </select>
          </div>
        </div>
      </section>

      <section class="space-y-4">
        <div v-if="errorMessage" class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {{ errorMessage }}
        </div>
        <div v-else-if="isDateRangeInvalid" class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          Дата начала не может быть позже даты окончания.
        </div>

        <div v-if="pending && !items.length" class="rounded-3xl border border-slate-100 bg-white px-4 py-12 text-center text-sm text-slate-500 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
          Загрузка истории вызовов...
        </div>

        <template v-else-if="items.length">
          <article
            v-for="item in items"
            :key="item.id"
            class="rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
          >
            <button
              type="button"
              class="grid w-full grid-cols-1 gap-3 px-5 py-4 text-left lg:grid-cols-[minmax(220px,1.2fr)_minmax(220px,1.2fr)_minmax(180px,1fr)_40px]"
              @click="toggleExpanded(item.id)"
            >
              <div class="min-w-0 space-y-1">
                <p class="truncate text-sm font-semibold text-slate-900">{{ item.user.name }}</p>
                <p class="truncate text-xs text-slate-500">
                  {{ item.user.username ? `@${item.user.username}` : '—' }} · {{ item.agent.name }}
                </p>
              </div>

              <div class="min-w-0 space-y-1">
                <div class="flex min-w-0 items-center gap-2">
                  <component
                    :is="toolLinkComponent(item.toolSettingsUrl)"
                    v-bind="toolLinkProps(item.toolSettingsUrl)"
                    class="truncate text-sm font-semibold text-slate-900 underline-offset-2 hover:underline"
                    @click.stop
                  >
                    {{ item.toolName }}
                  </component>
                </div>
                <p class="truncate text-xs text-slate-500">{{ item.toolDescription }}</p>
              </div>

              <div class="space-y-1 text-right">
                <span
                  class="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold"
                  :class="item.status === 'success' ? 'bg-emerald-100 text-emerald-700' : item.status === 'error' ? 'bg-rose-100 text-rose-700' : 'bg-slate-100 text-slate-600'"
                >
                  {{ item.status }}
                </span>
                <p class="text-xs text-slate-500">{{ formatDateTime(item.invokedAt) }}</p>
                <p class="text-xs text-slate-500">{{ item.durationMs !== null ? `${item.durationMs}мс` : '—' }}</p>
              </div>

              <span class="flex items-center justify-end text-slate-500">
                <ChevronDown class="h-5 w-5 transition-transform" :class="isExpanded(item.id) ? 'rotate-180' : ''" />
              </span>
            </button>

            <div class="px-5 pb-4" :class="isExpanded(item.id) ? 'block' : 'hidden'">
              <div class="mb-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50/70 p-3">
                <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">Параметры вызова</p>
                <div v-if="item.params.length" class="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <div
                    v-for="param in item.params"
                    :key="`${item.id}-${param.key}`"
                    class="rounded-xl border border-slate-100 bg-white px-3 py-2 shadow-sm"
                  >
                    <p class="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{{ param.key }}</p>
                    <p class="mt-1 text-xs text-slate-700">{{ previewValue(param.value) }}</p>
                  </div>
                </div>
                <p v-else class="text-xs text-slate-500">Параметры отсутствуют</p>
              </div>

              <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
                <div class="overflow-hidden rounded-xl border border-slate-700 bg-slate-900">
                  <div class="border-b border-slate-700 px-3 py-2 text-xs font-semibold text-slate-300">Request</div>
                  <pre class="max-h-80 overflow-auto p-3 text-xs text-slate-200">{{ toPrettyJson(item.requestPayload || paramsToObject(item.params)) }}</pre>
                </div>
                <div
                  class="overflow-hidden rounded-xl border"
                  :class="item.status === 'error' ? 'border-rose-800 bg-rose-950' : 'border-slate-700 bg-slate-900'"
                >
                  <div class="border-b px-3 py-2 text-xs font-semibold" :class="item.status === 'error' ? 'border-rose-800 text-rose-200' : 'border-slate-700 text-slate-300'">
                    {{ item.status === 'error' ? 'Error Response' : 'Response' }}
                  </div>
                  <pre class="max-h-80 overflow-auto p-3 text-xs" :class="item.status === 'error' ? 'text-rose-100' : 'text-slate-200'">{{ toPrettyJson(item.status === 'error' ? item.errorPayload : item.responsePayload) }}</pre>
                </div>
              </div>
            </div>

            <div v-if="!isExpanded(item.id)" class="space-y-2 px-5 pb-4">
              <div class="flex items-start gap-2 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                <span class="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600">REQ</span>
                <p class="truncate text-xs text-slate-700">{{ buildRequestPreview(item.params) }}</p>
              </div>
              <div class="flex items-start gap-2 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                <span
                  class="rounded px-1.5 py-0.5 text-[10px] font-bold"
                  :class="item.status === 'error' ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'"
                >
                  {{ item.status === 'error' ? 'ERR' : 'RES' }}
                </span>
                <p class="truncate text-xs text-slate-700">
                  {{ item.status === 'error' ? previewValue(item.errorPayload) : previewValue(item.responsePayload) }}
                </p>
              </div>
            </div>
          </article>
        </template>

        <div v-else class="rounded-3xl border border-slate-100 bg-white px-4 py-10 text-center text-sm text-slate-500 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
          По выбранным фильтрам вызовов не найдено.
        </div>
      </section>

      <section class="flex items-center justify-between">
        <p class="text-xs text-slate-500">Показано {{ items.length }} из {{ total }}</p>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="h-9 rounded-xl border border-slate-100 bg-white px-3 text-sm font-semibold text-slate-700 shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="pending || currentPage <= 1"
            @click="setPage(currentPage - 1)"
          >
            Назад
          </button>
          <span class="text-xs text-slate-500">Страница {{ currentPage }} / {{ totalPages }}</span>
          <button
            type="button"
            class="h-9 rounded-xl border border-slate-100 bg-white px-3 text-sm font-semibold text-slate-700 shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="pending || currentPage >= totalPages"
            @click="setPage(currentPage + 1)"
          >
            Далее
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ChevronDown, Search } from 'lucide-vue-next'
import { useToolCallsHistory } from '~/composables/useToolCallsHistory'
import type { ToolCallHistoryQuery } from '~/types/analytics'

definePageMeta({
  middleware: 'auth',
})

const { pageTitle } = useLayoutState()
const expandedRows = ref<Set<string>>(new Set())
const searchDebounce = ref<number | null>(null)

const {
  query,
  agents,
  items,
  total,
  currentPage,
  totalPages,
  toolOptions,
  pending,
  error,
  initialize,
  updateQuery,
  setPage,
} = useToolCallsHistory()

const errorMessage = computed(() => {
  const value = error.value as any
  if (!value) return null
  return value?.data?.message || value?.message || 'Не удалось загрузить историю вызовов'
})

const metrics = computed(() => {
  const successCount = items.value.filter(item => item.status === 'success').length
  const errorCount = items.value.filter(item => item.status === 'error').length
  const samples = items.value.filter(item => item.durationMs !== null).map(item => Number(item.durationMs))
  const avgDurationMs = samples.length ? Math.round(samples.reduce((sum, value) => sum + value, 0) / samples.length) : 0
  const successRate = items.value.length ? Math.round((successCount / items.value.length) * 1000) / 10 : 0

  return {
    total: total.value,
    successCount,
    errorCount,
    avgDurationMs,
    successRate,
  }
})

const isDateRangeInvalid = computed(() => {
  if (!query.dateFrom || !query.dateTo) return false
  return query.dateFrom > query.dateTo
})

const isExpanded = (id: string) => expandedRows.value.has(id)

const toggleExpanded = (id: string) => {
  const next = new Set(expandedRows.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedRows.value = next
}

const paramsToObject = (params: Array<{ key: string; value: unknown }>) =>
  params.reduce<Record<string, unknown>>((acc, param) => {
    acc[param.key] = param.value
    return acc
  }, {})

const buildRequestPreview = (params: Array<{ key: string; value: unknown }>) => {
  if (!params.length) return 'Параметры отсутствуют'
  return params
    .slice(0, 3)
    .map((param) => `${param.key}: ${previewValue(param.value)}`)
    .join(', ')
}

const previewValue = (value: unknown) => {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

const toPrettyJson = (payload: unknown) => {
  if (payload === null || payload === undefined || payload === '') return '—'
  if (typeof payload === 'string') {
    try {
      return JSON.stringify(JSON.parse(payload), null, 2)
    } catch {
      return payload
    }
  }
  try {
    return JSON.stringify(payload, null, 2)
  } catch {
    return String(payload)
  }
}

const formatDateTime = (value: string) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const isExternalUrl = (value: string) => /^https?:\/\//.test(value)

const toolLinkComponent = (url: string | null) => {
  if (!url) return 'span'
  return isExternalUrl(url) ? 'a' : 'NuxtLink'
}

const toolLinkProps = (url: string | null) => {
  if (!url) return {}
  if (isExternalUrl(url)) return { href: url, target: '_blank', rel: 'noopener noreferrer' }
  return { to: url }
}

const onSearchInput = (event: Event) => {
  const value = String((event.target as HTMLInputElement).value || '')
  if (searchDebounce.value) window.clearTimeout(searchDebounce.value)
  searchDebounce.value = window.setTimeout(() => {
    updateQuery({ search: value })
  }, 300)
}

const formatDateInput = (date: Date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const onDateFromChange = (event: Event) => {
  const value = String((event.target as HTMLInputElement).value || '')
  if (!value) return
  if (query.dateTo && value > query.dateTo) return
  updateQuery({ dateFrom: value })
}

const onDateToChange = (event: Event) => {
  const value = String((event.target as HTMLInputElement).value || '')
  if (!value) return
  if (query.dateFrom && value < query.dateFrom) return
  updateQuery({ dateTo: value })
}

const applyDaysPreset = (days: number) => {
  const dateTo = new Date()
  const dateFrom = new Date(dateTo)
  dateFrom.setDate(dateFrom.getDate() - (days - 1))
  updateQuery({
    dateFrom: formatDateInput(dateFrom),
    dateTo: formatDateInput(dateTo),
  })
}

await initialize()

onMounted(() => {
  pageTitle.value = 'История вызовов'
})
</script>
