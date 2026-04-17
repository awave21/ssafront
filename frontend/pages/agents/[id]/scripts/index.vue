<template>
  <AgentPageShell title="Потоки эксперта" :hide-actions="true" :contained="true">
    <div class="flex min-h-0 flex-1 gap-4">
      <aside class="w-[320px] shrink-0 rounded-lg border border-border bg-card p-3">
        <div class="mb-3 flex items-center justify-between gap-2">
          <p class="text-sm font-semibold">Знания агента</p>
          <button
            type="button"
            class="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            :disabled="creating"
            @click="handleCreate()"
          >
            + Поток
          </button>
        </div>

        <div class="mb-3 grid grid-cols-2 gap-2">
          <button
            v-for="tab in tabs"
            :key="tab.value"
            type="button"
            class="rounded-md border px-2 py-1.5 text-xs"
            :class="activeTab === tab.value ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'"
            @click="activeTab = tab.value"
          >
            {{ tab.label }}
          </button>
        </div>

        <div class="mb-2 text-xs text-muted-foreground">
          Потоки: {{ flows.length }} · Услуги: {{ services.length }} · Сотрудники: {{ specialists.length }}
        </div>

        <div class="max-h-[70vh] space-y-1 overflow-auto pr-1">
          <button
            v-for="item in listItems"
            :key="`${item.type}:${item.id}`"
            type="button"
            class="w-full rounded-md border px-3 py-2 text-left"
            :class="isSelected(item) ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/40'"
            @click="selectItem(item)"
          >
            <div class="truncate text-sm font-medium">{{ item.title }}</div>
            <div class="truncate text-xs text-muted-foreground">{{ item.subtitle }}</div>
          </button>
          <div
            v-if="!listItems.length"
            class="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground"
          >
            Ничего не найдено для выбранного фильтра.
          </div>
        </div>
      </aside>

      <section class="min-w-0 flex-1 rounded-lg border border-border bg-card p-4">
        <div v-if="isBusy" class="text-sm text-muted-foreground">Загрузка…</div>
        <div v-else-if="combinedError" class="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm">
          {{ combinedError }}
          <button type="button" class="ml-2 underline" @click="reloadAll">Повторить</button>
        </div>

        <template v-else-if="selectedItem?.type === 'flow' && selectedFlow">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 class="text-base font-semibold">{{ selectedFlow.name }}</h3>
              <p class="text-xs text-muted-foreground">
                {{ selectedFlow.flow_status === 'published' ? 'Опубликован' : 'Черновик' }}
                · Индекс: {{ indexLabel(selectedFlow.index_status) }}
              </p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <button class="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted" @click="openFlow(selectedFlow.id)">
                Редактировать
              </button>
              <button
                class="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
                :disabled="publishing || hasCoverageBlockers"
                @click="handlePublish(selectedFlow.id)"
              >
                Опубликовать
              </button>
              <button
                class="rounded-md border border-destructive/40 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10"
                @click="handleDelete(selectedFlow)"
              >
                Удалить
              </button>
            </div>
          </div>

          <div class="mb-4 rounded-md border border-border p-3 text-sm">
            <p class="mb-1 text-xs uppercase text-muted-foreground">Когда релевантно</p>
            <p>{{ flowWhenRelevant(selectedFlow) || 'Не заполнено' }}</p>
          </div>

          <div class="mb-4 rounded-md border border-border p-3">
            <div class="mb-2 flex items-center justify-between gap-2">
              <p class="text-sm font-medium">Покрытие сценария</p>
              <span class="text-xs text-muted-foreground">Score: {{ flowCoverage?.score ?? 0 }}%</span>
            </div>
            <div v-if="coverageLoading" class="text-sm text-muted-foreground">Проверка покрытия…</div>
            <div v-else-if="coverageError" class="text-sm text-destructive">{{ coverageError }}</div>
            <div v-else-if="flowCoverage" class="space-y-2">
              <div
                v-for="check in flowCoverage.checks"
                :key="check.key"
                class="rounded-md border p-2"
                :class="check.passed ? 'border-emerald-200 bg-emerald-50/40' : 'border-amber-200 bg-amber-50/40'"
              >
                <p class="text-sm">
                  <span class="mr-1">{{ check.passed ? '✓' : '⚠' }}</span>
                  {{ check.label }}
                </p>
                <p v-if="check.details" class="mt-1 text-xs text-muted-foreground">{{ check.details }}</p>
              </div>
              <p v-if="hasCoverageBlockers" class="text-xs text-amber-700">
                Есть критические пункты. Рекомендуется исправить перед публикацией.
              </p>
            </div>
          </div>

          <div class="rounded-md border border-border p-3">
            <p class="mb-2 text-sm font-medium">Тест запроса</p>
            <div class="flex flex-wrap items-center gap-2">
              <input
                v-model="testQuery"
                type="text"
                class="min-w-[240px] flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
                placeholder="Например: клиент говорит, что дорого"
                @keydown.enter.prevent="runTestSearch"
              >
              <button
                type="button"
                class="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
                :disabled="testLoading || !testQuery.trim()"
                @click="runTestSearch"
              >
                Проверить
              </button>
            </div>

            <div v-if="testError" class="mt-2 text-sm text-destructive">{{ testError }}</div>
            <div v-if="testResults.length" class="mt-3 space-y-2">
              <div v-for="match in testResults" :key="match.node_id" class="rounded-md border border-border p-2">
                <div class="flex items-center justify-between gap-2">
                  <p class="text-sm font-medium">{{ match.flow_name }} · {{ match.node_type }}</p>
                  <span class="text-xs text-muted-foreground">score {{ match.score.toFixed(3) }}</span>
                </div>
                <p class="mt-1 text-sm">{{ match.situation }}</p>
                <p v-if="match.good_question" class="mt-1 text-xs text-muted-foreground">
                  Вопрос: {{ match.good_question }}
                </p>
              </div>
            </div>
          </div>
        </template>

        <template v-else-if="selectedItem?.type === 'service' && selectedService">
          <div class="mb-4">
            <h3 class="text-base font-semibold">{{ selectedService.name }}</h3>
            <p class="text-xs text-muted-foreground">
              {{ selectedService.category || 'Без категории' }}
              · {{ formatDuration(selectedService.duration_seconds) }}
              · {{ selectedService.price ?? 'цена не указана' }}
            </p>
          </div>

          <div class="mb-4 rounded-md border border-border p-3">
            <div class="mb-2 flex items-center justify-between">
              <p class="text-sm font-medium">Как говорить (потоки)</p>
              <button
                type="button"
                class="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
                :disabled="creating"
                @click="handleCreate(selectedService.name)"
              >
                Создать поток
              </button>
            </div>
            <div v-if="!relatedFlowsForService.length" class="text-sm text-muted-foreground">
              Потоки не найдены. Создайте первый сценарий для этой услуги.
            </div>
            <ul v-else class="space-y-2">
              <li v-for="flow in relatedFlowsForService" :key="flow.id" class="rounded-md border border-border p-2">
                <button type="button" class="text-sm font-medium hover:underline" @click="selectFlow(flow.id)">
                  {{ flow.name }}
                </button>
                <p class="text-xs text-muted-foreground">{{ flowWhenRelevant(flow) || 'when_relevant не заполнено' }}</p>
              </li>
            </ul>
          </div>

          <div class="rounded-md border border-border p-3">
            <p class="mb-2 text-sm font-medium">Сотрудники услуги</p>
            <ul v-if="employeesForService.length" class="space-y-1">
              <li v-for="employee in employeesForService" :key="employee" class="text-sm">{{ employee }}</li>
            </ul>
            <p v-else class="text-sm text-muted-foreground">Нет связей сотрудник-услуга.</p>
          </div>
        </template>

        <template v-else-if="selectedItem?.type === 'employee' && selectedSpecialist">
          <div class="mb-4">
            <h3 class="text-base font-semibold">{{ selectedSpecialist.name }}</h3>
            <p class="text-xs text-muted-foreground">
              {{ selectedSpecialist.role || 'Специализация не указана' }}
            </p>
          </div>

          <div class="mb-4 rounded-md border border-border p-3">
            <p class="mb-2 text-sm font-medium">Информация для агента</p>
            <textarea
              v-model="specialistInfoDraft"
              rows="4"
              class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              placeholder="Например: принимает вт/чт, специализация по ботоксу, противопоказания..."
            />
            <div class="mt-2 flex justify-end">
              <button
                type="button"
                class="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
                :disabled="savingSpecialist"
                @click="saveSpecialistInfo"
              >
                Сохранить
              </button>
            </div>
          </div>

          <div class="rounded-md border border-border p-3">
            <p class="mb-2 text-sm font-medium">Потоки по сотруднику</p>
            <ul v-if="relatedFlowsForSpecialist.length" class="space-y-2">
              <li v-for="flow in relatedFlowsForSpecialist" :key="flow.id" class="rounded-md border border-border p-2">
                <button type="button" class="text-sm font-medium hover:underline" @click="selectFlow(flow.id)">
                  {{ flow.name }}
                </button>
                <p class="text-xs text-muted-foreground">{{ flowWhenRelevant(flow) || 'when_relevant не заполнено' }}</p>
              </li>
            </ul>
            <p v-else class="text-sm text-muted-foreground">Для этого сотрудника пока нет сценариев.</p>
          </div>
        </template>

        <div v-else class="text-sm text-muted-foreground">
          Выберите элемент слева, чтобы открыть карточку.
        </div>
      </section>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from '#app'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import { useScriptFlows } from '~/composables/useScriptFlows'
import { useSqnsKnowledge } from '~/composables/useSqnsKnowledge'
import { useToast } from '~/composables/useToast'
import type {
  ScriptFlow,
  ScriptFlowCoverageResult,
  ScriptFlowSearchTestMatch,
} from '~/types/scriptFlow'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})

type DashboardItem =
  | { type: 'flow'; id: string; title: string; subtitle: string }
  | { type: 'service'; id: string; title: string; subtitle: string }
  | { type: 'employee'; id: string; title: string; subtitle: string }

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
  testSearch,
  getFlowCoverage,
} = useScriptFlows(agentId)
const {
  services,
  specialists,
  serviceEmployeeLinks,
  isLoading: sqnsLoading,
  error: sqnsError,
  loadAll,
  updateSpecialistInfo,
} = useSqnsKnowledge(agentId)
const { success: toastSuccess, error: toastError } = useToast()

const creating = ref(false)
const publishing = ref(false)
const savingSpecialist = ref(false)

const activeTab = ref<'all' | 'flows' | 'services' | 'employees'>('all')
const tabs = [
  { value: 'all', label: 'ВСЁ' },
  { value: 'flows', label: 'Потоки' },
  { value: 'services', label: 'Услуги' },
  { value: 'employees', label: 'Сотрудники' },
] as const

const selectedItem = ref<DashboardItem | null>(null)

const testQuery = ref('')
const testLoading = ref(false)
const testError = ref<string | null>(null)
const testResults = ref<ScriptFlowSearchTestMatch[]>([])
const flowCoverage = ref<ScriptFlowCoverageResult | null>(null)
const coverageLoading = ref(false)
const coverageError = ref<string | null>(null)

const specialistInfoDraft = ref('')

const isBusy = computed(() => isLoading.value || sqnsLoading.value)
const combinedError = computed(() => error.value || sqnsError.value)
const activeSpecialists = computed(() => specialists.value.filter((s) => s.active))

const flowWhenRelevant = (flow: ScriptFlow) => {
  const v = (flow.flow_metadata as Record<string, unknown> | undefined)?.when_relevant
  return typeof v === 'string' ? v : ''
}

const getNodeBindings = (flow: ScriptFlow) => {
  const definition = (flow.flow_definition || {}) as Record<string, unknown>
  const nodes = Array.isArray(definition.nodes) ? definition.nodes : []
  const serviceIds = new Set<string>()
  const employeeIds = new Set<string>()
  for (const n of nodes) {
    if (!n || typeof n !== 'object') continue
    const data = (n as { data?: unknown }).data
    if (!data || typeof data !== 'object') continue
    const d = data as { service_ids?: unknown; employee_ids?: unknown }
    if (Array.isArray(d.service_ids))
      d.service_ids.forEach((id) => typeof id === 'string' && id && serviceIds.add(id))
    if (Array.isArray(d.employee_ids))
      d.employee_ids.forEach((id) => typeof id === 'string' && id && employeeIds.add(id))
  }
  return { serviceIds, employeeIds }
}

const indexLabel = (s: string) => {
  const m: Record<string, string> = {
    idle: 'не запускался',
    pending: 'в очереди',
    indexing: 'индексация',
    indexed: 'готово',
    failed: 'ошибка',
  }
  return m[s] || s
}

const formatDuration = (seconds: number) => {
  const mins = Math.round((seconds || 0) / 60)
  return `${mins} мин`
}

const listItems = computed<DashboardItem[]>(() => {
  const flowItems: DashboardItem[] = flows.value.map((f) => ({
    type: 'flow',
    id: f.id,
    title: f.name,
    subtitle: `${f.flow_status === 'published' ? 'Опубликован' : 'Черновик'} · ${indexLabel(f.index_status)}`,
  }))
  const serviceItems: DashboardItem[] = services.value.map((s) => ({
    type: 'service',
    id: s.id,
    title: s.name,
    subtitle: `${s.category || 'Без категории'} · ${formatDuration(s.duration_seconds)}`,
  }))
  const employeeItems: DashboardItem[] = activeSpecialists.value.map((s) => ({
    type: 'employee',
    id: s.id,
    title: s.name,
    subtitle: s.role || 'Специализация не указана',
  }))

  if (activeTab.value === 'flows') return flowItems
  if (activeTab.value === 'services') return serviceItems
  if (activeTab.value === 'employees') return employeeItems
  return [...flowItems, ...serviceItems, ...employeeItems]
})

const selectedFlow = computed(() => (
  selectedItem.value?.type === 'flow'
    ? flows.value.find((f) => f.id === selectedItem.value?.id) || null
    : null
))

const selectedService = computed(() => (
  selectedItem.value?.type === 'service'
    ? services.value.find((s) => s.id === selectedItem.value?.id) || null
    : null
))

const selectedSpecialist = computed(() => (
  selectedItem.value?.type === 'employee'
    ? activeSpecialists.value.find((s) => s.id === selectedItem.value?.id) || null
    : null
))

const hasCoverageBlockers = computed(() => Boolean(
  flowCoverage.value?.checks?.some((c) => !c.passed && c.severity === 'critical'),
))

const relatedFlowsForService = computed(() => {
  if (!selectedService.value) return []
  const needle = selectedService.value.name.toLowerCase()
  return flows.value.filter((f) => {
    const bindings = getNodeBindings(f)
    if (bindings.serviceIds.has(selectedService.value!.id)) return true
    const wr = flowWhenRelevant(f).toLowerCase()
    const name = f.name.toLowerCase()
    return wr.includes(needle) || name.includes(needle)
  })
})

const relatedFlowsForSpecialist = computed(() => {
  if (!selectedSpecialist.value) return []
  const needle = selectedSpecialist.value.name.toLowerCase()
  return flows.value.filter((f) => {
    const bindings = getNodeBindings(f)
    if (bindings.employeeIds.has(selectedSpecialist.value!.id)) return true
    const wr = flowWhenRelevant(f).toLowerCase()
    const name = f.name.toLowerCase()
    return wr.includes(needle) || name.includes(needle)
  })
})

const employeesForService = computed(() => {
  if (!selectedService.value) return []
  const serviceName = selectedService.value.name.toLowerCase()
  return serviceEmployeeLinks.value
    .filter((row) => row.service?.toLowerCase() === serviceName && row.employee)
    .map((row) => row.employee as string)
})

const isSelected = (item: DashboardItem) =>
  selectedItem.value?.type === item.type && selectedItem.value?.id === item.id

const selectItem = (item: DashboardItem) => {
  selectedItem.value = item
}

const selectFlow = (flowId: string) => {
  const flow = flows.value.find((f) => f.id === flowId)
  if (!flow) return
  selectedItem.value = {
    type: 'flow',
    id: flow.id,
    title: flow.name,
    subtitle: `${flow.flow_status} · ${indexLabel(flow.index_status)}`,
  }
}

const openFlow = async (flowId: string) => {
  await navigateTo(`/agents/${agentId}/scripts/${flowId}`)
}

const handleCreate = async (whenRelevant = '') => {
  creating.value = true
  try {
    const name = whenRelevant
      ? `Поток: ${whenRelevant}`
      : `Поток ${new Date().toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })}`
    const created = await createFlow({
      name,
      flow_metadata: { when_relevant: whenRelevant },
      flow_definition: {},
    })
    await fetchFlows()
    selectFlow(created.id)
    toastSuccess('Поток создан')
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
    if (selectedItem.value?.type === 'flow' && selectedItem.value.id === flow.id)
      selectedItem.value = null
    toastSuccess('Поток удалён')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось удалить поток')
  }
}

const handlePublish = async (flowId: string) => {
  publishing.value = true
  try {
    await publishFlow(flowId)
    await fetchFlows()
    toastSuccess('Поток опубликован')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось опубликовать поток')
  } finally {
    publishing.value = false
  }
}

const loadCoverage = async (flowId: string) => {
  coverageLoading.value = true
  coverageError.value = null
  try {
    flowCoverage.value = await getFlowCoverage(flowId)
  } catch (err: unknown) {
    coverageError.value = err instanceof Error ? err.message : 'Не удалось загрузить покрытие'
    flowCoverage.value = null
  } finally {
    coverageLoading.value = false
  }
}

const runTestSearch = async () => {
  const query = testQuery.value.trim()
  if (!query) return
  testLoading.value = true
  testError.value = null
  try {
    const res = await testSearch(query)
    const currentFlowId = selectedFlow.value?.id
    testResults.value = currentFlowId
      ? res.matches.filter((m) => m.flow_id === currentFlowId)
      : res.matches
  } catch (err: unknown) {
    testError.value = err instanceof Error ? err.message : 'Не удалось выполнить тест запроса'
    testResults.value = []
  } finally {
    testLoading.value = false
  }
}

const saveSpecialistInfo = async () => {
  if (!selectedSpecialist.value) return
  savingSpecialist.value = true
  try {
    await updateSpecialistInfo(selectedSpecialist.value.id, specialistInfoDraft.value.trim())
    toastSuccess('Информация сотрудника сохранена')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось сохранить информацию')
  } finally {
    savingSpecialist.value = false
  }
}

const reloadAll = async () => {
  await Promise.all([fetchFlows(), loadAll()])
}

watch(selectedSpecialist, (value) => {
  specialistInfoDraft.value = value?.information || ''
})

watch(selectedFlow, (flow) => {
  if (!flow) {
    flowCoverage.value = null
    coverageError.value = null
    return
  }
  loadCoverage(flow.id)
})

watch(listItems, (items) => {
  if (!selectedItem.value && items.length) selectedItem.value = items[0]
}, { immediate: true })

onMounted(async () => {
  await reloadAll()
})
</script>
