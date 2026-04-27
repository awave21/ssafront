<template>
  <AgentPageShell title="Потоки эксперта" :hide-actions="true" :contained="true">
    <div class="max-w-full space-y-6">
      <!-- Header: actions + search -->
      <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl bg-indigo-600 px-5 text-sm font-bold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
            :disabled="creating"
            @click="handleCreate()"
          >
            <Plus class="h-4 w-4" />
            {{ creating ? 'Создаём…' : 'Создать поток' }}
          </button>
          <NuxtLink
            :to="`/agents/${agentId}/scripts/library`"
            class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
            title="Общая библиотека сущностей (Motive / Argument / Proof / Objection / Constraint / Outcome)"
          >
            <Library class="h-4 w-4" />
            Библиотека
          </NuxtLink>
        </div>

        <div v-if="flows.length > 0" class="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
          <div class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
            <span class="font-medium text-slate-900">Всего:</span>
            <span>{{ flows.length }}</span>
          </div>
          <div class="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
            <span class="font-medium">Опубликовано:</span>
            <span>{{ publishedCount }}</span>
          </div>
          <div class="relative min-w-0 grow sm:grow-0">
            <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Поиск по названию или когда релевантно…"
              class="h-10 w-full min-w-0 rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm outline-none transition-all duration-300 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 sm:w-80"
            >
          </div>
        </div>
      </div>

      <!-- Error -->
      <div
        v-if="error"
        class="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      >
        <span>{{ error }}</span>
        <button type="button" class="font-semibold underline" @click="fetchFlows">
          Повторить
        </button>
      </div>

      <!-- Loading -->
      <div v-if="isLoading && !flows.length" class="flex justify-center py-12">
        <Loader2 class="h-8 w-8 animate-spin text-indigo-600" />
      </div>

      <!-- Empty state -->
      <div
        v-else-if="flows.length === 0"
        class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center"
      >
        <div class="mx-auto max-w-md">
          <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-slate-100">
            <Workflow class="h-8 w-8 text-slate-400" />
          </div>
          <h3 class="text-lg font-bold text-slate-900">Потоков пока нет</h3>
          <p class="mb-6 mt-2 text-slate-500">
            Создайте первый сценарий продаж — канвас с нодами, связанными со сущностями библиотеки.
          </p>
          <button
            type="button"
            class="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-bold text-white transition-colors hover:bg-indigo-700"
            :disabled="creating"
            @click="handleCreate()"
          >
            Создать первый поток
          </button>
        </div>
      </div>

      <!-- No results -->
      <div
        v-else-if="filteredFlows.length === 0"
        class="rounded-3xl border border-slate-100 bg-white p-8 text-center"
      >
        <p class="text-slate-500">Ничего не найдено по запросу «{{ searchQuery }}»</p>
      </div>

      <!-- Cards list -->
      <div v-else class="w-full min-w-0 space-y-4">
        <div
          v-for="flow in filteredFlows"
          :key="flow.id"
          class="group relative min-w-0 max-w-full cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-shadow duration-500 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
          @click="openFlow(flow.id)"
        >
          <div
            class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150"
          />

          <div class="flex items-start justify-between gap-4">
            <div class="flex min-w-0 flex-1 items-start gap-4">
              <div class="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-indigo-50 transition-colors group-hover:bg-indigo-100">
                <Workflow class="h-5 w-5 text-indigo-600" />
              </div>

              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <h4 class="truncate text-base font-bold text-slate-900">{{ flow.name }}</h4>
                  <span
                    class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
                    :class="flow.flow_status === 'published'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-slate-100 text-slate-600 border border-slate-200'"
                  >
                    {{ flow.flow_status === 'published' ? 'Опубликован' : 'Черновик' }}
                  </span>
                  <span
                    v-if="indexBadge(flow.index_status)"
                    class="inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium"
                    :class="indexBadge(flow.index_status)!.className"
                  >
                    {{ indexBadge(flow.index_status)!.label }}
                  </span>
                </div>
                <p class="mt-1 line-clamp-1 break-all text-xs text-slate-600">
                  {{ flowWhenRelevant(flow) || 'Когда релевантно не заполнено' }}
                </p>

                <div class="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                  <span class="inline-flex items-center gap-1">
                    <Workflow class="h-3.5 w-3.5 text-slate-400" />
                    {{ nodeCount(flow) }} узлов
                  </span>
                  <span
                    class="inline-flex items-center gap-1"
                    :class="kgLinkCount(flow) > 0 ? 'text-indigo-700 font-medium' : 'text-slate-400'"
                    :title="kgLinkCount(flow) > 0
                      ? 'Сколько ссылок на сущности библиотеки стоит на нодах'
                      : 'Ни один узел не связан с библиотекой — LLM не получит мотивы/аргументы'"
                  >
                    <Link2 class="h-3.5 w-3.5" />
                    {{ kgLinkCount(flow) }} связей с библиотекой
                  </span>
                  <span
                    v-if="unlinkedContentCount(flow) > 0"
                    class="inline-flex items-center gap-1 text-amber-600"
                    title="Узлов контента без единой связи с библиотекой — их стоит проработать"
                  >
                    <AlertTriangle class="h-3.5 w-3.5" />
                    {{ unlinkedContentCount(flow) }} без связи
                  </span>
                </div>
              </div>
            </div>

            <div
              class="relative z-20 flex shrink-0 items-center gap-1.5"
              @click.stop
            >
              <button
                type="button"
                class="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
                title="Открыть канвас"
                @click="openFlow(flow.id)"
              >
                <Pencil class="h-3.5 w-3.5" />
                Открыть
              </button>
              <button
                v-if="!isFlowIndexing(flow) && publishingId !== flow.id"
                type="button"
                class="inline-flex h-8 items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 text-xs font-medium text-emerald-700 transition-colors hover:bg-emerald-100 disabled:opacity-50"
                title="Опубликовать поток и поставить индексацию в очередь"
                @click="handlePublish(flow)"
              >
                <UploadCloud class="h-3.5 w-3.5" />
                Опубликовать
              </button>
              <button
                v-else-if="publishingId === flow.id"
                type="button"
                disabled
                class="inline-flex h-8 items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 text-xs font-medium text-emerald-700 opacity-50"
                title="Публикация…"
              >
                <UploadCloud class="h-3.5 w-3.5" />
                …
              </button>
              <button
                type="button"
                class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-red-200 bg-white text-red-600 transition-colors hover:bg-red-50"
                title="Удалить"
                @click="handleDelete(flow)"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { navigateTo, useRoute } from '#app'
import {
  AlertTriangle,
  Library,
  Link2,
  Loader2,
  Pencil,
  Plus,
  Search,
  Trash2,
  UploadCloud,
  Workflow,
} from 'lucide-vue-next'
import { useIntervalFn } from '@vueuse/core'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import { useAgentWebSocket } from '~/composables/useAgentWebSocket'
import { useScriptFlows } from '~/composables/useScriptFlows'
import { useToast } from '~/composables/useToast'
import type { ScriptFlow, ScriptFlowIndexStatus } from '~/types/scriptFlow'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})

const route = useRoute()
const agentId = route.params.id as string
const {
  flows,
  isLoading,
  error,
  fetchFlows,
  createFlow,
  deleteFlow,
  publishFlow,
} = useScriptFlows(agentId)
const { success: toastSuccess, error: toastError } = useToast()

const creating = ref(false)
const publishingId = ref<string | null>(null)
const searchQuery = ref('')

const publishedCount = computed(() =>
  flows.value.filter((f) => f.flow_status === 'published').length,
)

const isFlowIndexing = (flow: ScriptFlow) =>
  flow.index_status === 'pending' || flow.index_status === 'indexing'

const hasAnyFlowIndexing = computed(() =>
  flows.value.some((f) => f.index_status === 'pending' || f.index_status === 'indexing'),
)

const { isConnected } = useAgentWebSocket(computed(() => agentId), {
  onScriptFlowIndexUpdated: (data) => {
    if (data.agent_id !== agentId) return
    void fetchFlows()
  },
})

watch(isConnected, (connected, was) => {
  if (connected && was === false && hasAnyFlowIndexing.value)
    void fetchFlows()
})

/** Пока воркер крутит индексацию, периодически подтягиваем список — WS может быть недоступен за прокси. */
const { pause: pauseIndexPoll, resume: resumeIndexPoll } = useIntervalFn(
  () => {
    void fetchFlows()
  },
  10_000,
  { immediate: false },
)

watch(
  hasAnyFlowIndexing,
  (busy) => {
    if (busy)
      resumeIndexPoll()
    else
      pauseIndexPoll()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  pauseIndexPoll()
})

const filteredFlows = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return flows.value
  return flows.value.filter((f) => {
    const name = f.name.toLowerCase()
    const wr = flowWhenRelevant(f).toLowerCase()
    return name.includes(q) || wr.includes(q)
  })
})

const flowWhenRelevant = (flow: ScriptFlow): string => {
  const v = (flow.flow_metadata as Record<string, unknown> | undefined)?.when_relevant
  return typeof v === 'string' ? v : ''
}

const getFlowNodes = (flow: ScriptFlow): Array<Record<string, unknown>> => {
  const def = (flow.flow_definition || {}) as Record<string, unknown>
  const raw = def.nodes
  return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : []
}

const nodeCount = (flow: ScriptFlow): number => getFlowNodes(flow).length

const CONTENT_NODE_TYPES = new Set(['expertise', 'question', 'business_rule', 'end'])

const countKgLinksInData = (data: unknown): number => {
  if (!data || typeof data !== 'object') return 0
  const d = data as { kg_links?: Record<string, unknown> }
  const kg = d.kg_links
  if (!kg || typeof kg !== 'object') return 0
  let total = 0
  for (const key of ['motive_ids', 'argument_ids', 'proof_ids', 'objection_ids', 'constraint_ids']) {
    const arr = (kg as Record<string, unknown>)[key]
    if (Array.isArray(arr)) total += arr.length
  }
  if (typeof (kg as Record<string, unknown>).outcome_id === 'string'
    && (kg as Record<string, unknown>).outcome_id) total += 1
  return total
}

const kgLinkCount = (flow: ScriptFlow): number => {
  let total = 0
  for (const n of getFlowNodes(flow)) total += countKgLinksInData(n.data)
  return total
}

const unlinkedContentCount = (flow: ScriptFlow): number => {
  let total = 0
  for (const n of getFlowNodes(flow)) {
    const data = (n.data || {}) as Record<string, unknown>
    const nt = typeof data.node_type === 'string' ? data.node_type : ''
    if (!CONTENT_NODE_TYPES.has(nt)) continue
    if (countKgLinksInData(data) === 0) total += 1
  }
  return total
}

const indexBadge = (status: ScriptFlowIndexStatus) => {
  switch (status) {
    case 'indexed':
      return { label: 'В графе', className: 'border-indigo-200 bg-indigo-50 text-indigo-700' }
    case 'indexing':
    case 'pending':
      return { label: 'Индексация…', className: 'border-amber-200 bg-amber-50 text-amber-700' }
    case 'failed':
      return { label: 'Ошибка индекса', className: 'border-red-200 bg-red-50 text-red-700' }
    default:
      return null
  }
}

const openFlow = async (flowId: string) => {
  await navigateTo(`/agents/${agentId}/scripts/${flowId}?view=schema`)
}

const handleCreate = async () => {
  if (creating.value) return
  creating.value = true
  try {
    const name = `Поток ${new Date().toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })}`
    const created = await createFlow({
      name,
      flow_metadata: { when_relevant: '' },
      flow_definition: {},
    })
    await fetchFlows()
    toastSuccess('Поток создан')
    await navigateTo(`/agents/${agentId}/scripts/${created.id}?view=schema`)
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось создать поток')
  } finally {
    creating.value = false
  }
}

const handleDelete = async (flow: ScriptFlow) => {
  if (!confirm(`Удалить поток «${flow.name}»?`)) return
  try {
    await deleteFlow(flow.id)
    await fetchFlows()
    toastSuccess('Поток удалён')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось удалить поток')
  }
}

const handlePublish = async (flow: ScriptFlow) => {
  publishingId.value = flow.id
  try {
    await publishFlow(flow.id)
    await fetchFlows()
    toastSuccess('Поток опубликован — индексация поставлена в очередь')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось опубликовать поток')
  } finally {
    publishingId.value = null
  }
}

onMounted(() => {
  fetchFlows()
})
</script>
