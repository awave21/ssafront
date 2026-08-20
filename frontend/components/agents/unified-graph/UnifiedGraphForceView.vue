<template>
  <div
    ref="containerRef"
    class="relative w-full overflow-hidden bg-muted/20"
    :style="{ height: `${canvasH}px` }"
  >
    <div ref="canvasHostRef" class="absolute inset-0" />
    <div
      v-if="hint"
      class="pointer-events-none absolute left-2 max-w-[min(100%-1rem,24rem)] rounded-md border border-border bg-background/95 px-2 py-1.5 text-[10px] leading-snug text-muted-foreground shadow-sm"
      :class="props.bottomBadges?.length ? 'bottom-12' : 'bottom-2'"
    >
      {{ hint }}
    </div>
    <div
      v-if="props.bottomBadges?.length"
      class="pointer-events-none absolute bottom-2 left-2 flex max-w-[min(100%-1rem,42rem)] flex-wrap gap-1.5"
    >
      <span
        v-for="badge in props.bottomBadges"
        :key="badge"
        class="rounded-md border border-border bg-background/95 px-2 py-1 text-[10px] leading-none text-muted-foreground shadow-sm"
      >
        {{ badge }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { UnifiedGraphNodeDto, UnifiedGraphPreview } from '../../../types/unifiedGraph'
import { colorForOrigin, colorForType } from './colors'
import { formatRelation } from './relationLabels'

type ForceNode = UnifiedGraphNodeDto & { x?: number; y?: number; vx?: number; vy?: number }
type ForceLink = {
  source: string | ForceNode
  target: string | ForceNode
  relation_type: string
  origin_slice?: string | null
  provenance_tier?: string | null
}

const HTML_TAG_RE = /<[^>]+>/g
const toPlainText = (value: string | null | undefined) => {
  if (!value) return ''
  return value.replace(HTML_TAG_RE, ' ').replace(/\s+/g, ' ').trim()
}

const props = withDefaults(
  defineProps<{
    data: UnifiedGraphPreview | null
    heightPx?: number
    selectedGraphNodeId?: string | null
    layoutMode?: 'compact' | 'balanced' | 'spread'
    showIsolatedNodes?: boolean
    bottomBadges?: string[]
    /** Если задан — отрисовывать только узлы этих типов (и связанные с ними рёбра). null = все. */
    visibleTypes?: string[] | null
    /** Если true — скрывать рёбра с provenance_tier='semantic' (показывать только проверенные). */
    structuredEdgesOnly?: boolean
  }>(),
  {
    heightPx: 560,
    selectedGraphNodeId: null,
    layoutMode: 'balanced',
    showIsolatedNodes: false,
    bottomBadges: () => [],
    visibleTypes: null,
    structuredEdgesOnly: false,
  },
)

const emit = defineEmits<{
  (e: 'nodeSelect', node: UnifiedGraphNodeDto | null): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const canvasHostRef = ref<HTMLDivElement | null>(null)
const hint = ref('')
const canvasH = computed(() => props.heightPx ?? 560)

let graph: any = null
let ro: ResizeObserver | null = null
const adjacency = new Map<string, Set<string>>()
let hoveredId: string | null = null
let hoveredLink: ForceLink | null = null

const toPlainNode = (n: ForceNode): UnifiedGraphNodeDto => ({
  graph_node_id: n.graph_node_id,
  origin_slice: n.origin_slice,
  entity_type: n.entity_type,
  title: n.title,
  description: n.description,
  domain_entity_id: n.domain_entity_id ?? null,
  properties: n.properties && typeof n.properties === 'object' ? n.properties : {},
  provenance_tier: n.provenance_tier ?? null,
})

const nodeRadius = (deg: number, maxDeg: number): number => {
  const norm = Math.sqrt(Math.max(0, deg) / Math.max(1, maxDeg))
  return 4 + 10 * norm
}

const layoutForces = (mode: 'compact' | 'balanced' | 'spread') => {
  if (mode === 'compact') return { charge: -80, linkDistance: 30 }
  if (mode === 'spread') return { charge: -500, linkDistance: 120 }
  return { charge: -200, linkDistance: 60 }
}

const getNodeId = (ref: string | ForceNode): string =>
  typeof ref === 'string' ? ref : ref.graph_node_id

const buildAdjacency = (links: ForceLink[]) => {
  adjacency.clear()
  for (const l of links) {
    const s = getNodeId(l.source)
    const t = getNodeId(l.target)
    if (!adjacency.has(s)) adjacency.set(s, new Set())
    if (!adjacency.has(t)) adjacency.set(t, new Set())
    adjacency.get(s)!.add(t)
    adjacency.get(t)!.add(s)
  }
}

const isHighlighted = (id: string): boolean => {
  const focus = hoveredId ?? props.selectedGraphNodeId
  if (!focus) return true
  if (id === focus) return true
  return adjacency.get(focus)?.has(id) ?? false
}

const isLinkHighlighted = (link: ForceLink): boolean => {
  const focus = hoveredId ?? props.selectedGraphNodeId
  if (!focus) return true
  return getNodeId(link.source) === focus || getNodeId(link.target) === focus
}

const withAlpha = (hex: string, alpha: number): string => {
  if (hex.startsWith('rgba') || hex.startsWith('rgb')) return hex
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const r = parseInt(full.slice(0, 2), 16)
  const g = parseInt(full.slice(2, 4), 16)
  const b = parseInt(full.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

const clearHost = () => {
  const host = canvasHostRef.value
  if (!host) return
  while (host.firstChild) host.removeChild(host.firstChild)
}

const teardown = () => {
  if (graph) {
    try {
      graph.pauseAnimation?.()
      graph._destructor?.()
    }
    catch {
      // ignore
    }
    graph = null
  }
  clearHost()
}

const draw = async () => {
  const host = canvasHostRef.value
  const container = containerRef.value
  if (!host || !container) return

  hint.value = ''

  const linksRaw = props.data?.relations ?? []
  const rawNodes = props.data?.nodes ?? []

  if (!rawNodes.length) {
    teardown()
    return
  }

  const typeFilter = props.visibleTypes && props.visibleTypes.length
    ? new Set(props.visibleTypes)
    : null
  const allNodes = typeFilter
    ? rawNodes.filter((n) => typeFilter.has(n.entity_type))
    : rawNodes
  const allowedIds = new Set(allNodes.map((n) => n.graph_node_id))

  const degree = new Map<string, number>()
  for (const n of allNodes) degree.set(n.graph_node_id, 0)
  for (const r of linksRaw) {
    if (!allowedIds.has(r.source_graph_node_id) || !allowedIds.has(r.target_graph_node_id)) continue
    degree.set(r.source_graph_node_id, (degree.get(r.source_graph_node_id) ?? 0) + 1)
    degree.set(r.target_graph_node_id, (degree.get(r.target_graph_node_id) ?? 0) + 1)
  }

  const nodes: ForceNode[] = (props.showIsolatedNodes
    ? allNodes
    : allNodes.filter((n) => (degree.get(n.graph_node_id) ?? 0) > 0)
  ).map((n) => ({ ...n }))

  if (!nodes.length) {
    teardown()
    hint.value =
      'Все узлы без связей. Включите «Показать узлы без связей», чтобы отобразить их.'
    return
  }

  const visibleIds = new Set(nodes.map((n) => n.graph_node_id))
  const links: ForceLink[] = linksRaw
    .filter((r) => visibleIds.has(r.source_graph_node_id) && visibleIds.has(r.target_graph_node_id))
    .filter((r) => {
      if (!props.structuredEdgesOnly) return true
      // Если включён фильтр «только проверенные» — пропускаем семантические рёбра.
      const tier = (r as { provenance_tier?: string | null }).provenance_tier
      return tier !== 'semantic'
    })
    .map((r) => ({
      source: r.source_graph_node_id,
      target: r.target_graph_node_id,
      relation_type: r.relation_type,
      origin_slice: r.origin_slice ?? null,
      provenance_tier: (r as { provenance_tier?: string | null }).provenance_tier ?? null,
    }))
  buildAdjacency(links)

  const maxDeg = Math.max(1, ...nodes.map((n) => degree.get(n.graph_node_id) ?? 0))
  const cfg = layoutForces(props.layoutMode ?? 'balanced')
  const width = Math.max(container.clientWidth || 640, 320)
  const height = canvasH.value

  if (!graph) {
    const mod = await import('force-graph')
    const ForceGraph = (mod as any).default ?? (mod as any).ForceGraph ?? mod
    graph = new ForceGraph(host)
    graph
      .backgroundColor('rgba(0,0,0,0)')
      .nodeId('graph_node_id')
      .nodeRelSize(4)
      .linkDirectionalArrowLength(6)
      .linkDirectionalArrowRelPos(1)
      .linkCurvature(0.1)
      .linkWidth((l: ForceLink) => {
        const isSemantic = l.provenance_tier === 'semantic'
        const base = isLinkHighlighted(l) ? 1.5 : 0.6
        return isSemantic ? base * 0.7 : base
      })
      .linkLineDash((l: ForceLink) => {
        // Семантические рёбра — пунктир, чтобы отличить от структурных.
        return l.provenance_tier === 'semantic' ? [3, 3] : null
      })
      .linkColor((l: ForceLink) => {
        const base = colorForOrigin(l.origin_slice ?? null)
        const isSemantic = l.provenance_tier === 'semantic'
        const dimmed = isSemantic ? 0.4 : 1.0
        if (isLinkHighlighted(l)) return isSemantic ? withAlpha(base, 0.55) : base
        return withAlpha(base, 0.18 * dimmed)
      })
      .linkDirectionalArrowColor((l: ForceLink) => {
        const base = colorForOrigin(l.origin_slice ?? null)
        const isSemantic = l.provenance_tier === 'semantic'
        const dimmed = isSemantic ? 0.4 : 1.0
        if (isLinkHighlighted(l)) return isSemantic ? withAlpha(base, 0.55) : base
        return withAlpha(base, 0.18 * dimmed)
      })
      .nodeCanvasObject((node: ForceNode, ctx: CanvasRenderingContext2D, scale: number) => {
        const deg = degree.get(node.graph_node_id) ?? 0
        const r = nodeRadius(deg, maxDeg)
        const color = colorForType(node.entity_type) || colorForOrigin(node.origin_slice)
        const highlighted = isHighlighted(node.graph_node_id)
        const isSelected = props.selectedGraphNodeId === node.graph_node_id
        const isHovered = hoveredId === node.graph_node_id

        ctx.beginPath()
        ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI)
        ctx.fillStyle = highlighted ? color : withAlpha(color, 0.18)
        ctx.fill()
        if (isSelected || isHovered) {
          ctx.lineWidth = 2.5 / scale
          ctx.strokeStyle = isSelected ? '#0ea5e9' : '#f8fafc'
          ctx.stroke()
        }
        else if (highlighted) {
          ctx.lineWidth = 1 / scale
          ctx.strokeStyle = withAlpha(color, 0.6)
          ctx.stroke()
        }

        if ((scale >= 1.2 && highlighted) || isHovered || isSelected) {
          const label = toPlainText(node.title) || node.graph_node_id
          const trimmed = label.length > 40 ? label.slice(0, 40) + '…' : label
          const fontSize = Math.max(10 / scale, 2)
          ctx.font = `${fontSize}px ui-sans-serif, system-ui, sans-serif`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'top'
          const labelColor = isSelected ? '#0ea5e9' : isHovered ? '#0f172a' : 'rgba(148,163,184,0.95)'
          // draw text shadow for legibility on any background
          ctx.fillStyle = 'rgba(255,255,255,0.75)'
          ctx.fillText(trimmed, (node.x ?? 0) + 0.5, (node.y ?? 0) + r + 2.5)
          ctx.fillStyle = labelColor
          ctx.fillText(trimmed, node.x ?? 0, (node.y ?? 0) + r + 2)
        }
      })
      .nodePointerAreaPaint((node: ForceNode, color: string, ctx: CanvasRenderingContext2D) => {
        const deg = degree.get(node.graph_node_id) ?? 0
        const r = nodeRadius(deg, maxDeg)
        ctx.fillStyle = color
        ctx.beginPath()
        ctx.arc(node.x ?? 0, node.y ?? 0, r + 2, 0, 2 * Math.PI)
        ctx.fill()
      })
      .linkCanvasObjectMode(() => 'after')
      .linkCanvasObject((link: ForceLink, ctx: CanvasRenderingContext2D, scale: number) => {
        if (link !== hoveredLink || !link.relation_type) return
        const s = link.source as ForceNode
        const t = link.target as ForceNode
        if (typeof s !== 'object' || typeof t !== 'object') return
        const mx = ((s.x ?? 0) + (t.x ?? 0)) / 2
        const my = ((s.y ?? 0) + (t.y ?? 0)) / 2
        const labelRaw = formatRelation(link.relation_type)
        const text = labelRaw.length > 50 ? labelRaw.slice(0, 50) + '…' : labelRaw
        const fontSize = Math.max(10 / scale, 2)
        ctx.font = `${fontSize}px ui-sans-serif, system-ui, sans-serif`
        const padX = 4 / scale
        const padY = 2 / scale
        const w = ctx.measureText(text).width + padX * 2
        const h = fontSize + padY * 2
        ctx.fillStyle = 'rgba(15,23,42,0.92)'
        ctx.strokeStyle = 'rgba(148,163,184,0.5)'
        ctx.lineWidth = 0.5 / scale
        ctx.beginPath()
        ctx.rect(mx - w / 2, my - h / 2, w, h)
        ctx.fill()
        ctx.stroke()
        ctx.fillStyle = '#f1f5f9'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(text, mx, my)
      })
      .onNodeDragEnd((node: ForceNode) => {
        node.fx = node.x
        node.fy = node.y
      })
      .onNodeHover((node: ForceNode | null) => {
        hoveredId = node?.graph_node_id ?? null
        host.style.cursor = node ? 'pointer' : ''
      })
      .onLinkHover((link: ForceLink | null) => {
        hoveredLink = link
      })
      .onNodeClick((node: ForceNode) => {
        emit('nodeSelect', toPlainNode(node))
      })
      .onBackgroundClick(() => {
        emit('nodeSelect', null)
      })
  }

  graph.width(width).height(height)
  graph.d3Force('charge')?.strength(cfg.charge)
  graph.d3Force('link')?.distance(cfg.linkDistance)
  graph.graphData({ nodes, links })
  setTimeout(() => graph?.zoomToFit?.(400, 40), 50)
}

watch(
  () => props.data,
  () => {
    void draw()
  },
  { deep: false },
)

watch(
  () => props.layoutMode,
  () => {
    if (!graph) return
    const cfg = layoutForces(props.layoutMode ?? 'balanced')
    graph.d3Force('charge')?.strength(cfg.charge)
    graph.d3Force('link')?.distance(cfg.linkDistance)
    graph.d3ReheatSimulation?.()
  },
)

watch(
  () => props.selectedGraphNodeId,
  () => {
    graph?.refresh?.()
  },
)

watch(
  () => props.showIsolatedNodes,
  () => {
    void draw()
  },
)

watch(
  () => props.visibleTypes,
  () => {
    void draw()
  },
  { deep: true },
)

watch(
  () => props.heightPx,
  () => {
    if (!graph || !containerRef.value) return
    graph.width(containerRef.value.clientWidth || 640).height(canvasH.value)
  },
)

onMounted(() => {
  void draw()
  if (containerRef.value && typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(() => {
      if (!graph || !containerRef.value) return
      graph.width(containerRef.value.clientWidth || 640).height(canvasH.value)
    })
    ro.observe(containerRef.value)
  }
})

onUnmounted(() => {
  ro?.disconnect()
  ro = null
  teardown()
})
</script>
