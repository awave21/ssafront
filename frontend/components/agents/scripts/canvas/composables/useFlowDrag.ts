/**
 * useFlowDrag — drag менеджер на Pointer Events.
 *
 * Использует Pointer Capture чтобы получать pointermove даже когда курсор вышел
 * за пределы ноды. Обновления позиции идут через store.updatePosition (RAF-batched).
 * Vue реактивность не задействована в hot-path.
 */
import type { FlowCanvasStore, NodePosition } from './useFlowCanvas'
import type { Viewport } from './useFlowViewport'
import type { Ref } from 'vue'

export interface FlowDragHandlers {
  onPointerDown: (e: PointerEvent, nodeId: string) => void
}

export interface UseFlowDragOptions {
  store: FlowCanvasStore
  viewport: Ref<Viewport>
  /** Эмитится в начале реального драга (после первого movement, не на mousedown). */
  onDragStart?: (nodeId: string) => void
  /** Эмитится по drag-stop с новой позицией. */
  onDragStop?: (nodeId: string, position: NodePosition) => void
  /** Минимальное расстояние в screen-px чтобы считать что начался драг (отделяет click от drag). */
  dragThreshold?: number
}

export function useFlowDrag(options: UseFlowDragOptions): FlowDragHandlers {
  const { store, viewport, onDragStart, onDragStop } = options
  const dragThreshold = options.dragThreshold ?? 3

  const onPointerDown = (e: PointerEvent, nodeId: string) => {
    // Игнорируем правый клик / средний клик.
    if (e.button !== 0) return
    // Если событие пришло с handle/connect-element — drag НЕ ноды, а connection.
    // Здесь это handled выше по цепочке (handle сам перехватит pointerdown).

    const startScreenX = e.clientX
    const startScreenY = e.clientY
    const origin = store.getPosition(nodeId)
    if (!origin) return

    const target = e.currentTarget as HTMLElement | null
    if (!target) return

    let dragStarted = false

    const onMove = (ev: PointerEvent) => {
      const dx = ev.clientX - startScreenX
      const dy = ev.clientY - startScreenY
      // Threshold: пока расстояние <3px — это потенциальный клик, не драг.
      if (!dragStarted) {
        if (Math.abs(dx) < dragThreshold && Math.abs(dy) < dragThreshold) return
        dragStarted = true
        // Захватываем pointer ТОЛЬКО когда драг точно начался.
        try { target.setPointerCapture(ev.pointerId) }
        catch { /* ignore */ }
        onDragStart?.(nodeId)
      }
      // Конвертируем экранный delta в координаты канваса (учёт zoom).
      const flowDx = dx / viewport.value.zoom
      const flowDy = dy / viewport.value.zoom
      store.updatePosition(nodeId, { x: origin.x + flowDx, y: origin.y + flowDy })
    }

    const onUp = (ev: PointerEvent) => {
      target.removeEventListener('pointermove', onMove)
      target.removeEventListener('pointerup', onUp)
      target.removeEventListener('pointercancel', onUp)
      try { target.releasePointerCapture(ev.pointerId) }
      catch { /* ignore */ }
      if (dragStarted) {
        const finalPos = store.getPosition(nodeId)
        if (finalPos) onDragStop?.(nodeId, finalPos)
      }
      // Если drag не начался — был обычный клик, его обработает родительский @click.
    }

    target.addEventListener('pointermove', onMove)
    target.addEventListener('pointerup', onUp)
    target.addEventListener('pointercancel', onUp)
  }

  return { onPointerDown }
}

/**
 * Pan канваса при mousedown на пустом месте + zoom через wheel.
 */
export interface UseFlowPanZoomOptions {
  viewport: Ref<Viewport>
  setViewport: (vp: Partial<Viewport>) => void
  zoomAtPoint: (factor: number, screenPoint: { x: number; y: number }, canvasRect: DOMRect) => void
  panBy: (dx: number, dy: number) => void
}

export function useFlowPanZoom(options: UseFlowPanZoomOptions) {
  const { panBy, zoomAtPoint } = options

  const onPanePointerDown = (e: PointerEvent, paneEl: HTMLElement) => {
    if (e.button !== 0) return
    const startX = e.clientX, startY = e.clientY
    let started = false
    paneEl.style.cursor = 'grabbing'
    const onMove = (ev: PointerEvent) => {
      const dx = ev.clientX - startX
      const dy = ev.clientY - startY
      if (!started) {
        if (Math.abs(dx) < 2 && Math.abs(dy) < 2) return
        started = true
        try { paneEl.setPointerCapture(ev.pointerId) }
        catch { /* ignore */ }
      }
      // Pan moves the viewport by screen pixels (no zoom division — viewport.x/y are in screen pixels).
      panBy(ev.movementX, ev.movementY)
    }
    const onUp = (ev: PointerEvent) => {
      paneEl.removeEventListener('pointermove', onMove)
      paneEl.removeEventListener('pointerup', onUp)
      paneEl.removeEventListener('pointercancel', onUp)
      try { paneEl.releasePointerCapture(ev.pointerId) }
      catch { /* ignore */ }
      paneEl.style.cursor = ''
    }
    paneEl.addEventListener('pointermove', onMove)
    paneEl.addEventListener('pointerup', onUp)
    paneEl.addEventListener('pointercancel', onUp)
  }

  const onWheel = (e: WheelEvent, canvasRect: DOMRect) => {
    // Pinch-zoom (ctrlKey true on trackpad pinch) или wheel-up/down.
    e.preventDefault()
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1
    zoomAtPoint(factor, { x: e.clientX, y: e.clientY }, canvasRect)
  }

  return { onPanePointerDown, onWheel }
}
