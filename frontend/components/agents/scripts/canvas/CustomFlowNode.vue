<!--
  CustomFlowNode — обёртка одной ноды.

  Сама нода — обычный absolute div, position управляется напрямую через DOM
  (style.transform), вне Vue реактивности. Vue реактивно отвечает только за
  data, selected, warnOrphan и т.п. — атрибуты внутреннего слота (UniformNode).
-->
<template>
  <div
    ref="el"
    :data-node-id="node.id"
    class="custom-flow-node absolute left-0 top-0 will-change-transform"
    :class="{ 'is-selected': isSelected, 'is-dragging': isDragging }"
    @pointerdown="onPointerDown"
    @click.stop="onClick"
    @dblclick.stop="onDblClick"
    @mouseenter="emit('mouse-enter', node)"
  >
    <slot
      :id="node.id"
      :data="node.data"
      :selected="isSelected"
      :type="node.type"
    />
  </div>
</template>

<script setup lang="ts">
import { inject, onMounted, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import type { FlowCanvasStore, NodeMeta, NodePosition } from './composables/useFlowCanvas'
import { useFlowDrag } from './composables/useFlowDrag'
import type { Viewport } from './composables/useFlowViewport'

const props = defineProps<{
  node: NodeMeta & { position: NodePosition }
  selected: boolean
}>()

// Получаем store и live viewport ref через inject (Vue не auto-unwrap'ает их).
const store = inject<FlowCanvasStore>('customFlowStore')!
const viewport = inject<Ref<Viewport>>('customFlowViewport')!

const emit = defineEmits<{
  (e: 'click', node: NodeMeta, ev: MouseEvent): void
  (e: 'dblclick', node: NodeMeta, ev: MouseEvent): void
  (e: 'mouse-enter', node: NodeMeta): void
  (e: 'drag-start', node: NodeMeta): void
  (e: 'drag-stop', node: NodeMeta, position: NodePosition): void
}>()

const el = ref<HTMLDivElement | null>(null)
const isSelected = ref(false)
const isDragging = ref(false)

watch(() => props.selected, (v) => { isSelected.value = v }, { immediate: true })

const drag = useFlowDrag({
  store,
  viewport,
  onDragStart: (id) => {
    isDragging.value = true
    emit('drag-start', props.node)
  },
  onDragStop: (id, pos) => {
    isDragging.value = false
    emit('drag-stop', props.node, pos)
  },
})

const onPointerDown = (e: PointerEvent) => {
  // Если событие на handle — пропускаем (handle сам обработает в Phase 2).
  const target = e.target as HTMLElement | null
  if (target?.closest('[data-handle-id]')) return
  drag.onPointerDown(e, props.node.id)
}

const onClick = (e: MouseEvent) => emit('click', props.node, e)
const onDblClick = (e: MouseEvent) => emit('dblclick', props.node, e)

/**
 * Измеряет позиции всех handle-элементов внутри ноды (по data-атрибутам)
 * относительно top-left ноды и регистрирует их в store. Используется для
 * точных endpoints рёбер: edge выходит из CENTRA конкретного handle, а не
 * из right-center ноды.
 */
const measureHandles = () => {
  if (!el.value) return
  const nodeRect = el.value.getBoundingClientRect()
  const zoom = viewport.value.zoom || 1
  el.value.querySelectorAll<HTMLElement>('[data-handle-id]').forEach((h) => {
    const id = h.dataset.handleId
    const type = h.dataset.handleType as 'source' | 'target' | undefined
    if (!id || !type) return
    const hRect = h.getBoundingClientRect()
    // Центр handle относительно top-left ноды, в canvas-pixels (делим на zoom).
    const offsetX = (hRect.left + hRect.width / 2 - nodeRect.left) / zoom
    const offsetY = (hRect.top + hRect.height / 2 - nodeRect.top) / zoom
    store.setHandleOffset(props.node.id, id, { x: offsetX, y: offsetY, type })
  })
}

const measureNodeSize = () => {
  if (!el.value) return
  const rect = el.value.getBoundingClientRect()
  const zoom = viewport.value.zoom || 1
  // Размер в canvas-pixels (без zoom). При zoom=0.5 rect.width вдвое меньше CSS-pixel.
  store.updateNodeSize(props.node.id, rect.width / zoom, rect.height / zoom)
  measureHandles()
}

onMounted(() => {
  if (!el.value) return
  store.registerNodeElement(props.node.id, el.value, props.node.position)
  // Измеряем размер ноды + handles после первого layout.
  requestAnimationFrame(() => measureNodeSize())
  // ResizeObserver — на случай если размер ноды меняется (например, condition с разным числом веток).
  if (typeof ResizeObserver !== 'undefined') {
    const ro = new ResizeObserver(() => measureNodeSize())
    ro.observe(el.value)
    onBeforeUnmount(() => ro.disconnect())
  }
})

onBeforeUnmount(() => {
  store.unregisterNodeElement(props.node.id)
})
</script>

<style scoped>
.custom-flow-node {
  /* GPU-слой только во время драга — снижает количество постоянных слоёв. */
  transition: none;
}
.custom-flow-node.is-dragging {
  z-index: 10;
}
</style>
