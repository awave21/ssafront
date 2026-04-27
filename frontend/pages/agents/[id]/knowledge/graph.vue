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
        <div v-if="d3Preview?.nodes?.length" class="flex min-h-0 flex-1 flex-col">
          <UnifiedGraphD3View
            :data="d3Preview"
            :height-px="graphCanvasHeightPx"
            :bottom-badges="graphMetaBadges"
            :selected-graph-node-id="selectedNode?.graph_node_id ?? null"
            layout-mode="balanced"
            :show-isolated-nodes="true"
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
import UnifiedGraphNodeDetailPanel from '~/components/agents/unified-graph/UnifiedGraphNodeDetailPanel.vue'
import UnifiedGraphAskWidget from '~/components/agents/unified-graph/UnifiedGraphAskWidget.vue'
import { useApiFetch } from '~/composables/useApiFetch'
import { useLayoutState } from '~/composables/useLayoutState'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { UnifiedGraphNodeDto, UnifiedGraphPreview, UnifiedGraphRelationDto } from '~/types/unifiedGraph'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})

type GraphPreviewResponse = {
  tenant_id: string
  agent_id: string
  nodes: Array<{ id: string; label: string; type: string; description: string }>
  relations: Array<{ id: string; source: string; target: string; label: string }>
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

const rebuildBusy = ref(false)
const rebuildElapsedSec = ref(0)
const previewLoading = ref(false)
const previewDone = ref(false)
const message = ref('')
const error = ref(false)
const preview = ref<GraphPreviewResponse | null>(null)

const GRAPHRAG_REBUILD_TIMEOUT_MS = 3_700_000

let rebuildTickTimer: ReturnType<typeof setInterval> | null = null

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

const GRAPHRAG_ORIGIN = 'knowledge'

const selectedNode = ref<UnifiedGraphNodeDto | null>(null)
const d3Preview = computed((): UnifiedGraphPreview | null => {
  const nodes = graphNodes.value
  if (!nodes.length) return null
  const mappedNodes: UnifiedGraphNodeDto[] = nodes.map((n) => ({
    graph_node_id: n.id,
    origin_slice: GRAPHRAG_ORIGIN,
    entity_type: n.type || 'entity',
    title: n.label || n.id,
    description: n.description || null,
    domain_entity_id: null,
    properties: {},
    provenance_tier: null,
  }))
  const mappedRelations: UnifiedGraphRelationDto[] = graphRelations.value.map((r) => ({
    source_graph_node_id: r.source,
    target_graph_node_id: r.target,
    relation_type: (r.label || 'связь').trim().slice(0, 200) || 'связь',
    weight: null,
    origin_slice: GRAPHRAG_ORIGIN,
    properties: {},
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

const startRebuildTimer = () => {
  if (rebuildTickTimer) clearInterval(rebuildTickTimer)
  rebuildElapsedSec.value = 0
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

const rebuild = async () => {
  if (!agentId.value) return
  rebuildBusy.value = true
  error.value = false
  message.value = 'Идёт пересборка на сервере (запрос ждёт конца индексации). Обычно минуты, иногда до часа — см. таймер на кнопке.'
  startRebuildTimer()
  try {
    const res = await apiFetch<{ status: string; message?: string }>(
      `/agents/${agentId.value}/unified-graph/rebuild`,
      {
        method: 'POST',
        timeout: GRAPHRAG_REBUILD_TIMEOUT_MS,
        body: { active_sqns_only: true },
      },
    )
    const tail = res.message && res.message !== 'ok' ? ` ${res.message}` : ''
    message.value =
      res.status === 'accepted'
        ? `Готово за ${rebuildElapsedLabel.value}.${tail} Отображение обновлено ниже.`
        : JSON.stringify(res)
    await loadPreview()
  }
  catch (e: unknown) {
    error.value = true
    message.value = getReadableErrorMessage(
      e,
      'Пересборка не завершилась (ошибка или обрыв по таймауту сети/прокси). Проверьте логи сервера.',
    )
    await loadPreview()
  }
  finally {
    stopRebuildTimer()
    rebuildBusy.value = false
  }
}

watch(agentId, () => {
  selectedNode.value = null
  void loadPreview()
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
})

onUnmounted(() => {
  stopRebuildTimer()
  resetKnowledgeGraphHeaderState()
})
</script>
