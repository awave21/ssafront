<template>
  <AgentPageShell title="Граф знаний" :hide-actions="true" :contained="false">
    <div class="flex flex-col gap-4 px-1 pb-4 pt-1 sm:px-2">
      <p
        v-if="preview?.preview_legend"
        class="border-l-2 border-muted-foreground/30 pl-2 text-xs leading-relaxed text-muted-foreground"
      >
        {{ preview.preview_legend }}
      </p>
      <div
        v-if="message"
        class="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm"
        :class="error ? 'text-destructive' : 'text-foreground'"
      >
        {{ message }}
      </div>
      <div
        v-if="graphNodes.length || previewMetaLine"
        class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
      >
        <span v-if="previewMetaLine">{{ previewMetaLine }}</span>
      </div>
      <ClientOnly>
        <div v-if="d3Preview?.nodes?.length" class="flex flex-col gap-3">
          <UnifiedGraphD3View
            :data="d3Preview"
            :height-px="560"
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
      <div class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          :disabled="rebuildBusy"
          @click="rebuild"
        >
          {{ rebuildBusy ? `Пересборка… ${rebuildElapsedLabel}` : 'Пересобрать граф' }}
        </button>
        <button
          type="button"
          class="inline-flex items-center rounded-md border border-border bg-background px-3 py-2 text-xs font-medium hover:bg-muted/60 disabled:opacity-50"
          :disabled="previewLoading || rebuildBusy"
          title="Только перечитать output с диска"
          @click="loadPreview"
        >
          {{ previewLoading ? 'Загрузка…' : 'Обновить отображение' }}
        </button>
      </div>
      <ClientOnly>
        <UnifiedGraphAskWidget v-if="agentId" :agent-id="agentId" />
      </ClientOnly>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import UnifiedGraphD3View from '~/components/agents/unified-graph/UnifiedGraphD3View.vue'
import UnifiedGraphNodeDetailPanel from '~/components/agents/unified-graph/UnifiedGraphNodeDetailPanel.vue'
import UnifiedGraphAskWidget from '~/components/agents/unified-graph/UnifiedGraphAskWidget.vue'
import { useApiFetch } from '~/composables/useApiFetch'
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

const previewMetaLine = computed(() => {
  const p = preview.value
  if (!p || p.preview_source === 'no_workspace') return ''
  const parts: string[] = []
  if (typeof p.node_count === 'number') parts.push(`сущностей в индексе: ${p.node_count}`)
  if (typeof p.edge_count === 'number') parts.push(`связей на графе: ${p.edge_count}`)
  if (p.truncated) parts.push('показано частично (лимит узлов/рёбер)')
  return parts.join(' · ')
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

onMounted(() => {
  void loadPreview()
})

onUnmounted(() => {
  stopRebuildTimer()
})
</script>
