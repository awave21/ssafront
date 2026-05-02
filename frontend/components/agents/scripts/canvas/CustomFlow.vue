<!--
  CustomFlow — root компонент кастомного DOM-канваса.
  Drop-in замена для VueFlow с похожим API.

  АРХИТЕКТУРА:
  - Position store (Map) ВНЕ Vue реактивности — drag не платит за reactivity
  - DOM transform на нодах апдейтится через RAF-batched flush
  - Edges в одном SVG-слое; пути обновляются только для затронутых рёбер
  - Pan/zoom через transform на root group (CSS + SVG)
  - Vue реактивность только при drag-stop, structural changes (add/remove), edits
-->
<template>
  <div
    ref="canvasEl"
    class="custom-flow relative h-full w-full overflow-hidden"
    :class="{ 'is-dragging-pane': isPanning }"
    @pointerdown="onPanePointerDown"
    @click.self="onPaneClick"
    @wheel="onWheel"
    @dragover.prevent
    @drop="onDrop"
  >
    <!-- Pane background — фон + grid (если включён). -->
    <div class="custom-flow-pane absolute inset-0">
      <slot name="background" />
    </div>

    <!-- Граф: одна transform-group для всех нод и SVG-рёбер.
         inset-0 чтобы div был полного размера канваса (иначе SVG внутри 0×0). -->
    <div
      class="custom-flow-graph absolute inset-0"
      :style="graphStyle"
    >
      <!-- Edges layer — единый SVG для всех путей. -->
      <CustomFlowEdgeLayer
        :store="store"
        :viewport="viewport"
        :edges="edges"
        :width="canvasSize.width"
        :height="canvasSize.height"
        :selected-edge-id="selectedEdgeId"
        :default-stroke="defaultEdgeStroke"
        @edge-click="onEdgeClick"
      />

      <!-- Nodes layer — каждая нода с absolute transform-translate. -->
      <CustomFlowNode
        v-for="n in nodes"
        :key="n.id"
        :node="n"
        :selected="selectedNodeIds.has(n.id)"
        @click="onNodeClick"
        @dblclick="onNodeDblClick"
        @mouse-enter="onNodeMouseEnter"
        @drag-start="onNodeDragStart"
        @drag-stop="onNodeDragStop"
      >
        <template #default="slotProps">
          <slot
            :name="`node-${slotProps.type ?? 'default'}`"
            v-bind="slotProps"
          >
            <!-- Fallback default rendering -->
            <slot name="node-default" v-bind="slotProps">
              <div class="rounded border bg-card px-3 py-2 text-xs">{{ slotProps.id }}</div>
            </slot>
          </slot>
        </template>
      </CustomFlowNode>
    </div>

    <!-- Connect drag preview: phantom-линия от source-handle до курсора. -->
    <svg
      v-if="phantomPath"
      class="absolute left-0 top-0 h-full w-full pointer-events-none z-[20]"
    >
      <path
        :d="phantomPath"
        stroke="#6366f1"
        stroke-width="2"
        stroke-dasharray="6 3"
        fill="none"
        stroke-linecap="round"
      />
    </svg>

    <!-- UI overlay — toolbar, MiniMap, Controls (через slot). -->
    <slot name="overlay" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, provide, ref, shallowRef, watch, type Ref } from 'vue'
import CustomFlowEdgeLayer from './CustomFlowEdgeLayer.vue'
import CustomFlowNode from './CustomFlowNode.vue'
import { useFlowCanvas, type EdgeMeta, type NodeMeta, type NodePosition } from './composables/useFlowCanvas'
import { useFlowViewport, type Viewport } from './composables/useFlowViewport'
import { useFlowPanZoom } from './composables/useFlowDrag'
import { useFlowConnect } from './composables/useFlowConnect'

type FlowNode = NodeMeta & { position: NodePosition }

const props = defineProps<{
  nodes: FlowNode[]
  edges: EdgeMeta[]
  defaultViewport?: Viewport
  minZoom?: number
  maxZoom?: number
  defaultEdgeStroke?: string
}>()

/** Event payloads совместимы с VueFlow API. */
const emit = defineEmits<{
  (e: 'update:nodes', nodes: FlowNode[]): void
  (e: 'update:edges', edges: EdgeMeta[]): void
  (e: 'update:viewport', vp: Viewport): void
  (e: 'node-click', payload: { node: NodeMeta; event: MouseEvent }): void
  (e: 'node-double-click', payload: { node: NodeMeta; event: MouseEvent }): void
  (e: 'node-mouse-enter', payload: { node: NodeMeta }): void
  (e: 'node-drag-start', payload: { node: NodeMeta }): void
  (e: 'node-drag-stop', payload: { node: NodeMeta; position: NodePosition }): void
  (e: 'edge-click', payload: { edge: EdgeMeta; event: MouseEvent }): void
  (e: 'pane-click', ev: MouseEvent): void
  (e: 'drop', ev: DragEvent, projected: NodePosition): void
  (e: 'connect', params: { source: string; target: string; sourceHandle: string; targetHandle: string }): void
}>()

// ── Store + viewport ────────────────────────────────────────────────────────
const store = useFlowCanvas()
const vp = useFlowViewport({
  initial: props.defaultViewport ?? { x: 0, y: 0, zoom: 1 },
  minZoom: props.minZoom ?? 0.2,
  maxZoom: props.maxZoom ?? 2,
})
const viewport = vp.viewport
const viewportRef = vp.viewport

/**
 * Provide live viewport ref для дочерних компонентов (CustomFlowNode → useFlowDrag).
 * Через props Vue auto-unwraps ref — drag composable перестаёт видеть .value,
 * поэтому используем inject как обходной путь.
 */
provide('customFlowViewport', viewport)
provide('customFlowStore', store)

// reactive viewport copy для template (computed)
const graphStyle = computed(() => ({
  transform: `translate3d(${viewport.value.x}px, ${viewport.value.y}px, 0) scale(${viewport.value.zoom})`,
  transformOrigin: '0 0',
}))

// Эмит viewport changes на родителя (debounce-free на стороне CustomFlow,
// родитель сам debounce'нет).
watch(viewport, (v) => emit('update:viewport', v), { deep: true })

// ── Edges регистрация ───────────────────────────────────────────────────────
// Регистрируем все edges в store при изменении props.edges.
// useFlowCanvas сам пометит их dirty и SVG layer перерисует.
const registeredEdgeIds = new Set<string>()
watch(() => props.edges, (newEdges) => {
  const newIds = new Set(newEdges.map(e => e.id))
  // Удаляем те что больше нет.
  for (const id of registeredEdgeIds) {
    if (!newIds.has(id)) {
      store.unregisterEdge(id)
      registeredEdgeIds.delete(id)
    }
  }
  // Добавляем новые.
  for (const edge of newEdges) {
    if (!registeredEdgeIds.has(edge.id)) {
      store.registerEdge(edge)
      registeredEdgeIds.add(edge.id)
    } else {
      // Обновим metadata если source/target поменялся.
      store.unregisterEdge(edge.id)
      store.registerEdge(edge)
    }
  }
}, { immediate: true, deep: false })

// ── Canvas размер для SVG ───────────────────────────────────────────────────
const canvasEl = ref<HTMLDivElement | null>(null)
const canvasSize = ref({ width: 1200, height: 800 })

const measureCanvas = () => {
  if (!canvasEl.value) return
  const rect = canvasEl.value.getBoundingClientRect()
  canvasSize.value = { width: rect.width, height: rect.height }
}

let ro: ResizeObserver | null = null
onMounted(() => {
  measureCanvas()
  if (canvasEl.value && typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(measureCanvas)
    ro.observe(canvasEl.value)
  }
})
onBeforeUnmount(() => { ro?.disconnect() })

// ── Selection ───────────────────────────────────────────────────────────────
const selectedNodeIds = shallowRef(new Set<string>())
const selectedEdgeId = ref<string | null>(null)

const isPanning = ref(false)

// ── Connect drag ───────────────────────────────────────────────────────────
const connect = useFlowConnect({
  onConnect: (params) => emit('connect', params),
})

const phantomPath = computed(() => {
  if (!connect.inProgress.value || !canvasEl.value) return ''
  const rect = canvasEl.value.getBoundingClientRect()
  const start = connect.inProgress.value.startScreen
  const end = connect.inProgress.value.currentScreen
  // Координаты в screen-space → SVG (которое поверх всего канваса).
  const sx = start.x - rect.left
  const sy = start.y - rect.top
  const ex = end.x - rect.left
  const ey = end.y - rect.top
  // Простая bezier между точками для preview-линии.
  const dx = (ex - sx) / 2
  return `M ${sx} ${sy} C ${sx + dx} ${sy}, ${ex - dx} ${ey}, ${ex} ${ey}`
})

// ── Pan / zoom ──────────────────────────────────────────────────────────────
const panZoom = useFlowPanZoom({
  viewport,
  setViewport: vp.setViewport,
  zoomAtPoint: vp.zoomAtPoint,
  panBy: vp.panBy,
})

const onPanePointerDown = (e: PointerEvent) => {
  // 1) Если pointerdown на handle — стартуем connect-drag, не пан.
  if ((e.target as HTMLElement).closest('[data-handle-id]')) {
    if (connect.tryStartConnect(e)) return
  }
  // 2) Если pointerdown на ноде — drag ноды (обработается в CustomFlowNode).
  if ((e.target as HTMLElement).closest('.custom-flow-node')) return
  // 3) Иначе — pan канваса.
  if (!canvasEl.value) return
  isPanning.value = true
  panZoom.onPanePointerDown(e, canvasEl.value)
  // Reset isPanning when pointer up.
  const cleanup = () => { isPanning.value = false; window.removeEventListener('pointerup', cleanup) }
  window.addEventListener('pointerup', cleanup, { once: true })
}

const onWheel = (e: WheelEvent) => {
  if (!canvasEl.value) return
  panZoom.onWheel(e, canvasEl.value.getBoundingClientRect())
}

// ── Event handlers ──────────────────────────────────────────────────────────
const onNodeClick = (node: NodeMeta, ev: MouseEvent) => {
  const ids = new Set(selectedNodeIds.value)
  if (ev.shiftKey) {
    if (ids.has(node.id)) ids.delete(node.id)
    else ids.add(node.id)
  } else {
    ids.clear()
    ids.add(node.id)
  }
  selectedNodeIds.value = ids
  selectedEdgeId.value = null
  emit('node-click', { node, event: ev })
}

const onNodeDblClick = (node: NodeMeta, ev: MouseEvent) => {
  emit('node-double-click', { node, event: ev })
}

const onNodeMouseEnter = (node: NodeMeta) => {
  emit('node-mouse-enter', { node })
}

const onNodeDragStart = (node: NodeMeta) => {
  emit('node-drag-start', { node })
}

const onNodeDragStop = (node: NodeMeta, position: NodePosition) => {
  // Sync позиций из store в Vue ref для persistence.
  // Создаём новый массив, обновляем position на изменившейся ноде.
  const next = props.nodes.map(n =>
    n.id === node.id ? { ...n, position: { ...position } } : n,
  )
  emit('update:nodes', next as FlowNode[])
  emit('node-drag-stop', { node, position })
}

const onEdgeClick = (edge: EdgeMeta, ev: MouseEvent) => {
  selectedEdgeId.value = edge.id
  emit('edge-click', { edge, event: ev })
}

const onPaneClick = (ev: MouseEvent) => {
  selectedNodeIds.value = new Set()
  selectedEdgeId.value = null
  emit('pane-click', ev)
}

const onDrop = (ev: DragEvent) => {
  if (!canvasEl.value) return
  const rect = canvasEl.value.getBoundingClientRect()
  const projected = vp.screenToFlow({ x: ev.clientX, y: ev.clientY }, rect)
  emit('drop', ev, projected)
}

// ── Public API (defineExpose) — для совместимости с useVueFlow ─────────────
const findNode = (id: string): FlowNode | null => {
  return props.nodes.find(n => n.id === id) ?? null
}

const project = (screen: { x: number; y: number }): NodePosition => {
  if (!canvasEl.value) return { x: 0, y: 0 }
  return vp.screenToFlow(screen, canvasEl.value.getBoundingClientRect())
}

const fitView = (options: { padding?: number; nodes?: { id: string }[] } = {}) => {
  const targetIds = options.nodes?.map(n => n.id)
  let bounds: { minX: number; minY: number; maxX: number; maxY: number } | null
  if (targetIds && targetIds.length > 0) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const id of targetIds) {
      const box = store.getNodeBox(id)
      if (!box) continue
      minX = Math.min(minX, box.x)
      minY = Math.min(minY, box.y)
      maxX = Math.max(maxX, box.x + box.width)
      maxY = Math.max(maxY, box.y + box.height)
    }
    bounds = isFinite(minX) ? { minX, minY, maxX, maxY } : null
  } else {
    bounds = store.getAllNodesBounds()
  }
  if (!bounds || !canvasEl.value) return
  const rect = canvasEl.value.getBoundingClientRect()
  vp.fitBounds(bounds, { width: rect.width, height: rect.height }, options.padding ?? 0.1)
}

const setSelectedNodes = (ids: string[]) => {
  selectedNodeIds.value = new Set(ids)
}
const clearSelection = () => {
  selectedNodeIds.value = new Set()
  selectedEdgeId.value = null
}

defineExpose({
  // Selectors
  findNode,
  // Coordinates
  project,
  screenToFlow: project,
  // Viewport
  viewport,
  setViewport: vp.setViewport,
  zoomIn: vp.zoomIn,
  zoomOut: vp.zoomOut,
  zoomMaxReached: vp.zoomMaxReached,
  zoomMinReached: vp.zoomMinReached,
  fitView,
  // Selection
  setSelectedNodes,
  clearSelection,
  // Store (для добавления edges из родителя)
  store,
})
</script>

<style scoped>
.custom-flow {
  background: linear-gradient(180deg, rgba(255,255,255,0.6), rgba(248,250,252,0.94)) #f8fafc;
  cursor: grab;
}
.custom-flow.is-dragging-pane {
  cursor: grabbing;
}
.custom-flow-pane {
  pointer-events: none;
}
</style>
