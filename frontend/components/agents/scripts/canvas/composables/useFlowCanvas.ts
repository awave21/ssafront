/**
 * useFlowCanvas — центральный store позиций нод + RAF-flush.
 *
 * КЛЮЧЕВОЕ: positions хранятся в обычном Map (НЕ reactive). Drag обновляет Map
 * напрямую и пишет transform в DOM через requestAnimationFrame. Vue узнаёт о
 * новых позициях ТОЛЬКО на drag-stop через `commitPositions()`.
 *
 * Это устраняет reactivity overhead на каждый mousemove — главную причину лагов
 * Vue Flow.
 */
import { shallowRef, type Ref } from 'vue'

export type NodePosition = { x: number; y: number }
export type NodeMeta = { id: string; type?: string; data?: Record<string, unknown> }
export type EdgeMeta = { id: string; source: string; target: string; sourceHandle?: string | null; targetHandle?: string | null }

/** Bbox ноды в координатах канваса — для расчёта edge endpoints. */
export type NodeBox = NodePosition & { width: number; height: number }

/** Offset центра handle относительно top-left ноды (в canvas-pixels). */
export type HandleOffset = { x: number; y: number; type: 'source' | 'target' }

export interface FlowCanvasStore {
  /** Position update с RAF-batched DOM apply. */
  updatePosition: (id: string, pos: NodePosition) => void
  /** Текущая позиция ноды (read). */
  getPosition: (id: string) => NodePosition | undefined
  /** Регистрация DOM-элемента ноды (вызывается из CustomFlowNode onMounted). */
  registerNodeElement: (id: string, el: HTMLElement, initialPos: NodePosition) => void
  /** Unregister на unmount. */
  unregisterNodeElement: (id: string) => void
  /** Обновить размер ноды (после первого layout). */
  updateNodeSize: (id: string, w: number, h: number) => void
  /** Bbox ноды для edge-path computation. */
  getNodeBox: (id: string) => NodeBox | undefined
  /** Установить offset handle (центр) относительно top-left ноды. */
  setHandleOffset: (nodeId: string, handleId: string, offset: HandleOffset) => void
  /** Получить offset handle для расчёта endpoints рёбер. */
  getHandleOffset: (nodeId: string, handleId: string) => HandleOffset | undefined
  /** Регистрация edge-зависимости (для частичного flush'а). */
  registerEdge: (edge: EdgeMeta) => void
  unregisterEdge: (edgeId: string) => void
  /** Set dirty edge IDs that need path repaint — используется EdgeLayer. */
  dirtyEdgeIds: Set<string>
  /** Сигнал для EdgeLayer'а что появились грязные edges (reactive). */
  flushTick: Ref<number>
  /** Sync текущих позиций Map в Vue ref (вызывается на drag-stop для persistence). */
  commitPositions: (nodes: Ref<NodeMeta[]>) => void
  /** Bbox всех нод — для fitView. */
  getAllNodesBounds: () => { minX: number; minY: number; maxX: number; maxY: number } | null
  /** Получить все edges (read-only). */
  getEdges: () => readonly EdgeMeta[]
}

export function useFlowCanvas(): FlowCanvasStore {
  // Hot-path state — НЕ reactive, чтобы не платить за proxy на каждом mousemove.
  const positions = new Map<string, NodePosition>()
  const sizes = new Map<string, { width: number; height: number }>()
  const nodeElements = new Map<string, HTMLElement>()
  const edges = new Map<string, EdgeMeta>()
  /** Offset центра каждого handle относительно top-left ноды (canvas-pixels). */
  const handleOffsetsByNode = new Map<string, Map<string, HandleOffset>>()
  /** Adjacency: какие edge-ids зависят от движения этой ноды. */
  const edgesByNode = new Map<string, Set<string>>()

  const dirtyNodes = new Set<string>()
  const dirtyEdgeIds = new Set<string>()
  /** Reactive счётчик кадров — EdgeLayer слушает и перерисовывает грязные пути. */
  const flushTick = shallowRef(0)

  let rafId: number | null = null

  const scheduleFlush = () => {
    if (rafId !== null) return
    rafId = requestAnimationFrame(flush)
  }

  const flush = () => {
    rafId = null
    // 1) Применяем transform на DOM-элементы напрямую (вне Vue).
    for (const id of dirtyNodes) {
      const pos = positions.get(id)
      const el = nodeElements.get(id)
      if (!pos || !el) continue
      // translate3d промоутит layer на GPU, transform применяется на compositor.
      el.style.transform = `translate3d(${pos.x}px, ${pos.y}px, 0)`
      // Все рёбра, связанные с этой нодой → грязные.
      const adj = edgesByNode.get(id)
      if (adj) for (const eid of adj) dirtyEdgeIds.add(eid)
    }
    dirtyNodes.clear()
    // 2) Триггерим EdgeLayer reactively (он сам прочитает dirtyEdgeIds и перерисует пути).
    if (dirtyEdgeIds.size > 0) flushTick.value++
  }

  const updatePosition = (id: string, pos: NodePosition) => {
    positions.set(id, pos)
    dirtyNodes.add(id)
    scheduleFlush()
  }

  const getPosition = (id: string) => positions.get(id)

  const registerNodeElement = (id: string, el: HTMLElement, initialPos: NodePosition) => {
    nodeElements.set(id, el)
    if (!positions.has(id)) positions.set(id, initialPos)
    // Применяем стартовый transform сразу.
    const pos = positions.get(id)!
    el.style.transform = `translate3d(${pos.x}px, ${pos.y}px, 0)`
  }

  const unregisterNodeElement = (id: string) => {
    nodeElements.delete(id)
    sizes.delete(id)
    edgesByNode.delete(id)
    handleOffsetsByNode.delete(id)
  }

  const setHandleOffset = (nodeId: string, handleId: string, offset: HandleOffset) => {
    let map = handleOffsetsByNode.get(nodeId)
    if (!map) {
      map = new Map()
      handleOffsetsByNode.set(nodeId, map)
    }
    const prev = map.get(handleId)
    if (prev && prev.x === offset.x && prev.y === offset.y && prev.type === offset.type) return
    map.set(handleId, offset)
    // Все edges связанные с этой нодой зависят от позиций handles → пометить dirty.
    const adj = edgesByNode.get(nodeId)
    if (adj) {
      for (const eid of adj) dirtyEdgeIds.add(eid)
      flushTick.value++
    }
  }

  const getHandleOffset = (nodeId: string, handleId: string): HandleOffset | undefined => {
    return handleOffsetsByNode.get(nodeId)?.get(handleId)
  }

  const updateNodeSize = (id: string, w: number, h: number) => {
    const prev = sizes.get(id)
    if (prev && prev.width === w && prev.height === h) return
    sizes.set(id, { width: w, height: h })
    // Все edges связанные с нодой нужно пересчитать (endpoints зависят от размера).
    const adj = edgesByNode.get(id)
    if (adj) {
      for (const eid of adj) dirtyEdgeIds.add(eid)
      flushTick.value++
    }
  }

  const getNodeBox = (id: string): NodeBox | undefined => {
    const pos = positions.get(id)
    const size = sizes.get(id)
    if (!pos) return undefined
    return {
      x: pos.x,
      y: pos.y,
      width: size?.width ?? 220,
      height: size?.height ?? 64,
    }
  }

  const registerEdge = (edge: EdgeMeta) => {
    edges.set(edge.id, edge)
    let srcAdj = edgesByNode.get(edge.source)
    if (!srcAdj) { srcAdj = new Set(); edgesByNode.set(edge.source, srcAdj) }
    srcAdj.add(edge.id)
    let tgtAdj = edgesByNode.get(edge.target)
    if (!tgtAdj) { tgtAdj = new Set(); edgesByNode.set(edge.target, tgtAdj) }
    tgtAdj.add(edge.id)
    dirtyEdgeIds.add(edge.id)
    flushTick.value++
  }

  const unregisterEdge = (edgeId: string) => {
    const edge = edges.get(edgeId)
    if (!edge) return
    edges.delete(edgeId)
    edgesByNode.get(edge.source)?.delete(edgeId)
    edgesByNode.get(edge.target)?.delete(edgeId)
    dirtyEdgeIds.delete(edgeId)
  }

  const commitPositions = (nodesRef: Ref<NodeMeta[]>) => {
    // Создаём новый массив (не deep clone, только верхний уровень) с обновлёнными position.
    // ТОЛЬКО для нод, чьи позиции реально изменились — иначе ссылка остаётся той же
    // (важно для v-memo на UniformNode: data reference stable → нет re-render).
    const list = nodesRef.value
    let changed = false
    const next = list.map((n) => {
      const newPos = positions.get(n.id)
      if (!newPos) return n
      if ((n as { position?: NodePosition }).position?.x === newPos.x
        && (n as { position?: NodePosition }).position?.y === newPos.y) return n
      changed = true
      return { ...n, position: { ...newPos } }
    })
    if (changed) nodesRef.value = next as NodeMeta[]
  }

  const getAllNodesBounds = () => {
    if (positions.size === 0) return null
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const [id, pos] of positions) {
      const size = sizes.get(id) ?? { width: 220, height: 64 }
      if (pos.x < minX) minX = pos.x
      if (pos.y < minY) minY = pos.y
      if (pos.x + size.width > maxX) maxX = pos.x + size.width
      if (pos.y + size.height > maxY) maxY = pos.y + size.height
    }
    return { minX, minY, maxX, maxY }
  }

  const getEdges = (): readonly EdgeMeta[] => Array.from(edges.values())

  return {
    updatePosition,
    getPosition,
    registerNodeElement,
    unregisterNodeElement,
    updateNodeSize,
    getNodeBox,
    setHandleOffset,
    getHandleOffset,
    registerEdge,
    unregisterEdge,
    dirtyEdgeIds,
    flushTick,
    commitPositions,
    getAllNodesBounds,
    getEdges,
  }
}
