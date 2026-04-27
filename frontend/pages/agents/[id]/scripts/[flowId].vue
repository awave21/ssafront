<template>
  <AgentPageShell
    :title="shellTitle"
    :hide-actions="true"
    :contained="true"
    :flush="true"
    :prevent-inner-scroll="true"
  >
    <div v-if="loadError" class="px-4 text-sm text-destructive">
      {{ loadError }}
      <button type="button" class="ml-2 underline" @click="goBack">Назад</button>
    </div>
    <div v-else-if="!flow" class="px-4 text-sm text-muted-foreground">Загрузка…</div>
    <div v-else class="flex min-h-0 flex-1 flex-col gap-2 px-4 pb-4 pt-3">

      <div
        v-if="saveError || saving || hasUnsavedChanges || lastSavedAt"
        class="flex shrink-0 items-center justify-end text-xs text-muted-foreground"
      >
        <span v-if="saveError" class="text-destructive">{{ saveError }}</span>
        <span v-else-if="saving">Сохранение черновика…</span>
        <span v-else-if="hasUnsavedChanges">Есть несохранённые изменения…</span>
        <span v-else class="text-muted-foreground">Черновик сохранён (Ctrl+S)</span>
      </div>
      <div class="relative min-h-0 flex-1 rounded-lg border border-border overflow-hidden bg-background">
        <ScriptFlowEditor
          ref="scriptFlowEditorRef"
          :revision="editorRevision"
          :flow-definition="flow.flow_definition || {}"
          :runtime-usage-by-node="toolUsageSnapshot?.by_node_id"
          :var-names="flowVarNames"
          :agent-functions="agentTools.filter(t => t.id).map(t => ({ id: t.id!, name: t.name, description: t.description }))"
          :flow-variables="(flow.flow_metadata as Record<string, unknown> | undefined)?.variables as Record<string, unknown> | undefined"
          :service-options="serviceOptions"
          :employee-options="employeeOptions"
          :kg-entity-options="kgEntityOptions"
          :view-mode="viewMode"
          @update:flow-definition="onFlowDefinitionUpdate"
          @update:flow-variables="onFlowVariablesUpdate"
          @update:view-mode="viewMode = $event"
          @request-immediate-persist="() => void flushPersistAwait()"
          @template-applied="onScriptFlowTemplateApplied"
        />
        <div
          v-if="sandboxOpen"
          class="absolute bottom-4 left-4 z-20"
        >
          <ScriptFlowSearchSandbox
            :agent-id="agentId"
            :flow-id="String(route.params.flowId)"
            :flow-name="flow?.name ?? null"
            @close="sandboxOpen = false"
          />
        </div>
        <div
          v-if="coverageOpen"
          class="absolute right-4 top-4 z-20"
        >
          <ScriptFlowCoverageMatrix
            :agent-id="agentId"
            :service-labels="serviceLabelMap"
            @close="coverageOpen = false"
          />
        </div>
      </div>
    </div>

    <Dialog :open="readinessOpen" @update:open="onReadinessDialogOpenChange">
      <DialogContent class="sm:max-w-lg max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Проверка перед публикацией</DialogTitle>
          <DialogDescription>
            Оценка полноты сценария общения и доступности его шагов для ассистента.
            Критические замечания блокируют публикацию.
          </DialogDescription>
        </DialogHeader>
        <div v-if="coverageLoading" class="py-8 text-center text-sm text-muted-foreground">Загрузка…</div>
        <div v-else-if="coverageSnapshot" class="min-h-0 flex-1 space-y-3 overflow-auto text-xs">
          <div class="flex flex-wrap items-center gap-2 text-muted-foreground">
            <span>Оценка: <strong class="text-foreground">{{ coverageSnapshot.score }}</strong></span>
            <span
              v-if="coverageRiskSummary"
              class="rounded-md border px-2 py-0.5 font-medium text-foreground"
              :class="readinessRiskChipClass"
            >
              {{ readinessRiskLabel }}
            </span>
            <span v-if="coverageSnapshot.stats">
              шагов {{ coverageSnapshot.stats.total_nodes }}, доступных ассистенту {{ coverageSnapshot.stats.searchable_nodes }}
            </span>
          </div>
          <p class="text-[11px] text-muted-foreground">
            Сначала непройденные проверки. Если замечание привязано к узлу — откройте его на схеме кнопкой ниже.
          </p>
          <ul class="space-y-2">
            <li
              v-for="c in readinessChecksOrdered"
              :key="c.key"
              class="rounded-md border px-2 py-2"
              :class="checkRowClass(c)"
            >
              <div class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span class="font-medium">{{ c.label }}</span>
                <span
                  v-if="!c.passed"
                  class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  {{ c.severity === 'critical' ? 'критично' : 'предупреждение' }}
                </span>
              </div>
              <div
                v-if="coverageCheckNodeId(c)"
                class="mt-2 flex flex-wrap items-center gap-2"
              >
                <span class="text-[11px] text-muted-foreground">
                  Узел «<span class="font-medium text-foreground">{{
                    flowDefinitionNodeTitle(
                      flow?.flow_definition as Record<string, unknown> | undefined,
                      coverageCheckNodeId(c)!,
                    ) || coverageCheckNodeId(c)
                  }}</span>»
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  class="h-7 px-2 text-[11px]"
                  type="button"
                  @click="openCheckOnCanvas(c)"
                >
                  На схеме
                </Button>
              </div>
              <div
                v-else-if="c.details && !coverageCheckNodeId(c)"
                class="mt-1 text-[11px] text-muted-foreground"
              >
                {{ c.details }}
              </div>
              <div
                v-else-if="!c.passed && !coverageCheckNodeId(c)"
                class="mt-1 text-[11px] italic text-muted-foreground"
              >
                Подробности не заданы для этой проверки на сервере — откройте таблицу покрытия на схеме.
              </div>
            </li>
          </ul>
        </div>
        <DialogFooter>
          <Button variant="secondary" @click="readinessOpen = false">Закрыть</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog :open="draftPreviewOpen" @update:open="(v: boolean) => { draftPreviewOpen = v }">
      <DialogContent class="sm:max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Текст для обучения ассистента</DialogTitle>
          <DialogDescription>
            Предпросмотр того, как черновая схема превратится в текст для памяти ассистента (без публикации).
          </DialogDescription>
        </DialogHeader>
        <div class="min-h-0 flex-1 overflow-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-[11px] whitespace-pre-wrap">
          <template v-if="draftPreviewLoading">Компиляция…</template>
          <template v-else>{{ draftPreviewText || '—' }}</template>
        </div>
        <DialogFooter>
          <Button variant="secondary" @click="draftPreviewOpen = false">Закрыть</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, provide, ref, toRaw, watch, watchEffect } from 'vue'
import { navigateTo, useRoute } from '#app'
import { useEventListener, useIntervalFn } from '@vueuse/core'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import ScriptFlowEditor from '~/components/agents/scripts/ScriptFlowEditor.vue'
import TacticLibraryView from '~/components/agents/scripts/TacticLibraryView.vue'
import ScriptFlowSearchSandbox from '~/components/agents/scripts/ScriptFlowSearchSandbox.vue'
import ScriptFlowCoverageMatrix from '~/components/agents/scripts/ScriptFlowCoverageMatrix.vue'
import { Button } from '~/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '~/components/ui/dialog'
import { useScriptFlows } from '~/composables/useScriptFlows'
import { useAgentWebSocket } from '~/composables/useAgentWebSocket'
import { useScriptFlowCoverageInline } from '~/composables/useScriptFlowCoverageInline'
import { useSqnsKnowledge } from '~/composables/useSqnsKnowledge'
import { useAgentKgEntities } from '~/composables/useAgentKgEntities'
import { useApiFetch } from '~/composables/useApiFetch'
import type { Tool } from '~/types/tool'
import { useLayoutState, type LayoutBreadcrumbSegment } from '~/composables/useLayoutState'
import type { ScriptFlow, ScriptFlowCoverageCheck, ScriptFlowCoverageResult, VariableBinding } from '~/types/scriptFlow'
import {
  TEMPLATE_MOTIVE_SEEDS,
  TEMPLATE_NODE_MOTIVE_BY_NODE_ID,
} from '~/constants/scriptFlowTemplateMotives'
import { coverageRiskBadgeLabel, summarizeCoverageRisk } from '~/utils/scriptFlowCoverageRisk'
import { coverageCheckNodeId, flowDefinitionNodeTitle } from '~/utils/scriptFlowCoverageNav'
import { useToast } from '~/composables/useToast'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})

const route = useRoute()
const agentId = route.params.id as string
const {
  flows,
  fetchFlows,
  getFlow,
  updateFlow,
  publishFlow,
  unpublishFlow,
  getFlowCoverage,
  compileDraft,
  retryFlowIndex,
  getFlowToolUsage,
} = useScriptFlows(agentId)
const {
  services,
  specialists,
  loadAll,
  updateSpecialistInfo,
  updateServiceDescription,
} = useSqnsKnowledge(agentId)
const {
  entities: kgEntities,
  fetchEntities: fetchKgEntities,
  createEntity: createKgEntity,
} = useAgentKgEntities(agentId)
const {
  layoutBreadcrumbSegments,
  breadcrumbBackPath,
  scriptFlowActionsVisible,
  scriptFlowSandboxOpen: sandboxOpen,
  scriptFlowCoverageOpen: coverageOpen,
  scriptFlowToolbarPayload,
} = useLayoutState()

const { error: toastError, success: toastSuccess } = useToast()
const apiFetch = useApiFetch()
const agentTools = ref<Tool[]>([])

/** Свести привязку к Tool: только активные / не удалённые. */
const normalizeBoundTool = (tool: Tool | null | undefined): Tool | null => {
  const id = String(tool?.id ?? '').trim()
  if (!id) return null
  if (tool?.is_deleted) return null
  if (tool?.status === 'deprecated') return null
  const st = tool?.status
  // Бэкенд отдаёт active; SQNS и старые записи могут не слать status — считаем активными
  if (st && st !== 'active' && st !== '') return null
  const merged = { ...tool, id } as Tool
  if (!merged.name?.trim()) merged.name = merged.description?.trim() ? merged.description.slice(0, 40) : id
  return merged
}

const dedupeToolsById = (list: Tool[]): Tool[] => {
  const seen = new Set<string>()
  return list.filter((t) => {
    const id = String(t.id ?? '')
    if (!id || seen.has(id)) return false
    seen.add(id)
    return true
  })
}

type SqnsStatusLite = {
  sqnsEnabled?: boolean
  sqnsTools?: Array<{
    name: string
    description?: string
    isEnabled?: boolean
  }>
}

const mapSqnsEnabledTools = (payload: SqnsStatusLite | null | undefined): Tool[] => {
  if (!payload?.sqnsEnabled) return []
  const tools = Array.isArray(payload.sqnsTools) ? payload.sqnsTools : []
  return tools
    .filter(t => t?.name && t.isEnabled)
    .map((t) => {
      const name = String(t.name).trim()
      return {
        id: name,
        name,
        description: String(t.description ?? '').trim(),
        endpoint: '',
        http_method: 'POST',
        execution_type: 'internal',
        auth_type: 'service',
        input_schema: { type: 'object', properties: {} },
        parameter_mapping: null,
        response_transform: null,
        status: 'active',
        is_deleted: false,
      } as Tool
    })
}

/**
 * Загрузка инструментов агента (те же данные, что вкладка «Функции»).
 * 1) /agents/.../tools/details — если tool в ответе пустой, догружаем GET /tools/{tool_id}
 * 2) при ошибке — как useFunctionsCrud: /agents/.../tools + параллельно /tools/{id}
 */
const fetchAgentTools = async () => {
  try {
    const [bindings, sqnsStatus] = await Promise.all([
      apiFetch<Array<{ tool?: Tool | null; tool_id: string }>>(`/agents/${agentId}/tools/details`),
      apiFetch<SqnsStatusLite>(`/agents/${agentId}/sqns`).catch(() => null),
    ])
    const boundTools = bindings
      .map(b => normalizeBoundTool(b.tool ?? null))
      .filter((x): x is Tool => x !== null)
    const sqnsTools = mapSqnsEnabledTools(sqnsStatus)
    const ok = dedupeToolsById([
      ...boundTools,
      ...sqnsTools,
    ])
    agentTools.value = ok
    return
  }
  catch (e) {
    console.warn('[script-flow] tools load failed', e)
    agentTools.value = []
  }
}

const flow = ref<ScriptFlow | null>(null)
const loadError = ref<string | null>(null)
const saveError = ref<string | null>(null)
const saving = ref(false)
const editorRevision = ref(0)

const viewModeFromQuery = (q: unknown): 'schema' | 'list' => {
  const s = Array.isArray(q) ? q[0] : q
  return s === 'list' ? 'list' : 'schema'
}
/** Канвас по умолчанию; с карточки списка — `?view=schema`; глубокая ссылка `?view=list` — список узлов. */
const viewMode = ref<'schema' | 'list'>(viewModeFromQuery(route.query.view))

watch(
  () => route.query.view,
  v => {
    viewMode.value = viewModeFromQuery(v)
  },
)

const publishing = ref(false)
const retrying = ref(false)

const readinessOpen = ref(false)
const coverageLoading = ref(false)
const coverageSnapshot = ref<ScriptFlowCoverageResult | null>(null)
const coverageRiskSummary = ref<ReturnType<typeof summarizeCoverageRisk> | null>(null)
const toolUsageSnapshot = ref<{
  approximate_flow_tool_calls: number
  days: number
  disclaimer?: string | null
  daily_series?: Array<{ date: string; count: number }>
  top_node_refs?: Array<{
    node_ref: string
    tactic_title?: string | null
    count: number
    last_invoked_at?: string | null
  }>
  by_node_id?: Record<string, {
    node_ref: string
    tactic_title?: string | null
    count: number
    last_invoked_at?: string | null
  }>
} | null>(null)

const lastSavedAt = ref<number | null>(null)
const lastPersistedDefinitionSignature = ref('')
const persistRequested = ref(false)
let persistPromise: Promise<void> | null = null

/** Редактор эмитит `flow_definition` с debounce — перед PATCH нужно дернуть flush (см. `flushPersistAwait`). */
const scriptFlowEditorRef = ref<{
  flushFlowDefinitionToParent?: () => void
  focusCanvasNode?: (id: string) => boolean
  applyTemplateKgLinks?: (templateId: string, motiveNameLcToId: Record<string, string>) => void
} | null>(null)

/** После загрузки шаблона — создать мотивы в библиотеке агента и привязать их к узлам шаблона. */
const onScriptFlowTemplateApplied = async ({ templateId }: { templateId: string }) => {
  const seeds = TEMPLATE_MOTIVE_SEEDS[templateId]
  if (!seeds?.length)
    return
  let created = 0
  let skipped = 0
  for (const s of seeds) {
    try {
      await createKgEntity({
        entity_type: 'motive',
        name: s.name,
        description: s.description,
      })
      created++
    }
    catch (e: unknown) {
      const err = e as { status?: number; statusCode?: number; data?: { error?: string } }
      const code = err.status ?? err.statusCode ?? 0
      const duplicate = code === 409 || err.data?.error === 'duplicate_name'
      if (duplicate)
        skipped++
      else
        console.warn('[script flow template motives]', s.name, e)
    }
  }
  await fetchKgEntities()
  const motiveNameLcToId: Record<string, string> = {}
  for (const e of kgEntities.value) {
    if (e.entity_type !== 'motive')
      continue
    motiveNameLcToId[e.name.trim().toLowerCase()] = e.id
  }
  scriptFlowEditorRef.value?.applyTemplateKgLinks?.(templateId, motiveNameLcToId)
  const hasBindings = Boolean(TEMPLATE_NODE_MOTIVE_BY_NODE_ID[templateId])
  if (created || skipped) {
    toastSuccess(
      'Мотивы в библиотеке',
      [
        `Новых записей: ${created}. Уже были в библиотеке: ${skipped}.`,
        hasBindings ? ' Связи с ключевыми узлами сценария добавлены, где имена совпали.' : '',
      ].join(''),
    )
  }
}

const draftPreviewOpen = ref(false)
const draftPreviewLoading = ref(false)
const draftPreviewText = ref('')

const catalogSpecialistMap = computed(() => {
  const acc: Record<string, { information?: string | null }> = {}
  for (const s of specialists.value)
    acc[s.id] = { information: s.information ?? null }
  return acc
})

const catalogServiceMap = computed(() => {
  const acc: Record<string, { description?: string | null }> = {}
  for (const s of services.value) {
    const row = s as typeof s & { description?: string | null }
    acc[s.id] = { description: row.description ?? null }
  }
  return acc
})

provide('catalogSpecialistMap', catalogSpecialistMap)
provide('catalogServiceMap', catalogServiceMap)
provide('sqnsPatchSpecialistProfile', updateSpecialistInfo)
provide('sqnsPatchServiceDescription', updateServiceDescription)

const { coverageInline, refreshCoverageInline } = useScriptFlowCoverageInline(
  () => route.params.flowId as string,
  flow,
  getFlowCoverage,
)

provide(
  'flowCoverageNodeIssues',
  computed(() => coverageInline.value?.node_issues ?? {}),
)

const gotoFlowOptions = computed(() => {
  const fid = route.params.flowId as string
  return flows.value
    .filter(f => f.id !== fid)
    .map(f => ({
      id: f.id,
      name: (f.name || '').trim() || f.id,
      flow_status: f.flow_status,
    }))
})
provide('scriptFlowGotoOptions', gotoFlowOptions)

const serviceLabelMap = computed<Record<string, string>>(() => {
  const acc: Record<string, string> = {}
  for (const s of services.value) acc[s.id] = s.name
  return acc
})

/** Заголовок вкладки / оболочки (имя сценария после загрузки). */
const shellTitle = computed(() => flow.value?.name || 'Сценарий общения')
const stringifyDefinition = (definition: Record<string, unknown> | null | undefined) => {
  try {
    return JSON.stringify(toRaw(definition ?? {}))
  } catch {
    return '{}'
  }
}

const cloneDefinition = (definition: Record<string, unknown> | null | undefined): Record<string, unknown> => {
  const source = toRaw(definition ?? {})
  if (typeof structuredClone === 'function') {
    try {
      return structuredClone(source)
    } catch {
      /* reactive/proxy object can fail structuredClone in browser */
    }
  }
  try {
    return JSON.parse(JSON.stringify(source)) as Record<string, unknown>
  } catch {
    return {}
  }
}

const currentDefinitionSignature = computed(() => stringifyDefinition(flow.value?.flow_definition as Record<string, unknown> | undefined))
const hasUnsavedChanges = computed(() =>
  Boolean(flow.value) && currentDefinitionSignature.value !== lastPersistedDefinitionSignature.value,
)

const rememberPersistedDefinition = (definition: Record<string, unknown> | null | undefined) => {
  lastPersistedDefinitionSignature.value = stringifyDefinition(definition)
}

const syncScriptFlowBreadcrumbs = () => {
  const listPath = `/agents/${agentId}/scripts`
  const segments: LayoutBreadcrumbSegment[] = [
    { label: 'Сценарии общения', action: { type: 'route', path: listPath } },
    {
      label: loadError.value
        ? 'Ошибка'
        : (flow.value?.name?.trim() || 'Загрузка…'),
      action: null,
    },
  ]
  layoutBreadcrumbSegments.value = segments
}

watch([flow, loadError], syncScriptFlowBreadcrumbs, { immediate: true })

const flowVarNames = computed(() => {
  const vars = (flow.value?.flow_metadata as Record<string, unknown> | undefined)?.variables
  if (!vars || typeof vars !== 'object') return []
  return Object.keys(vars as object)
})

const serviceOptions = computed(() =>
  services.value.map((s) => ({ id: s.id, name: s.name })),
)

const employeeOptions = computed(() =>
  specialists.value
    .filter((s) => s.active)
    .map((s) => ({ id: s.id, name: s.name, active: s.active })),
)

const kgEntityOptions = computed(() =>
  kgEntities.value.map((e) => ({
    id: e.id,
    name: e.name,
    description: e.description,
    entity_type: e.entity_type,
    meta: e.meta,
  })),
)

const checkRowClass = (c: ScriptFlowCoverageCheck) => {
  if (c.passed) return 'border-emerald-200 bg-emerald-50/80 dark:border-emerald-900/50 dark:bg-emerald-950/30'
  if (c.severity === 'critical') return 'border-destructive/50 bg-destructive/10'
  return 'border-amber-200 bg-amber-50/80 dark:border-amber-900/40 dark:bg-amber-950/25'
}

const readinessRiskLabel = computed(() =>
  coverageRiskSummary.value ? coverageRiskBadgeLabel(coverageRiskSummary.value) : '',
)

const readinessRiskChipClass = computed(() => {
  switch (coverageRiskSummary.value?.level) {
    case 'ok':
      return 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100'
    case 'warn':
      return 'border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950/45 dark:text-amber-50'
    case 'critical':
      return 'border-destructive/50 bg-destructive/15 text-destructive'
    default:
      return 'border-border'
  }
})

/** Непройденные проверки сверху — проще найти предупреждения в длинном списке. */
const readinessChecksOrdered = computed(() => {
  const checks = coverageSnapshot.value?.checks
  if (!checks?.length) return []
  return [...checks].sort((a, b) => {
    if (a.passed !== b.passed) return a.passed ? 1 : -1
    const pri = (s: string) => (s === 'critical' ? 0 : 1)
    const da = pri(a.severity)
    const db = pri(b.severity)
    if (da !== db) return da - db
    return a.label.localeCompare(b.label, 'ru')
  })
})

const onReadinessDialogOpenChange = (open: boolean) => {
  readinessOpen.value = open
  if (!open)
    coverageSnapshot.value = null
}

/** Закрыть диалог готовности, переключить на схему и выделить узел из проверки. */
const openCheckOnCanvas = async (c: ScriptFlowCoverageCheck) => {
  const nodeId = coverageCheckNodeId(c)
  if (!nodeId) return
  viewMode.value = 'schema'
  readinessOpen.value = false
  await nextTick()
  const ok = scriptFlowEditorRef.value?.focusCanvasNode?.(nodeId)
  if (!ok)
    toastError('Узел не найден на схеме — сохраните черновик или обновите страницу.')
}

const goBack = async () => {
  await navigateTo(`/agents/${agentId}/scripts`)
}

const refreshFlowMetrics = async (reuseCoverage?: ScriptFlowCoverageResult | null) => {
  const fid = route.params.flowId as string
  try {
    const usageP = getFlowToolUsage(fid, 7).catch(() => null)
    const covP = reuseCoverage != null
      ? Promise.resolve(reuseCoverage)
      : getFlowCoverage(fid).catch(() => null)
    const [usage, cov] = await Promise.all([usageP, covP])
    toolUsageSnapshot.value = usage
      ? {
          approximate_flow_tool_calls: usage.approximate_flow_tool_calls ?? 0,
          days: usage.days ?? 7,
          disclaimer: usage.disclaimer ?? null,
          daily_series: usage.daily_series as Array<{ date: string; count: number }> | undefined,
          top_node_refs: Array.isArray(usage.top_node_refs) ? usage.top_node_refs : undefined,
          by_node_id: usage.by_node_id && typeof usage.by_node_id === 'object'
            ? usage.by_node_id as Record<string, {
                node_ref: string
                tactic_title?: string | null
                count: number
                last_invoked_at?: string | null
              }>
            : undefined,
        }
      : null
    coverageRiskSummary.value = cov ? summarizeCoverageRisk(cov) : null
  }
  catch {
    toolUsageSnapshot.value = null
    coverageRiskSummary.value = null
  }
}

/** После отрисовки канваса (двойной rAF), чтобы не менять высоту панели в первом кадре. */
const scheduleFlowMetricsRefresh = () => {
  void nextTick(() => {
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          void refreshFlowMetrics()
        })
      })
    } else {
      void refreshFlowMetrics()
    }
  })
}

const loadFlow = async (opts: { keepCanvas?: boolean } = {}) => {
  const fid = route.params.flowId as string
  loadError.value = null
  if (!opts.keepCanvas)
    flow.value = null
  try {
    await Promise.all([loadAll(), fetchKgEntities(), fetchFlows(), fetchAgentTools()])
    const fresh = await getFlow(fid)
    flow.value = fresh
    rememberPersistedDefinition(fresh.flow_definition)
    if (!opts.keepCanvas)
      editorRevision.value += 1
    scheduleFlowMetricsRefresh()
    void refreshCoverageInline()
  } catch (e: unknown) {
    loadError.value = e instanceof Error ? e.message : 'Не удалось загрузить поток'
  }
}

const currentFlowId = computed(() => route.params.flowId as string)

const flowIndexInProgress = computed(() =>
  flow.value?.index_status === 'pending' || flow.value?.index_status === 'indexing',
)

const { isConnected } = useAgentWebSocket(computed(() => agentId), {
  onScriptFlowIndexUpdated: (data) => {
    if (data.agent_id !== agentId) return
    if (data.flow_id !== currentFlowId.value) return
    void loadFlow({ keepCanvas: true })
  },
})

watch(isConnected, (connected, was) => {
  if (connected && was === false && flowIndexInProgress.value)
    void loadFlow({ keepCanvas: true })
})

const { pause: pauseIndexPoll, resume: resumeIndexPoll } = useIntervalFn(
  () => {
    void loadFlow({ keepCanvas: true })
  },
  10_000,
  { immediate: false },
)

watch(
  flowIndexInProgress,
  (busy) => {
    if (busy)
      resumeIndexPoll()
    else
      pauseIndexPoll()
  },
  { immediate: true },
)

const persistFlowOnce = async () => {
  const fid = route.params.flowId as string
  if (!flow.value) return
  const snapshot = cloneDefinition(flow.value.flow_definition as Record<string, unknown> | undefined)
  const snapshotSignature = stringifyDefinition(snapshot)
  const baseVersion = flow.value.definition_version ?? 0
  saving.value = true
  saveError.value = null
  try {
    const updated = await updateFlow(
      fid,
      {
        flow_definition: snapshot,
      },
      { definitionVersion: baseVersion },
    )
    if (!flow.value) return
    const liveSignature = stringifyDefinition(flow.value.flow_definition as Record<string, unknown> | undefined)
    const isStillCurrentSnapshot = liveSignature === snapshotSignature

    if (isStillCurrentSnapshot) {
      flow.value = updated
      rememberPersistedDefinition(updated.flow_definition)
      lastSavedAt.value = Date.now()
    } else {
      // Пока PATCH выполнялся, пользователь успел поменять граф.
      // Не затираем новые локальные ноды старым server response; обновим только версию.
      flow.value = {
        ...flow.value,
        definition_version: updated.definition_version,
        updated_at: updated.updated_at,
      }
      persistRequested.value = true
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'Не удалось сохранить'
    saveError.value = msg
    if (/409|конфликт|conflict/i.test(msg))
      toastError('Версия потока устарела — обновите страницу.')
  } finally {
    saving.value = false
  }
}

const runPersistQueue = async (): Promise<void> => {
  if (persistPromise) return await persistPromise
  persistPromise = (async () => {
    while (persistRequested.value) {
      persistRequested.value = false
      await persistFlowOnce()
    }
  })().finally(() => {
    persistPromise = null
  })
  await persistPromise
}

const requestPersist = () => {
  persistRequested.value = true
  void runPersistQueue()
}

const requestPersistAndWait = async (): Promise<void> => {
  persistRequested.value = true
  await runPersistQueue()
}

let persistTimer: ReturnType<typeof setTimeout> | null = null

const schedulePersist = () => {
  if (persistTimer)
    clearTimeout(persistTimer)
  persistTimer = setTimeout(() => {
    persistTimer = null
    requestPersist()
  }, 900)
}

/** Сбросить таймер автосохранения и дождаться PATCH — нужно перед публикацией, иначе на сервере старая схема. */
const flushPersistAwait = async (): Promise<void> => {
  if (persistTimer) {
    clearTimeout(persistTimer)
    persistTimer = null
  }
  scriptFlowEditorRef.value?.flushFlowDefinitionToParent?.()
  await nextTick()
  await requestPersistAndWait()
}

const flushPersist = () => {
  void flushPersistAwait()
}

useEventListener(document, 'visibilitychange', () => {
  if (document.visibilityState === 'hidden')
    flushPersist()
})

useEventListener(window, 'keydown', (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    const t = e.target as HTMLElement | null
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable))
      return
    e.preventDefault()
    flushPersist()
  }
})

useEventListener(window, 'beforeunload', () => {
  if (persistTimer) {
    clearTimeout(persistTimer)
    persistTimer = null
  }
  scriptFlowEditorRef.value?.flushFlowDefinitionToParent?.()
  requestPersist()
})

const onFlowDefinitionUpdate = (def: Record<string, unknown>) => {
  if (!flow.value) return
  flow.value = { ...flow.value, flow_definition: def }
  saveError.value = null
  schedulePersist()
}

const onFlowVariablesUpdate = (vars: Record<string, unknown>) => {
  if (!flow.value) return
  const meta = {
    ...(flow.value.flow_metadata as Record<string, unknown> | undefined ?? {}),
    variables: vars as Record<string, VariableBinding>,
  }
  flow.value = { ...flow.value, flow_metadata: meta }
  saveError.value = null
  schedulePersist()
}

const fetchCoverageForDialog = async () => {
  const fid = route.params.flowId as string
  coverageLoading.value = true
  coverageSnapshot.value = null
  try {
    const cov = await getFlowCoverage(fid)
    coverageSnapshot.value = cov
    coverageRiskSummary.value = summarizeCoverageRisk(cov)
  } finally {
    coverageLoading.value = false
  }
}

const onReadinessClick = async () => {
  readinessOpen.value = true
  await fetchCoverageForDialog()
}

const onDraftPreviewClick = async () => {
  if (!flow.value) return
  scriptFlowEditorRef.value?.flushFlowDefinitionToParent?.()
  await nextTick()
  draftPreviewOpen.value = true
  draftPreviewLoading.value = true
  draftPreviewText.value = ''
  const fid = route.params.flowId as string
  try {
    const res = await compileDraft(fid, {
      flow_definition: flow.value.flow_definition,
      flow_metadata: flow.value.flow_metadata as Record<string, unknown> | undefined,
    })
    draftPreviewText.value = res.compiled_text ?? ''
  } catch (e: unknown) {
    draftPreviewText.value = e instanceof Error ? e.message : 'Не удалось скомпилировать черновик'
  } finally {
    draftPreviewLoading.value = false
  }
}

const onRetryIndex = async () => {
  const fid = route.params.flowId as string
  retrying.value = true
  saveError.value = null
  try {
    await retryFlowIndex(fid)
    await loadFlow()
  } catch (e: unknown) {
    saveError.value = e instanceof Error ? e.message : 'Не удалось повторить индексацию'
  } finally {
    retrying.value = false
  }
}

const onPublishClick = async () => {
  const fid = route.params.flowId as string
  publishing.value = true
  saveError.value = null
  try {
    await flushPersistAwait()
    if (saveError.value)
      return

    const cov = await getFlowCoverage(fid)
    coverageSnapshot.value = cov
    coverageRiskSummary.value = summarizeCoverageRisk(cov)
    const criticalFailed = cov.checks.filter((c) => !c.passed && c.severity === 'critical')
    if (criticalFailed.length) {
      readinessOpen.value = true
      saveError.value = 'Есть критические проверки — исправьте или откройте «Готовность».'
      return
    }
    await publishFlow(fid)
    await loadFlow({ keepCanvas: true })
    // После успешной публикации показать список предупреждений (иначе заметен только счётчик в шапке).
    if (coverageRiskSummary.value?.level === 'warn')
      readinessOpen.value = true
  } catch (e: unknown) {
    saveError.value = e instanceof Error ? e.message : 'Не удалось опубликовать'
  } finally {
    publishing.value = false
  }
}

const onUnpublishClick = async () => {
  const fid = route.params.flowId as string
  if (!flow.value) return
  publishing.value = true
  saveError.value = null
  try {
    await unpublishFlow(fid)
    await loadFlow({ keepCanvas: true })
  } catch (e: unknown) {
    saveError.value = e instanceof Error ? e.message : 'Не удалось снять с публикации'
  } finally {
    publishing.value = false
  }
}

watchEffect(() => {
  if (!flow.value) {
    scriptFlowToolbarPayload.value = null
    return
  }
  scriptFlowToolbarPayload.value = {
    flow: flow.value,
    publishing: publishing.value,
    retrying: retrying.value,
    riskSummary: coverageRiskSummary.value,
    toolUsage: toolUsageSnapshot.value,
    onPublish: onPublishClick,
    onUnpublish: onUnpublishClick,
    onReadiness: onReadinessClick,
    onDraftPreview: onDraftPreviewClick,
    onRetryIndex: onRetryIndex,
  }
})

onMounted(() => {
  scriptFlowActionsVisible.value = true
  breadcrumbBackPath.value = null
  sandboxOpen.value = false
  coverageOpen.value = false
  loadFlow()
})

onUnmounted(() => {
  pauseIndexPoll()
  scriptFlowToolbarPayload.value = null
  scriptFlowActionsVisible.value = false
  breadcrumbBackPath.value = null
  layoutBreadcrumbSegments.value = null
  sandboxOpen.value = false
  coverageOpen.value = false
})

watch(
  () => route.params.flowId,
  () => {
    loadFlow()
  },
)
</script>
