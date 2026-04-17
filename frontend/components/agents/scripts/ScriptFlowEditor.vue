<template>
  <div class="flex h-full flex-col overflow-hidden bg-background" @drop="onDrop" @dragover="onDragOver">
    <div class="relative flex-1 overflow-hidden">
      <VueFlow
        v-model:nodes="nodes"
        v-model:edges="edges"
        :default-viewport="defaultViewport"
        :connect-on-click="false"
        :default-edge-options="defaultEdgeOptions"
        :connection-line-type="ConnectionLineType.Bezier"
        :connection-line-style="{ stroke: '#6366f1', strokeWidth: 2, strokeDasharray: '6 3' }"
        class="h-full w-full bg-muted/10"
        fit-view-on-init
        :node-types="nodeTypes"
        @connect="onConnect"
        @node-click="onNodeClick"
        @edge-click="onEdgeClick"
        @pane-click="onPaneClick"
      >
        <Background :gap="20" pattern-color="#94a3b8" :size="1" />

        <Controls position="bottom-right" class="!m-4 !border-none !bg-transparent !shadow-none">
          <ControlButton title="Сбросить вид" @click="resetView">
            <Maximize class="h-4 w-4" />
          </ControlButton>
        </Controls>

        <!-- Node Library Panel -->
        <Panel position="top-right" class="flex flex-col gap-2 p-3">
          <div class="rounded-xl border border-border bg-card/95 p-2 shadow-xl backdrop-blur-md w-52">
            <button
              type="button"
              class="w-full flex items-center justify-between rounded-lg border border-border px-2.5 py-1.5 text-[11px] font-medium hover:bg-muted/40 transition-colors"
              @click="showConstraintEdges = !showConstraintEdges"
            >
              <span>Обязательные связи</span>
              <span :class="showConstraintEdges ? 'text-primary' : 'text-muted-foreground'">
                {{ showConstraintEdges ? 'ON' : 'OFF' }}
              </span>
            </button>
          </div>

          <div class="flex flex-col gap-1.5 rounded-xl border border-border bg-card/95 p-3 shadow-xl backdrop-blur-md w-52">
            <h4 class="text-[10px] font-bold uppercase tracking-widest text-muted-foreground px-1 mb-1">Типы узлов</h4>
            <DraggableNodeItem
              v-for="nt in NODE_PALETTE"
              :key="nt.type"
              :type="nt.type"
              :label="nt.label"
              :description="nt.description"
              :color="nt.color"
              :emoji="nt.emoji"
            />
          </div>
        </Panel>
      </VueFlow>

      <!-- Edge delete popup (click on edge to delete it) -->
      <Transition
        enter-active-class="transition-all duration-150 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition-all duration-100 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
        <div
          v-if="edgeLabelPopup.visible"
          class="absolute z-50 flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 shadow-2xl"
          :style="{ left: `${edgeLabelPopup.x}px`, top: `${edgeLabelPopup.y}px` }"
        >
          <span class="text-[11px] text-muted-foreground">Удалить линию?</span>
          <button
            class="rounded-lg bg-destructive/10 border border-destructive/30 px-3 py-1 text-xs font-bold text-destructive hover:bg-destructive/20 transition-colors"
            @click="deleteSelectedEdge"
          >Удалить</button>
          <button
            class="rounded-lg border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted transition-colors"
            @click="closeEdgeLabelPopup"
          >✕</button>
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, markRaw, nextTick, provide, computed } from 'vue'
import {
  VueFlow, useVueFlow, ConnectionLineType,
  type Node, type Edge as FlowEdge, type XYPosition,
  type Connection, type EdgeMouseEvent, Panel,
} from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls, ControlButton } from '@vue-flow/controls'
import { Maximize } from 'lucide-vue-next'
import ExpertNode from './ExpertNode.vue'
import DraggableNodeItem from './DraggableNodeItem.vue'
import { NODE_TYPE_COLORS } from '~/types/scriptFlow'

const NODE_PALETTE = [
  { type: 'trigger',   label: 'Триггер',    description: 'Входная точка',      color: NODE_TYPE_COLORS.trigger,   emoji: '⚡' },
  { type: 'expertise', label: 'Экспертиза', description: 'Знания + подход',    color: NODE_TYPE_COLORS.expertise, emoji: '🧠' },
  { type: 'question',  label: 'Вопрос',     description: 'Вопрос клиенту',     color: NODE_TYPE_COLORS.question,  emoji: '❓' },
  { type: 'condition', label: 'Условие',    description: 'По ответу клиента',  color: NODE_TYPE_COLORS.condition, emoji: '🔀' },
  { type: 'goto',      label: 'Переход',    description: 'В другой поток',     color: NODE_TYPE_COLORS.goto,      emoji: '➡️' },
  { type: 'business_rule', label: 'Бизнес-правило', description: 'Правило для сущности', color: NODE_TYPE_COLORS.business_rule, emoji: '📋' },
  { type: 'end',       label: 'Конец',      description: 'Завершение ветки',   color: NODE_TYPE_COLORS.end,       emoji: '🔴' },
]

import '@vue-flow/core/dist/style.css'
import '@vue-flow/controls/dist/style.css'

const props = defineProps<{
  revision: number
  flowDefinition: Record<string, unknown>
  varNames?: string[]
  serviceOptions?: Array<{ id: string; name: string; is_enabled?: boolean }>
  employeeOptions?: Array<{ id: string; name: string; active?: boolean }>
}>()

const emit = defineEmits<{
  (e: 'update:flowDefinition', v: Record<string, unknown>): void
  (e: 'selectNode', id: string | null): void
}>()

// ── Expanded node state (provide to ExpertNode children) ─────────────────────
const expandedNodeId = ref<string | null>(null)
provide('expandedNodeId', expandedNodeId)
provide('setExpandedNodeId', (id: string | null) => { expandedNodeId.value = id })
provide('flowVarNames', computed(() => props.varNames ?? []))
provide('flowServiceOptions', computed(() => props.serviceOptions ?? []))
provide('flowEmployeeOptions', computed(() => props.employeeOptions ?? []))

const { project, fitView, addEdges } = useVueFlow()

const defaultEdgeOptions = {
  type: 'default',
  animated: false,
  style: { stroke: 'rgba(99,102,241,0.5)', strokeWidth: 2 },
  labelStyle: { fill: 'hsl(var(--foreground))', fontWeight: 600, fontSize: 11 },
  labelBgStyle: { fill: 'hsl(var(--card))', rx: 6, ry: 6 },
  labelBgPadding: [6, 4] as [number, number],
}

// ── Edge label popup ─────────────────────────────────────────────────────────
const edgeLabelInputRef = ref<HTMLInputElement | null>(null)
const edgeLabelPopup = ref({
  visible: false,
  edgeId: '',
  label: '',
  x: 0,
  y: 0,
})

// All node types use ExpertNode — the visual is differentiated by node.data.node_type
const nodeTypes = {
  expert:   markRaw(ExpertNode),
  trigger:  markRaw(ExpertNode),
  expertise: markRaw(ExpertNode),
  question: markRaw(ExpertNode),
  condition: markRaw(ExpertNode),
  goto:     markRaw(ExpertNode),
  end:      markRaw(ExpertNode),
}

const defaultViewport = { x: 0, y: 0, zoom: 0.8 }
const CONSTRAINT_EDGE_PREFIX = 'cst-'

function isXYPosition(p: unknown): p is XYPosition {
  if (typeof p !== 'object' || p === null) return false
  const o = p as { x?: unknown; y?: unknown }
  return typeof o.x === 'number' && typeof o.y === 'number'
}

function parseFlowNodes(raw: unknown): Node[] {
  if (!Array.isArray(raw)) return []
  const out: Node[] = []
  for (const item of raw) {
    if (typeof item !== 'object' || item === null) continue
    const o = item as Record<string, unknown>
    if (typeof o.id !== 'string' || !isXYPosition(o.position)) continue
    out.push({
      ...item,
      type: o.type || 'expert', // Default to expert type
    } as Node)
  }
  return out
}

function parseFlowEdges(raw: unknown): FlowEdge[] {
  if (!Array.isArray(raw)) return []
  const out: FlowEdge[] = []
  for (const item of raw) {
    if (typeof item !== 'object' || item === null) continue
    const o = item as Record<string, unknown>
    if (typeof o.id !== 'string' || typeof o.source !== 'string' || typeof o.target !== 'string') {
      continue
    }
    // Force bezier curve; strip any stored labels (conditions live on nodes now)
    const { label: _label, ...rest } = item as Record<string, unknown>
    void _label
    const edgeId = typeof o.id === 'string' ? o.id : ''
    if (edgeId.startsWith(CONSTRAINT_EDGE_PREFIX)) continue
    out.push({ ...rest, type: 'default' } as FlowEdge)
  }
  return out
}

const defaultNodes = (): Node[] => [
  {
    id: 'n1',
    type: 'expert',
    position: { x: 250, y: 150 },
    data: {
      title: 'Триггер',
      node_type: 'trigger',
      situation: 'Когда уместен этот поток',
      is_entry_point: true,
    },
  },
]

const nodes = ref<Node[]>([])
const edges = ref<FlowEdge[]>([])
const selectedId = ref<string | null>(null)
const showConstraintEdges = ref(true)

const nodeRefOptions = computed(() =>
  nodes.value.map((n) => {
    const data = (n.data || {}) as Record<string, unknown>
    const title = typeof data.title === 'string' && data.title.trim() ? data.title : n.id
    const nodeType = typeof data.node_type === 'string' ? data.node_type : String(n.type || '')
    return {
      id: String(n.id),
      title,
      node_type: nodeType,
    }
  }),
)
provide('flowNodeRefOptions', nodeRefOptions)

let idCounter = 1

const rebuildConstraintEdges = () => {
  const baseEdges = edges.value.filter((e) => !String(e.id || '').startsWith(CONSTRAINT_EDGE_PREFIX))
  if (!showConstraintEdges.value) {
    edges.value = [...baseEdges]
    return
  }
  const generated: FlowEdge[] = []

  for (const node of nodes.value) {
    const targetId = String(node.id || '')
    const data = (node.data || {}) as Record<string, unknown>
    const constraints = (data.constraints && typeof data.constraints === 'object')
      ? data.constraints as { must_follow_node_refs?: string[] }
      : {}
    const mustFollow = Array.isArray(constraints.must_follow_node_refs)
      ? constraints.must_follow_node_refs.filter((x) => typeof x === 'string' && x.trim())
      : []
    for (const sourceId of mustFollow) {
      if (!nodes.value.some((n) => String(n.id) === sourceId)) continue
      if (sourceId === targetId) continue
      generated.push({
        id: `${CONSTRAINT_EDGE_PREFIX}${sourceId}->${targetId}`,
        source: sourceId,
        target: targetId,
        type: 'default',
        label: 'must_follow',
        selectable: false,
        updatable: false,
        style: {
          stroke: '#0ea5e9',
          strokeWidth: 2,
          strokeDasharray: '4 3',
        },
        data: { isConstraint: true },
      } as FlowEdge)
    }
  }

  edges.value = [...baseEdges, ...generated]
}

const syncFromProps = () => {
  const d = props.flowDefinition || {}
  const rawNodes = d.nodes
  const rawEdges = d.edges
  const parsedNodes = parseFlowNodes(
    Array.isArray(rawNodes) ? JSON.parse(JSON.stringify(rawNodes)) : [],
  )
  if (parsedNodes.length > 0) {
    nodes.value = parsedNodes
    let maxN = 0
    for (const n of nodes.value) {
      const id = String((n as { id?: string }).id || '')
      const m = /^n(\d+)$/.exec(id)
      if (m) maxN = Math.max(maxN, parseInt(m[1], 10))
    }
    idCounter = maxN || nodes.value.length
  } else {
    nodes.value = defaultNodes()
    idCounter = 1
  }
  edges.value = parseFlowEdges(Array.isArray(rawEdges) ? JSON.parse(JSON.stringify(rawEdges)) : [])
  rebuildConstraintEdges()
}

watch(
  () => props.revision,
  () => {
    syncFromProps()
  },
  { immediate: true },
)

const pushEmit = () => {
  const vp =
    (props.flowDefinition.viewport as Record<string, unknown> | undefined) || defaultViewport
  emit('update:flowDefinition', {
    nodes: nodes.value,
    edges: edges.value.filter((e) => !String(e.id || '').startsWith(CONSTRAINT_EDGE_PREFIX)),
    viewport: vp,
  })
}

watch(
  [nodes, edges],
  () => {
    pushEmit()
  },
  { deep: true },
)

watch(
  nodes,
  () => {
    rebuildConstraintEdges()
  },
  { deep: true },
)

watch(showConstraintEdges, () => {
  rebuildConstraintEdges()
})


// ── Connect handler ───────────────────────────────────────────────────────────
const onConnect = (connection: Connection) => {
  const newEdge: FlowEdge = {
    id: `e-${connection.source}-${connection.target}-${Date.now()}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle ?? undefined,
    targetHandle: connection.targetHandle ?? undefined,
    ...defaultEdgeOptions,
  }
  addEdges([newEdge])
  rebuildConstraintEdges()
}

const onNodeClick = (evt: { node?: { id: string } }) => {
  const id = evt.node?.id ?? null
  selectedId.value = id
  // Toggle expansion: clicking the same node collapses it, clicking a new node expands it
  expandedNodeId.value = expandedNodeId.value === id ? null : id
  closeEdgeLabelPopup()
  emit('selectNode', id)
}

const onEdgeClick = ({ edge, event }: EdgeMouseEvent) => {
  const clientX = event instanceof MouseEvent ? event.clientX : (event as TouchEvent).touches[0]?.clientX ?? 0
  const clientY = event instanceof MouseEvent ? event.clientY : (event as TouchEvent).touches[0]?.clientY ?? 0
  openEdgeLabelPopup(edge.id, '', clientX - 80, clientY + 10)
}

const onPaneClick = () => {
  selectedId.value = null
  expandedNodeId.value = null
  closeEdgeLabelPopup()
  emit('selectNode', null)
}

const openEdgeLabelPopup = (edgeId: string, label: string, x: number, y: number) => {
  edgeLabelPopup.value = { visible: true, edgeId, label, x, y }
  nextTick(() => edgeLabelInputRef.value?.focus())
}

const closeEdgeLabelPopup = () => {
  edgeLabelPopup.value.visible = false
}

const deleteSelectedEdge = () => {
  const { edgeId } = edgeLabelPopup.value
  if (String(edgeId || '').startsWith(CONSTRAINT_EDGE_PREFIX)) {
    closeEdgeLabelPopup()
    return
  }
  edges.value = edges.value.filter(e => e.id !== edgeId)
  rebuildConstraintEdges()
  closeEdgeLabelPopup()
}

const resetView = () => {
  fitView()
}

// Drag and Drop Logic
const onDragOver = (event: DragEvent) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/vueflow')
  if (!type) return

  const position = project({
    x: event.clientX - 40, // Offset for better placement
    y: event.clientY - 40,
  })

  idCounter += 1
  const id = `n${idCounter}`
  
  const paletteItem = NODE_PALETTE.find(n => n.type === type)
  const newNode: Node = {
    id,
    type: 'expert',  // all rendered with ExpertNode component
    position,
    data: {
      title: paletteItem?.label ?? 'Новый узел',
      node_type: type,
      situation: '',
      is_entry_point: type === 'trigger' || type === 'expertise' || type === 'question',
    },
  }

  nodes.value = [...nodes.value, newNode]
  rebuildConstraintEdges()
}

defineExpose({
  selectedId,
  nodes,
  edges,
})
</script>

<style>
/* All custom node types share the same transparent wrapper */
.vue-flow__node-expert,
.vue-flow__node-trigger,
.vue-flow__node-expertise,
.vue-flow__node-question,
.vue-flow__node-condition,
.vue-flow__node-goto,
.vue-flow__node-business_rule,
.vue-flow__node-end {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}

.vue-flow__handle {
  height: 12px !important;
  width: 12px !important;
  border: 2px solid white !important;
  background: #3b82f6 !important;
  transition: transform 0.2s ease;
}

.vue-flow__handle:hover {
  transform: scale(1.25);
}

.vue-flow__edge-path {
  stroke: rgba(59, 130, 246, 0.4) !important;
  stroke-width: 3px !important;
  transition: stroke 0.2s ease;
}

.vue-flow__edge-path:hover {
  stroke: #3b82f6 !important;
}

.vue-flow__controls-button {
  border-radius: 8px !important;
  border: 1px solid #e2e8f0 !important;
  background: rgba(255, 255, 255, 0.9) !important;
  color: #0f172a !important;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
  backdrop-filter: blur(4px) !important;
  transition: all 0.2s ease !important;
}

.vue-flow__controls-button:hover {
  background: #f1f5f9 !important;
  transform: scale(1.05);
}

.vue-flow__controls-button:active {
  transform: scale(0.95);
}

.vue-flow__minimap {
  border-radius: 12px !important;
  border: 1px solid #e2e8f0 !important;
  background: rgba(255, 255, 255, 0.8) !important;
  backdrop-filter: blur(4px) !important;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1) !important;
}
</style>
