<template>
  <AgentPageShell title="Граф знаний" :hide-actions="true" :contained="true" :flush="true">
    <div class="flex h-full min-h-0 flex-col">
      <div
        v-if="message"
        class="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm"
        :class="error ? 'text-destructive' : 'text-foreground'"
      >
        {{ message }}
      </div>
      <ClientOnly>
        <div v-if="d3Preview?.nodes?.length" class="relative flex min-h-0 flex-1 flex-col">
          <div
            class="pointer-events-auto absolute right-2 top-2 z-10 flex items-center overflow-hidden rounded-md border border-border bg-background/95 text-[11px] shadow-sm"
          >
            <button
              type="button"
              class="px-2 py-1 transition-colors"
              :class="viewMode === 'force' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'"
              @click="setViewMode('force')"
            >
              Force
            </button>
            <button
              type="button"
              class="border-l border-border px-2 py-1 transition-colors"
              :class="viewMode === 'd3' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'"
              @click="setViewMode('d3')"
            >
              D3
            </button>
          </div>
          <div
            v-if="Object.keys(typeCounts).length"
            class="pointer-events-auto absolute left-2 top-2 z-10 max-w-[min(100%-7rem,52rem)] rounded-md border border-border bg-background/95 p-1.5 shadow-sm"
          >
            <UnifiedGraphTypeChips
              :counts="typeCounts"
              :selected="visibleTypes"
              @toggle="onTypeToggle"
              @reset="onTypeReset"
            />
          </div>
          <button
            v-if="semanticEdgeCount > 0"
            type="button"
            class="pointer-events-auto absolute right-2 top-12 z-10 inline-flex items-center gap-1.5 rounded-md border bg-background/95 px-2 py-1 text-[11px] shadow-sm transition-colors"
            :class="
              structuredEdgesOnly
                ? 'border-primary bg-primary/10 text-foreground'
                : 'border-border text-muted-foreground hover:bg-muted'
            "
            :title="
              structuredEdgesOnly
                ? `Скрыто ${semanticEdgeCount} семантических связей. Кликнуть, чтобы показать.`
                : `Показать только проверенные связи (скрыть ${semanticEdgeCount} семантических).`
            "
            @click="setStructuredEdgesOnly(!structuredEdgesOnly)"
          >
            <span
              class="h-1.5 w-1.5 rounded-full"
              :class="structuredEdgesOnly ? 'bg-primary' : 'bg-muted-foreground/50'"
            />
            Только проверенные
          </button>
          <UnifiedGraphForceView
            v-if="viewMode === 'force'"
            :data="d3Preview"
            :height-px="graphCanvasHeightPx"
            :bottom-badges="graphMetaBadges"
            :selected-graph-node-id="selectedNode?.graph_node_id ?? null"
            layout-mode="balanced"
            :show-isolated-nodes="true"
            :visible-types="visibleTypes"
            :structured-edges-only="structuredEdgesOnly"
            @node-select="onNodeSelect"
          />
          <UnifiedGraphD3View
            v-else
            :data="d3Preview"
            :height-px="graphCanvasHeightPx"
            :bottom-badges="graphMetaBadges"
            :selected-graph-node-id="selectedNode?.graph_node_id ?? null"
            layout-mode="balanced"
            :show-isolated-nodes="true"
            :visible-types="visibleTypes"
            @node-select="onNodeSelect"
          />
          <UnifiedGraphNodeDetailPanel
            :node="selectedNode"
            :preview="d3Preview"
            @close="selectedNode = null"
            @select-node="selectedNode = $event"
          />
        </div>
        <div
          v-else-if="previewDone && !previewLoading"
          class="flex min-h-[220px] items-center justify-center rounded-lg border border-dashed border-border px-4 text-center text-sm text-muted-foreground"
        >
          {{ emptyGraphHint }}
        </div>
        <div
          v-else-if="previewLoading"
          class="flex min-h-[220px] items-center justify-center rounded-lg border border-border bg-muted/10 text-sm text-muted-foreground"
        >
          Загрузка графа…
        </div>
      </ClientOnly>
      <ClientOnly>
        <UnifiedGraphAskWidget v-if="agentId" :agent-id="agentId" />
      </ClientOnly>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useWindowSize } from '@vueuse/core'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import UnifiedGraphD3View from '~/components/agents/unified-graph/UnifiedGraphD3View.vue'
import UnifiedGraphForceView from '~/components/agents/unified-graph/UnifiedGraphForceView.vue'
import UnifiedGraphNodeDetailPanel from '~/components/agents/unified-graph/UnifiedGraphNodeDetailPanel.vue'
import UnifiedGraphTypeChips from '~/components/agents/unified-graph/UnifiedGraphTypeChips.vue'
import UnifiedGraphAskWidget from '~/components/agents/unified-graph/UnifiedGraphAskWidget.vue'
import { useApiFetch } from '~/composables/useApiFetch'
import { useLayoutState } from '~/composables/useLayoutState'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type {
  UnifiedGraphNodeDto,
  UnifiedGraphPreview,
  UnifiedGraphRelationDto,
  UnifiedGraphRebuildJob,
  UnifiedGraphRebuildStartResponse,
  UnifiedGraphRebuildStatusResponse,
} from '~/types/unifiedGraph'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})

type GraphPreviewNode = {
  id: string
  label: string
  type: string
  description: string
  origin_slice?: string | null
  provenance_tier?: string | null
}

type GraphPreviewRelation = {
  id: string
  source: string
  target: string
  label: string
  origin_slice?: string | null
  provenance_tier?: string | null
  weight?: number | null
}

type GraphPreviewResponse = {
  tenant_id: string
  agent_id: string
  nodes: GraphPreviewNode[]
  relations: GraphPreviewRelation[]
  preview_source: string
  preview_error: string | null
  message: string | null
  node_count?: number
  edge_count?: number
  truncated?: boolean
  preview_legend?: string | null
}

const route = useRoute()
const agentId = computed(() => String(route.params.id || ''))
const apiFetch = useApiFetch()
const { height: windowHeight } = useWindowSize()
const {
  knowledgeGraphRebuildAction,
  knowledgeGraphRefreshAction,
  knowledgeGraphRebuildBusy,
  knowledgeGraphRefreshBusy,
  knowledgeGraphRebuildLabel,
  layoutBreadcrumbSegments,
  resetKnowledgeGraphHeaderState,
} = useLayoutState()

const visibleTypes = ref<string[] | null>(null)
const typeCounts = computed<Record<string, number>>(() => {
  const out: Record<string, number> = {}
  const nodes = d3Preview.value?.nodes ?? []
  for (const n of nodes) {
    const t = n.entity_type || 'entity'
    out[t] = (out[t] ?? 0) + 1
  }
  return out
})
const onTypeToggle = (type: string) => {
  const current = new Set(visibleTypes.value ?? Object.keys(typeCounts.value))
  if (current.has(type) && current.size === 1) {
    visibleTypes.value = null
    return
  }
  if (visibleTypes.value === null) {
    visibleTypes.value = [type]
    return
  }
  if (current.has(type)) current.delete(type)
  else current.add(type)
  visibleTypes.value = current.size === 0 ? null : Array.from(current)
}
const onTypeReset = () => {
  visibleTypes.value = null
}

const STRUCTURED_ONLY_STORAGE_KEY = 'unifiedGraph.structuredOnly'
const structuredEdgesOnly = ref(false)
const setStructuredEdgesOnly = (v: boolean) => {
  structuredEdgesOnly.value = v
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(STRUCTURED_ONLY_STORAGE_KEY, v ? '1' : '0')
    }
    catch {
      // ignore
    }
  }
}
const semanticEdgeCount = computed(() => {
  const rels = preview.value?.relations ?? []
  return rels.filter((r) => r.provenance_tier === 'semantic').length
})

type GraphViewMode = 'force' | 'd3'
const VIEW_MODE_STORAGE_KEY = 'unifiedGraph.viewMode'
const viewMode = ref<GraphViewMode>('force')
const setViewMode = (mode: GraphViewMode) => {
  viewMode.value = mode
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(VIEW_MODE_STORAGE_KEY, mode)
    }
    catch {
      // ignore storage errors (private mode, quota)
    }
  }
}

const rebuildBusy = ref(false)
const rebuildElapsedSec = ref(0)
const previewLoading = ref(false)
const previewDone = ref(false)
const message = ref('')
const error = ref(false)
const preview = ref<GraphPreviewResponse | null>(null)

let rebuildTickTimer: ReturnType<typeof setInterval> | null = null
let rebuildPollTimer: ReturnType<typeof setTimeout> | null = null

const REBUILD_POLL_INTERVAL_MS = 3000

const rebuildElapsedLabel = computed(() => {
  const s = rebuildElapsedSec.value
  const m = Math.floor(s / 60)
  const r = s % 60
  return m > 0 ? `${m}:${String(r).padStart(2, '0')}` : `${r} с`
})

const TOP_BAR_HEIGHT_PX = 60
const graphCanvasHeightPx = computed(() =>
  Math.max(420, windowHeight.value - TOP_BAR_HEIGHT_PX),
)

const graphNodes = computed(() => preview.value?.nodes ?? [])
const graphRelations = computed(() => preview.value?.relations ?? [])

const selectedNode = ref<UnifiedGraphNodeDto | null>(null)
const d3Preview = computed((): UnifiedGraphPreview | null => {
  const nodes = graphNodes.value
  if (!nodes.length) return null
  const mappedNodes: UnifiedGraphNodeDto[] = nodes.map((n) => ({
    graph_node_id: n.id,
    origin_slice: (n.origin_slice || 'knowledge').toLowerCase(),
    entity_type: (n.type || 'entity').toLowerCase(),
    title: n.label || n.id,
    description: n.description || null,
    domain_entity_id: null,
    properties: {},
    provenance_tier: n.provenance_tier ?? null,
  }))
  const mappedRelations: UnifiedGraphRelationDto[] = graphRelations.value.map((r) => ({
    source_graph_node_id: r.source,
    target_graph_node_id: r.target,
    relation_type: (r.label || 'связь').trim().slice(0, 200) || 'связь',
    weight: r.weight ?? null,
    origin_slice: (r.origin_slice || 'knowledge').toLowerCase(),
    properties: {},
    provenance_tier: r.provenance_tier ?? null,
  }))
  return { nodes: mappedNodes, relations: mappedRelations }
})

const onNodeSelect = (node: UnifiedGraphNodeDto | null) => {
  selectedNode.value = node
}

const graphMetaBadges = computed(() => {
  const p = preview.value
  if (!p || p.preview_source === 'no_workspace') return [] as string[]
  const parts: string[] = []
  if (typeof p.node_count === 'number') parts.push(`сущностей в индексе: ${p.node_count}`)
  if (typeof p.edge_count === 'number') parts.push(`связей на графе: ${p.edge_count}`)
  if (p.truncated) parts.push('показано частично (лимит узлов/рёбер)')
  return parts
})

const emptyGraphHint = computed(() => {
  const p = preview.value
  if (p?.preview_error) return p.preview_error
  if (p?.message) return p.message
  return 'Нет данных для графа. Настройте индексацию GraphRAG и нажмите «Пересобрать граф».'
})

const rebuildStatusText = (job: UnifiedGraphRebuildJob): string => {
  switch (job.status) {
    case 'queued':
      return 'Пересборка в очереди на запуск.'
    case 'running':
      return 'Идёт пересборка графа на сервере.'
    case 'succeeded':
      return 'Пересборка графа завершена.'
    case 'failed':
      return 'Пересборка графа завершилась с ошибкой.'
    default:
      return 'Статус пересборки обновляется.'
  }
}

const rebuildStageText = (job: UnifiedGraphRebuildJob): string => {
  switch (job.stage) {
    case 'queued':
      return 'Ожидание запуска.'
    case 'dispatching':
      return 'Подготовка и отправка корпуса.'
    case 'indexing':
      return 'Индексация GraphRAG и синхронизация в Neo4j.'
    case 'done':
      return 'Готово.'
    case 'failed':
      return 'Ошибка выполнения.'
    default:
      return ''
  }
}

const startRebuildTimer = (reset = true) => {
  if (rebuildTickTimer) clearInterval(rebuildTickTimer)
  if (reset) rebuildElapsedSec.value = 0
  rebuildTickTimer = setInterval(() => {
    rebuildElapsedSec.value += 1
  }, 1000)
}

const stopRebuildTimer = () => {
  if (rebuildTickTimer) {
    clearInterval(rebuildTickTimer)
    rebuildTickTimer = null
  }
}

const stopRebuildPolling = () => {
  if (rebuildPollTimer) {
    clearTimeout(rebuildPollTimer)
    rebuildPollTimer = null
  }
}

const syncElapsedFromJob = (job: UnifiedGraphRebuildJob) => {
  if (!job.started_at) {
    rebuildElapsedSec.value = 0
    return
  }
  const startedAtMs = Date.parse(job.started_at)
  if (Number.isNaN(startedAtMs)) {
    rebuildElapsedSec.value = 0
    return
  }
  rebuildElapsedSec.value = Math.max(0, Math.floor((Date.now() - startedAtMs) / 1000))
}

const loadPreview = async () => {
  if (!agentId.value) return
  previewLoading.value = true
  try {
    const data = await apiFetch<GraphPreviewResponse>(`/agents/${agentId.value}/unified-graph/preview`)
    preview.value = data
  }
  catch (e: unknown) {
    preview.value = {
      tenant_id: '',
      agent_id: agentId.value,
      nodes: [],
      relations: [],
      preview_source: 'error',
      preview_error: getReadableErrorMessage(e, 'Не удалось загрузить граф'),
      message: null,
    }
  }
  finally {
    previewLoading.value = false
    previewDone.value = true
  }
}

const applyRebuildJobState = (job: UnifiedGraphRebuildJob | null) => {
  if (!job) {
    rebuildBusy.value = false
    stopRebuildTimer()
    return
  }

  const active = job.status === 'queued' || job.status === 'running'
  rebuildBusy.value = active
  if (active) {
    syncElapsedFromJob(job)
    if (!rebuildTickTimer) startRebuildTimer(false)
    error.value = false
    const statusText = rebuildStatusText(job)
    const stageText = rebuildStageText(job)
    const progressText = Number.isFinite(job.progress_pct) ? ` ${job.progress_pct}%` : ''
    message.value = `${statusText}${progressText ? ` ${progressText}.` : ''}${stageText ? ` ${stageText}` : ''} Таймер показывает длительность ожидания.`
    return
  }

  rebuildBusy.value = false
  stopRebuildTimer()
  if (job.status === 'succeeded') {
    error.value = false
    const tail = job.message && job.message !== 'ok' ? ` ${job.message}` : ''
    message.value = `Готово за ${rebuildElapsedLabel.value}.${tail} Отображение обновлено ниже.`
    return
  }

  error.value = true
  message.value = job.error_message || 'Пересборка графа завершилась с ошибкой. Проверьте логи сервера.'
}

const pollRebuildJob = async (jobId: string, opts?: { refreshPreviewOnFinish?: boolean }) => {
  if (!agentId.value) return
  stopRebuildPolling()
  try {
    const res = await apiFetch<UnifiedGraphRebuildStatusResponse>(
      `/agents/${agentId.value}/unified-graph/rebuild-jobs/${jobId}`,
    )
    applyRebuildJobState(res.job)

    if (res.job && (res.job.status === 'queued' || res.job.status === 'running')) {
      rebuildPollTimer = setTimeout(() => {
        void pollRebuildJob(jobId, opts)
      }, REBUILD_POLL_INTERVAL_MS)
      return
    }

    if (opts?.refreshPreviewOnFinish) {
      await loadPreview()
    }
  }
  catch (e: unknown) {
    error.value = true
    rebuildBusy.value = false
    stopRebuildTimer()
    stopRebuildPolling()
    message.value = getReadableErrorMessage(
      e,
      'Не удалось получить статус пересборки графа. Проверьте состояние сервера и попробуйте обновить страницу.',
    )
  }
}

const loadRebuildStatus = async () => {
  if (!agentId.value) return
  stopRebuildPolling()
  try {
    const res = await apiFetch<UnifiedGraphRebuildStatusResponse>(
      `/agents/${agentId.value}/unified-graph/rebuild-status`,
    )
    if (res.job && (res.job.status === 'queued' || res.job.status === 'running')) {
      applyRebuildJobState(res.job)
      rebuildPollTimer = setTimeout(() => {
        void pollRebuildJob(res.job!.id)
      }, REBUILD_POLL_INTERVAL_MS)
      return
    }
    rebuildBusy.value = false
    stopRebuildTimer()
  }
  catch {
    // Не шумим при обычной загрузке страницы: rebuild-status вспомогательный.
  }
}

const rebuild = async () => {
  if (!agentId.value) return
  error.value = false
  stopRebuildPolling()
  startRebuildTimer(true)
  rebuildBusy.value = true
  message.value = 'Запускаем пересборку графа…'
  try {
    const res = await apiFetch<UnifiedGraphRebuildStartResponse>(
      `/agents/${agentId.value}/unified-graph/rebuild`,
      {
        method: 'POST',
        body: { active_sqns_only: true },
      },
    )
    applyRebuildJobState(res.job)
    if (res.message) {
      message.value = `${res.message} ${rebuildStatusText(res.job)} ${rebuildStageText(res.job)}`.trim()
    }
    await pollRebuildJob(res.job.id, { refreshPreviewOnFinish: true })
  }
  catch (e: unknown) {
    error.value = true
    rebuildBusy.value = false
    stopRebuildTimer()
    message.value = getReadableErrorMessage(
      e,
      'Не удалось запустить пересборку графа. Проверьте состояние сервера и попробуйте снова.',
    )
  }
}

watch(agentId, () => {
  selectedNode.value = null
  stopRebuildTimer()
  stopRebuildPolling()
  rebuildBusy.value = false
  message.value = ''
  error.value = false
  void loadPreview()
  void loadRebuildStatus()
})

watch(preview, () => {
  selectedNode.value = null
})

watch([rebuildBusy, rebuildElapsedLabel], () => {
  knowledgeGraphRebuildBusy.value = rebuildBusy.value
  knowledgeGraphRebuildLabel.value = rebuildBusy.value
    ? `Пересборка… ${rebuildElapsedLabel.value}`
    : 'Пересобрать граф'
})

watch([previewLoading, rebuildBusy], () => {
  knowledgeGraphRefreshBusy.value = previewLoading.value || rebuildBusy.value
})

onMounted(() => {
  if (typeof window !== 'undefined') {
    try {
      const saved = window.localStorage.getItem(VIEW_MODE_STORAGE_KEY)
      if (saved === 'd3' || saved === 'force') viewMode.value = saved
      const onlyStructured = window.localStorage.getItem(STRUCTURED_ONLY_STORAGE_KEY)
      if (onlyStructured === '1') structuredEdgesOnly.value = true
    }
    catch {
      // ignore
    }
  }
  // На графе используем обычный title в top bar, без крошек из соседних страниц БЗ.
  layoutBreadcrumbSegments.value = null
  knowledgeGraphRebuildAction.value = () => {
    void rebuild()
  }
  knowledgeGraphRefreshAction.value = () => {
    void loadPreview()
  }
  knowledgeGraphRebuildBusy.value = rebuildBusy.value
  knowledgeGraphRefreshBusy.value = previewLoading.value || rebuildBusy.value
  knowledgeGraphRebuildLabel.value = rebuildBusy.value
    ? `Пересборка… ${rebuildElapsedLabel.value}`
    : 'Пересобрать граф'
  void loadPreview()
  void loadRebuildStatus()
})

onUnmounted(() => {
  stopRebuildTimer()
  stopRebuildPolling()
  resetKnowledgeGraphHeaderState()
})
</script>
