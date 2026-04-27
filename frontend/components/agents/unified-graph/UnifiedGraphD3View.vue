<template>
  <div
    ref="containerRef"
    class="relative w-full overflow-hidden bg-muted/20"
    :style="{ height: `${canvasH}px` }"
  >
    <svg ref="svgRef" class="block h-full w-full touch-none" />
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
import type { SimulationNodeDatum } from 'd3'
import type { UnifiedGraphNodeDto, UnifiedGraphPreview, UnifiedGraphRelationDto } from '../../../types/unifiedGraph'

type SimNode = UnifiedGraphNodeDto &
  SimulationNodeDatum & { x?: number; y?: number; vx?: number; vy?: number; fx?: number | null; fy?: number | null }

type SimLink = Omit<UnifiedGraphRelationDto, 'source_graph_node_id' | 'target_graph_node_id'> & {
  source: SimNode | string
  target: SimNode | string
}

const ORIGIN_COLORS: Record<string, string> = {
  sqns: '#6366f1',
  knowledge: '#22c55e',
  directory: '#f97316',
  script_bridge: '#ec4899',
}

const ORIGIN_LABELS: Record<string, string> = {
  sqns: 'SQNS',
  knowledge: 'Файлы',
  directory: 'Справочники',
  script_bridge: 'Сценарии',
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
    /** Подсветка выбранного узла (клик → боковая панель). */
    selectedGraphNodeId?: string | null
    /** Вариант раскладки: влияет на плотность и разлёт кластеров. */
    layoutMode?: 'compact' | 'balanced' | 'spread'
    /** Показывать узлы без рёбер (изолированные). По умолчанию скрыты для читаемости. */
    showIsolatedNodes?: boolean
    /** Нижние информационные плашки (счётчики и статус). */
    bottomBadges?: string[]
  }>(),
  { heightPx: 560, selectedGraphNodeId: null, layoutMode: 'balanced', showIsolatedNodes: false, bottomBadges: () => [] },
)

const emit = defineEmits<{
  (e: 'nodeSelect', node: UnifiedGraphNodeDto | null): void
}>()

const toPlainNode = (d: SimNode): UnifiedGraphNodeDto => ({
  graph_node_id: d.graph_node_id,
  origin_slice: d.origin_slice,
  entity_type: d.entity_type,
  title: d.title,
  description: d.description,
  domain_entity_id: d.domain_entity_id,
  properties: d.properties && typeof d.properties === 'object' ? d.properties : {},
  provenance_tier: d.provenance_tier,
})

const containerRef = ref<HTMLDivElement | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)
const hint = ref('')
const canvasH = computed(() => props.heightPx ?? 560)

let teardown: (() => void) | null = null
let ro: ResizeObserver | null = null
/** Обновить обводку узлов без перезапуска симуляции (только смена выделения). */
let refreshNodeSelection: (() => void) | null = null
/** Центрировать выбранный узел в текущем масштабе. */
let focusSelectedNode: (() => void) | null = null
/** Короткая pulse-анимация выбранного узла. */
let pulseSelectedNode: (() => void) | null = null
let focusRetryTimer: ReturnType<typeof setTimeout> | null = null
/** Подсветка соседей выбранного / наведённого узла (интерактивный KG в духе LightRAG WebUI). */
let applyFocusStyle: (() => void) | null = null

const draw = async () => {
  teardown?.()
  teardown = null
  hint.value = ''

  const el = containerRef.value
  const svgEl = svgRef.value
  if (!el || !svgEl) return

  const d3 = await import('d3')
  d3.select(svgEl).selectAll('*').remove()

  if (!props.data?.nodes?.length) return

  const width = Math.max(el.clientWidth || 640, 320)
  const height = canvasH.value

  const linksRaw = props.data.relations ?? []
  const allNodes: SimNode[] = props.data.nodes.map((n) => ({ ...n }))
  const degree = new Map<string, number>()
  for (const n of allNodes) degree.set(n.graph_node_id, 0)
  for (const r of linksRaw) {
    degree.set(r.source_graph_node_id, (degree.get(r.source_graph_node_id) ?? 0) + 1)
    degree.set(r.target_graph_node_id, (degree.get(r.target_graph_node_id) ?? 0) + 1)
  }
  const nodes: SimNode[] = props.showIsolatedNodes
    ? allNodes
    : allNodes.filter((n) => (degree.get(n.graph_node_id) ?? 0) > 0)
  const descLen = new Map<string, number>()
  for (const n of allNodes) descLen.set(n.graph_node_id, toPlainText(n.description).length)

  if (!nodes.length && allNodes.length) {
    hint.value =
      'Все узлы без связей. Включите «Показать узлы без связей», чтобы отобразить их.'
    d3.select(svgEl).attr('viewBox', `0 0 ${width} ${height}`).attr('width', '100%').attr('height', '100%')
    return
  }

  const svg = d3
    .select(svgEl)
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('width', '100%')
    .attr('height', '100%')

  const root = svg.append('g').attr('class', 'zoom-root')
  const clusterLayer = root.append('g').attr('class', 'clusters')

  const visibleIds = new Set(nodes.map((n) => n.graph_node_id))
  const nodeById = new Map(nodes.map((n) => [n.graph_node_id, n]))
  const mainNodeId =
    [...nodes]
      .sort((a, b) => {
        const ad = degree.get(a.graph_node_id) ?? 0
        const bd = degree.get(b.graph_node_id) ?? 0
        if (bd !== ad) return bd - ad
        return (descLen.get(b.graph_node_id) ?? 0) - (descLen.get(a.graph_node_id) ?? 0)
      })[0]?.graph_node_id ?? null
  const maxDeg = Math.max(1, ...nodes.map((n) => degree.get(n.graph_node_id) ?? 0))
  const maxDesc = Math.max(1, ...nodes.map((n) => descLen.get(n.graph_node_id) ?? 0))
  const originGroups = Array.from(new Set(nodes.map((n) => n.origin_slice))).sort()
  /** Один срез (типично GraphRAG): без ослабления group-узлы слипаются в центре кластера. */
  const singleOrigin = originGroups.length <= 1
  const layoutCfg =
    props.layoutMode === 'compact'
      ? { clusterRadiusFactor: 0.2, charge: -72, linkDistance: 44, groupStrength: 0.18, clusterCircle: 72, collision: 22 }
      : props.layoutMode === 'spread'
        ? { clusterRadiusFactor: 0.38, charge: -155, linkDistance: 78, groupStrength: 0.09, clusterCircle: 108, collision: 30 }
        : { clusterRadiusFactor: 0.28, charge: -105, linkDistance: 58, groupStrength: 0.11, clusterCircle: 92, collision: 26 }

  const clusterRadiusBoost = singleOrigin ? 1.12 : 1
  const groupStrengthEff = singleOrigin ? layoutCfg.groupStrength * 0.55 : layoutCfg.groupStrength
  const clusterRadius = Math.max(
    88,
    Math.min(width, height) * layoutCfg.clusterRadiusFactor * clusterRadiusBoost,
  )
  const clusterTargets = new Map<string, { x: number; y: number }>()
  originGroups.forEach((origin, idx) => {
    const angle = (Math.PI * 2 * idx) / Math.max(originGroups.length, 1)
    clusterTargets.set(origin, {
      x: width / 2 + Math.cos(angle) * clusterRadius,
      y: height / 2 + Math.sin(angle) * clusterRadius,
    })
  })

  const links: SimLink[] = linksRaw
    .filter((r) => visibleIds.has(r.source_graph_node_id) && visibleIds.has(r.target_graph_node_id))
    .map((r) => ({
      ...r,
      source: nodeById.get(r.source_graph_node_id) ?? r.source_graph_node_id,
      target: nodeById.get(r.target_graph_node_id) ?? r.target_graph_node_id,
    }))
    .filter((l) => typeof l.source !== 'string' && typeof l.target !== 'string')

  const nCount = Math.max(nodes.length, 1)
  const sqrtN = Math.sqrt(nCount)
  const density = links.length / Math.max(nCount, 1)
  const chargeEff = layoutCfg.charge * (1 + sqrtN * 0.05) * (1 + Math.min(density, 4) * 0.03)
  const linkDistEff =
    layoutCfg.linkDistance * (1 + 0.1 * Math.log1p(density)) * (1 + 0.04 * (Math.min(width, height) / 560 - 1))

  const collisionRadius = (d: SimNode) => {
    const t = (d.title || d.graph_node_id).trim()
    const len = Math.min(t.length, 36)
    return layoutCfg.collision + 2 + Math.sqrt(len) * 0.9
  }

  for (const node of nodes) {
    if (node.x == null || node.y == null) {
      const jitter = 48 + sqrtN * 6
      node.x = width / 2 + (Math.random() - 0.5) * jitter * 2
      node.y = height / 2 + (Math.random() - 0.5) * jitter * 2
    }
  }

  const simulation = d3
    .forceSimulation(nodes as SimulationNodeDatum[])
    .velocityDecay(0.58)
    .alphaDecay(0.019)
    .alphaMin(0.006)
    .force(
      'link',
      d3
        .forceLink<SimNode, SimLink>(links)
        .id((d) => d.graph_node_id)
        .distance(linkDistEff)
        .strength(Math.max(0.28, Math.min(0.48, 0.58 - Math.min(density, 3) * 0.05))),
    )
    .force('charge', d3.forceManyBody().strength(chargeEff))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force(
      'group-x',
      d3
        .forceX<SimNode>((d) => clusterTargets.get(d.origin_slice)?.x ?? width / 2)
        .strength(groupStrengthEff),
    )
    .force(
      'group-y',
      d3
        .forceY<SimNode>((d) => clusterTargets.get(d.origin_slice)?.y ?? height / 2)
        .strength(groupStrengthEff),
    )
    .force('collision', d3.forceCollide<SimNode>().radius(collisionRadius).iterations(3))

  simulation.stop()
  const warmTicks = Math.min(220, Math.floor(32 + nCount * 1.2 + links.length * 0.45))
  for (let i = 0; i < warmTicks; i++) simulation.tick()

  const clusterNodes = originGroups.map((origin) => {
    const target = clusterTargets.get(origin) ?? { x: width / 2, y: height / 2 }
    return { origin, ...target }
  })

  const clusterSel = clusterLayer
    .selectAll('g')
    .data(clusterNodes)
    .join('g')

  clusterSel
    .append('circle')
    .attr('r', layoutCfg.clusterCircle)
    .attr('fill', (d) => `${ORIGIN_COLORS[d.origin] ?? '#64748b'}14`)
    .attr('stroke', (d) => `${ORIGIN_COLORS[d.origin] ?? '#64748b'}66`)
    .attr('stroke-width', 1)

  clusterSel
    .append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', -96)
    .attr('font-size', 11)
    .attr('font-weight', 600)
    .attr('fill', '#475569')
    .text((d) => ORIGIN_LABELS[d.origin] ?? d.origin)

  clusterSel.attr('transform', (d) => `translate(${d.x},${d.y})`)

  const linkLayer = root.append('g').attr('class', 'links')
  const nodeLayer = root.append('g').attr('class', 'nodes')

  const linkLine = linkLayer
    .selectAll('line.link-edge')
    .data(links)
    .join('line')
    .attr('class', 'link-edge')
    .attr('stroke', '#94a3b8')
    .attr('stroke-opacity', 0.48)
    .attr('stroke-width', 1.1)

  const truncateEdge = (s: string, max: number) => {
    const t = (s || '').trim()
    if (!t) return ''
    return t.length > max ? `${t.slice(0, max - 1)}…` : t
  }

  const linkLabel = linkLayer
    .selectAll('text.link-label')
    .data(links)
    .join('text')
    .attr('class', 'link-label')
    .attr('font-size', 7.5)
    .attr('fill', '#64748b')
    .attr('text-anchor', 'middle')
    .attr('pointer-events', 'none')
    .attr('opacity', 1)
    .text((d) => truncateEdge(d.relation_type, 22))

  const pointerInSim = (event: MouseEvent | d3.D3DragEvent<SVGGElement, SimNode, SimNode | SVGGElement>) => {
    const p = d3.pointer(event, svgEl)
    return d3.zoomTransform(svgEl).invert(p)
  }
  const baseFill = (d: SimNode) => ORIGIN_COLORS[d.origin_slice] ?? '#64748b'
  const isMain = (d: SimNode) => !!mainNodeId && d.graph_node_id === mainNodeId
  const mainFill = '#f59e0b'
  const mainStroke = '#d97706'
  const baseRadius = (d: SimNode) => {
    const degNorm = Math.sqrt((degree.get(d.graph_node_id) ?? 0) / maxDeg)
    const descNorm = Math.sqrt((descLen.get(d.graph_node_id) ?? 0) / maxDesc)
    // Более заметная шкала: отличие видно не только у главного узла.
    return 7.5 + degNorm * 4.4 + descNorm * 4.6 + (isMain(d) ? 2.2 : 0)
  }

  const nodeSel = nodeLayer
    .selectAll('g.node')
    .data(nodes)
    .join('g')
    .attr('class', 'node')
    .style('cursor', 'grab')

  nodeSel
    .append('circle')
    .attr('r', (d) => baseRadius(d))
    .attr('fill', (d) => (isMain(d) ? mainFill : ORIGIN_COLORS[d.origin_slice] ?? '#64748b'))

  pulseSelectedNode = () => {
    const selectedId = props.selectedGraphNodeId
    if (!selectedId) return
    nodeSel
      .select('circle')
      .filter((d: SimNode) => d.graph_node_id === selectedId)
      .interrupt()
      .transition()
      .duration(140)
      .ease(d3.easeCubicOut)
      .attr('r', (d: SimNode) => baseRadius(d) + 3)
      .transition()
      .duration(260)
      .ease(d3.easeCubicInOut)
      .attr('r', (d: SimNode) => baseRadius(d) + 1.2)
  }

  const labelMode = nCount > 96 ? 'short' : 'full'
  nodeSel
    .append('title')
    .text((d) => [d.title, d.entity_type, isMain(d) ? 'главный узел' : '', toPlainText(d.description).slice(0, 400)].filter(Boolean).join('\n'))

  nodeSel
    .append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', labelMode === 'full' ? 24 : 21)
    .attr('font-size', labelMode === 'full' ? 9 : 8)
    .attr('fill', '#334155')
    .attr('pointer-events', 'none')
    .text((d) => {
      const t = (d.title || d.graph_node_id).trim()
      if (labelMode === 'short') return t.length > 20 ? `${t.slice(0, 18)}…` : t
      return t.length > 30 ? `${t.slice(0, 28)}…` : t
    })

  let hoverId: string | null = null
  const neighborSet = (center: string) => {
    const nb = new Set<string>([center])
    for (const l of links) {
      const a = (l.source as SimNode).graph_node_id
      const b = (l.target as SimNode).graph_node_id
      if (a === center) nb.add(b)
      if (b === center) nb.add(a)
    }
    return nb
  }

  const brightenFill = (hex: string, k: number) => {
    try {
      return d3.rgb(hex).brighter(k).formatHex()
    } catch {
      return hex
    }
  }

  applyFocusStyle = () => {
    const rawSid = props.selectedGraphNodeId
    const sid = rawSid && nodeById.has(rawSid) ? rawSid : null
    const fid = hoverId ?? sid ?? null
    const ms = 200
    const ease = d3.easeCubicOut

    if (!fid) {
      linkLine.transition().duration(ms).ease(ease).attr('stroke-opacity', 0.48).attr('stroke-width', 1.1).attr('stroke', '#94a3b8')
      linkLabel.transition().duration(ms).ease(ease).attr('opacity', 1)
      nodeSel.select('text').transition().duration(ms).ease(ease).attr('opacity', 1)
      nodeSel.select('circle').each(function (d: SimNode) {
        const c = d3.select(this)
        const on = !!(sid && d.graph_node_id === sid)
        c.transition()
          .duration(ms)
          .ease(ease)
          .attr('opacity', 1)
          .attr('r', on ? baseRadius(d) + 1.2 : baseRadius(d))
          .attr('stroke', on ? '#6366f1' : isMain(d) ? mainStroke : '#0f172a')
          .attr('stroke-width', on ? 3 : isMain(d) ? 1.5 : 0.35)
          .attr('fill', isMain(d) ? mainFill : baseFill(d))
      })
      return
    }

    const nb = neighborSet(fid)
    const strong = !!sid && fid === sid && !hoverId
    const dimNode = hoverId ? 0.42 : 0.38
    const dimEdge = hoverId ? 0.36 : 0.32
    const isHover = !!hoverId

    linkLine
      .transition()
      .duration(ms)
      .ease(ease)
      .attr('stroke-opacity', (d: SimLink) => {
        const a = (d.source as SimNode).graph_node_id
        const b = (d.target as SimNode).graph_node_id
        return a === fid || b === fid ? (strong ? 0.95 : 0.82) : dimEdge
      })
      .attr('stroke-width', (d: SimLink) => {
        const a = (d.source as SimNode).graph_node_id
        const b = (d.target as SimNode).graph_node_id
        return a === fid || b === fid ? (strong ? 2.4 : 1.85) : 0.75
      })
      .attr('stroke', (d: SimLink) => {
        const a = (d.source as SimNode).graph_node_id
        const b = (d.target as SimNode).graph_node_id
        return a === fid || b === fid ? (strong ? '#6366f1' : '#0ea5e9') : '#cbd5e1'
      })
    linkLabel.transition().duration(ms).ease(ease).attr('opacity', (d: SimLink) => {
      const a = (d.source as SimNode).graph_node_id
      const b = (d.target as SimNode).graph_node_id
      return a === fid || b === fid ? 1 : dimNode + 0.14
    })

    nodeSel.select('text').transition().duration(ms).ease(ease).attr('opacity', (d: SimNode) => (nb.has(d.graph_node_id) ? 1 : dimNode))

    nodeSel.select('circle').each(function (d: SimNode) {
      const c = d3.select(this)
      const id = d.graph_node_id
      const inN = nb.has(id)
      const isFocal = id === fid
      const bf = baseFill(d)

      if (isHover) {
        if (isFocal) {
          c.transition()
            .duration(ms)
            .ease(ease)
            .attr('opacity', 1)
            .attr('r', baseRadius(d) + 2.6)
            .attr('stroke', '#0369a1')
            .attr('stroke-width', 2.8)
            .attr('fill', isMain(d) ? mainFill : brightenFill(bf, 0.5))
        }
        else if (inN) {
          c.transition()
            .duration(ms)
            .ease(ease)
            .attr('opacity', 1)
            .attr('r', baseRadius(d) + 1.1)
            .attr('stroke', '#0284c7')
            .attr('stroke-width', 2.2)
            .attr('fill', isMain(d) ? mainFill : brightenFill(bf, 0.3))
        }
        else {
          c.transition()
            .duration(ms)
            .ease(ease)
            .attr('opacity', dimNode)
            .attr('r', Math.max(8, baseRadius(d) - 1.3))
            .attr('stroke', '#cbd5e1')
            .attr('stroke-width', 0.25)
            .attr('fill', isMain(d) ? mainFill : bf)
        }
      }
      else {
        const isSel = !!(sid && id === sid)
        if (inN) {
          c.transition()
            .duration(ms)
            .ease(ease)
            .attr('opacity', 1)
            .attr('r', isSel ? baseRadius(d) + 1.2 : baseRadius(d) + 0.5)
            .attr('stroke', isSel ? '#6366f1' : isMain(d) ? mainStroke : '#818cf8')
            .attr('stroke-width', isSel ? 3 : 2)
            .attr('fill', isMain(d) ? mainFill : isSel ? brightenFill(bf, 0.18) : brightenFill(bf, 0.1))
        }
        else {
          c.transition()
            .duration(ms)
            .ease(ease)
            .attr('opacity', dimNode)
            .attr('r', Math.max(8, baseRadius(d) - 1.3))
            .attr('stroke', '#cbd5e1')
            .attr('stroke-width', 0.25)
            .attr('fill', isMain(d) ? mainFill : bf)
        }
      }
    })
  }

  refreshNodeSelection = () => {
    applyFocusStyle?.()
  }
  refreshNodeSelection()

  const drag = d3
    .drag<SVGGElement, SimNode>()
    .on('start', (event, d) => {
      if (!event.active) simulation.alphaTarget(0.42).restart()
      const [x, y] = pointerInSim(event)
      d.fx = x
      d.fy = y
      nodeSel.filter((n: SimNode) => n.graph_node_id === d.graph_node_id).style('cursor', 'grabbing')
    })
    .on('drag', (event, d) => {
      const [x, y] = pointerInSim(event)
      d.fx = x
      d.fy = y
    })
    .on('end', (event, d) => {
      if (!event.active) simulation.alphaTarget(0)
      d.fx = null
      d.fy = null
      nodeSel.style('cursor', 'grab')
    })

  nodeSel.call(drag)

  nodeSel
    .on('mouseenter', (_event, d) => {
      hoverId = d.graph_node_id
      applyFocusStyle?.()
      hint.value = [
        d.title,
        `тип: ${d.entity_type}`,
        `срез: ${d.origin_slice}`,
        isMain(d) ? 'главный узел' : '',
        d.description ? toPlainText(d.description).slice(0, 220) : '',
      ]
        .filter(Boolean)
        .join(' · ')
    })
    .on('mouseleave', () => {
      hoverId = null
      applyFocusStyle?.()
      hint.value = ''
    })
    .on('click', (event: MouseEvent, d) => {
      event.stopPropagation()
      emit('nodeSelect', toPlainNode(d))
    })

  const zoom = d3
    .zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.28, 3.2])
    .filter((event) => {
      if (event.type === 'wheel') return true
      const t = event.target as Element | null
      if (t?.closest?.('g.node')) return false
      return !event.button
    })
    .on('zoom', (ev) => {
      root.attr('transform', ev.transform.toString())
    })

  svg.call(zoom)
  svg.on('click.unified-graph-clear-selection', (event: MouseEvent) => {
    const target = event.target as Element | null
    if (!target) return
    // Клик по узлу не сбрасывает выделение; клик по пустому пространству сбрасывает.
    if (target.closest('g.nodes g.node')) return
    emit('nodeSelect', null)
  })

  focusSelectedNode = () => {
    const selectedId = props.selectedGraphNodeId
    if (!selectedId) return
    const node = nodeById.get(selectedId)
    if (!node) return
    if (typeof node.x !== 'number' || typeof node.y !== 'number') return
    const current = d3.zoomTransform(svgEl)
    const k = Math.max(0.45, current.k || 1)
    const tx = width / 2 - node.x * k
    const ty = height / 2 - node.y * k
    svg
      .transition()
      .duration(260)
      .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(k))
  }

  simulation.on('tick', () => {
    linkLine
      .attr('x1', (d) => (d.source as SimNode).x ?? 0)
      .attr('y1', (d) => (d.source as SimNode).y ?? 0)
      .attr('x2', (d) => (d.target as SimNode).x ?? 0)
      .attr('y2', (d) => (d.target as SimNode).y ?? 0)

    linkLabel.attr('x', (d) => {
      const a = d.source as SimNode
      const b = d.target as SimNode
      return ((a.x ?? 0) + (b.x ?? 0)) / 2
    })
    linkLabel.attr('y', (d) => {
      const a = d.source as SimNode
      const b = d.target as SimNode
      return ((a.y ?? 0) + (b.y ?? 0)) / 2 - 3
    })

    nodeSel.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`)
  })

  simulation.alpha(0.32).restart()
  applyFocusStyle?.()

  const stopSim = () => {
    simulation.stop()
  }

  teardown = () => {
    stopSim()
    refreshNodeSelection = null
    focusSelectedNode = null
    pulseSelectedNode = null
    applyFocusStyle = null
    if (focusRetryTimer) clearTimeout(focusRetryTimer)
    focusRetryTimer = null
    svg.on('.zoom', null)
    svg.on('click.unified-graph-clear-selection', null)
    d3.select(svgEl).selectAll('*').remove()
  }
}

onMounted(() => {
  void draw()
  if (containerRef.value) {
    let t: ReturnType<typeof setTimeout> | null = null
    ro = new ResizeObserver(() => {
      if (t) clearTimeout(t)
      t = setTimeout(() => void draw(), 120)
    })
    ro.observe(containerRef.value)
  }
})

watch(
  () => props.data,
  () => {
    void draw()
  },
  { deep: true },
)

watch(
  () => props.layoutMode,
  () => {
    void draw()
  },
)

watch(
  () => props.showIsolatedNodes,
  () => {
    void draw()
  },
)

watch(
  () => props.selectedGraphNodeId,
  () => {
    refreshNodeSelection?.()
    applyFocusStyle?.()
    focusSelectedNode?.()
    pulseSelectedNode?.()
    if (focusRetryTimer) clearTimeout(focusRetryTimer)
    focusRetryTimer = setTimeout(() => {
      focusSelectedNode?.()
      pulseSelectedNode?.()
      focusRetryTimer = null
    }, 180)
  },
)

watch(canvasH, () => {
  void draw()
})

onUnmounted(() => {
  if (focusRetryTimer) clearTimeout(focusRetryTimer)
  focusRetryTimer = null
  ro?.disconnect()
  ro = null
  teardown?.()
  teardown = null
})
</script>
