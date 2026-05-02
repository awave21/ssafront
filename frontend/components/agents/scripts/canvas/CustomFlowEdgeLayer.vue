<!--
  CustomFlowEdgeLayer — единый SVG-слой для всех рёбер.

  Все edges рисуются в ОДНОМ <svg>, что даёт один paint layer.
  Пути в Map<edgeId, string>; перерасчёт происходит только для рёбер,
  чьи source/target в dirtyEdgeIds (см. useFlowCanvas).
-->
<template>
  <!-- SVG занимает всю площадь .custom-flow-graph (inset-0).
       Координаты путей — в canvas-space, viewport transform применяется родителем
       .custom-flow-graph; здесь НЕ дублируем. overflow:visible — на случай если
       пути выходят за SVG bbox. -->
  <svg
    class="absolute inset-0 pointer-events-none"
    style="overflow: visible;"
    width="100%"
    height="100%"
  >
    <path
      v-for="edge in edges"
      :key="edge.id"
      :d="paths[edge.id] ?? ''"
      :stroke="edgeStroke(edge)"
      :stroke-width="edge.id === selectedEdgeId ? 2.5 : 2"
      stroke-linecap="round"
      stroke-linejoin="round"
      fill="none"
      class="cursor-pointer pointer-events-auto"
      :class="{ 'opacity-90': edge.id === selectedEdgeId }"
      @click="onEdgeClick(edge, $event)"
    />
  </svg>
</template>

<script setup lang="ts">
import { reactive, watch, type Ref } from 'vue'
import type { FlowCanvasStore, EdgeMeta } from './composables/useFlowCanvas'
import type { Viewport } from './composables/useFlowViewport'
import { buildEdgePath, type EdgePathType } from './composables/useFlowEdgePath'

const props = defineProps<{
  store: FlowCanvasStore
  viewport: Viewport
  edges: readonly EdgeMeta[]
  width: number
  height: number
  selectedEdgeId?: string | null
  /** Цвет рёбер по умолчанию (можно override per-edge через style.stroke). */
  defaultStroke?: string
  /** Тип пути по умолчанию. */
  defaultType?: EdgePathType
}>()

const emit = defineEmits<{
  (e: 'edge-click', edge: EdgeMeta, ev: MouseEvent): void
}>()

/** Кэш SVG-путей по edgeId — обновляется реактивно через flushTick. */
const paths = reactive<Record<string, string>>({})

const recomputePath = (edge: EdgeMeta) => {
  const sourceBox = props.store.getNodeBox(edge.source)
  const targetBox = props.store.getNodeBox(edge.target)
  if (!sourceBox || !targetBox) {
    paths[edge.id] = ''
    return
  }
  // Используем точные offsets handle'ов если есть. Fallback на right/left-center.
  const sourceHandleId = edge.sourceHandle ?? 'source'
  const targetHandleId = edge.targetHandle ?? 'target'
  const sOff = props.store.getHandleOffset(edge.source, sourceHandleId)
    ?? { x: sourceBox.width, y: sourceBox.height / 2, type: 'source' as const }
  const tOff = props.store.getHandleOffset(edge.target, targetHandleId)
    ?? { x: 0, y: targetBox.height / 2, type: 'target' as const }
  const endpoints = {
    sourceX: sourceBox.x + sOff.x,
    sourceY: sourceBox.y + sOff.y,
    targetX: targetBox.x + tOff.x,
    targetY: targetBox.y + tOff.y,
  }
  paths[edge.id] = buildEdgePath(props.defaultType ?? 'smoothstep', endpoints)
}

/** Полный пересчёт всех рёбер — при первой загрузке и при изменении набора. */
const recomputeAll = () => {
  for (const edge of props.edges) recomputePath(edge)
}

/** Частичный пересчёт — только грязные edges (драг). */
const recomputeDirty = () => {
  const dirty = props.store.dirtyEdgeIds
  if (dirty.size === 0) return
  // Создаём словарь существующих edges для O(1) lookup.
  const byId = new Map(props.edges.map(e => [e.id, e]))
  for (const id of dirty) {
    const edge = byId.get(id)
    if (edge) recomputePath(edge)
  }
  dirty.clear()
}

// Триггер от useFlowCanvas — после каждого RAF-flush обновляем грязные edges.
watch(() => props.store.flushTick.value, () => {
  recomputeDirty()
})

// При смене edges или viewport — пересчёт всего.
watch(() => props.edges, () => {
  recomputeAll()
}, { immediate: true })

// При viewport pan/zoom edges не пересчитываются — они в transform group.
// При размере canvas меняется только width/height SVG.

const edgeStroke = (edge: EdgeMeta) => {
  if (edge.id === props.selectedEdgeId) return 'rgba(79, 70, 229, 0.9)'
  return props.defaultStroke ?? 'rgba(99, 102, 241, 0.5)'
}

const onEdgeClick = (edge: EdgeMeta, ev: MouseEvent) => {
  emit('edge-click', edge, ev)
}
</script>
