/**
 * Viewport — состояние pan/zoom + утилиты конвертации координат.
 * Reactive, чтобы шаблоны (transform group, MiniMap) могли подписаться на изменение.
 */
import { ref, type Ref } from 'vue'

export type Viewport = { x: number; y: number; zoom: number }

export interface UseFlowViewportOptions {
  initial?: Viewport
  minZoom?: number
  maxZoom?: number
  zoomStep?: number
}

export function useFlowViewport(options: UseFlowViewportOptions = {}) {
  const minZoom = ref(options.minZoom ?? 0.2)
  const maxZoom = ref(options.maxZoom ?? 2)
  const zoomStep = options.zoomStep ?? 1.2

  const viewport = ref<Viewport>(options.initial ?? { x: 0, y: 0, zoom: 1 })

  /** Экранные координаты → координаты канваса (с учётом pan/zoom). */
  const screenToFlow = (screen: { x: number; y: number }, canvasRect: DOMRect): { x: number; y: number } => {
    const localX = screen.x - canvasRect.left
    const localY = screen.y - canvasRect.top
    return {
      x: (localX - viewport.value.x) / viewport.value.zoom,
      y: (localY - viewport.value.y) / viewport.value.zoom,
    }
  }

  /** Координаты канваса → экранные (с учётом pan/zoom). */
  const flowToScreen = (flow: { x: number; y: number }, canvasRect: DOMRect): { x: number; y: number } => {
    return {
      x: flow.x * viewport.value.zoom + viewport.value.x + canvasRect.left,
      y: flow.y * viewport.value.zoom + viewport.value.y + canvasRect.top,
    }
  }

  /** Алиас для совместимости с Vue Flow API. */
  const project = (screen: { x: number; y: number }, canvasRect: DOMRect) => screenToFlow(screen, canvasRect)

  const setViewport = (vp: Partial<Viewport>) => {
    viewport.value = {
      x: vp.x ?? viewport.value.x,
      y: vp.y ?? viewport.value.y,
      zoom: clampZoom(vp.zoom ?? viewport.value.zoom),
    }
  }

  const clampZoom = (z: number) => Math.max(minZoom.value, Math.min(maxZoom.value, z))

  /**
   * Зум вокруг точки (например, курсора при wheel-zoom).
   * Сохраняет точку под курсором на месте при изменении масштаба.
   */
  const zoomAtPoint = (factor: number, screenPoint: { x: number; y: number }, canvasRect: DOMRect) => {
    const oldZoom = viewport.value.zoom
    const newZoom = clampZoom(oldZoom * factor)
    if (newZoom === oldZoom) return

    const localX = screenPoint.x - canvasRect.left
    const localY = screenPoint.y - canvasRect.top
    // Точка в координатах канваса до zoom
    const flowX = (localX - viewport.value.x) / oldZoom
    const flowY = (localY - viewport.value.y) / oldZoom

    viewport.value = {
      zoom: newZoom,
      x: localX - flowX * newZoom,
      y: localY - flowY * newZoom,
    }
  }

  const zoomIn = () => {
    viewport.value = { ...viewport.value, zoom: clampZoom(viewport.value.zoom * zoomStep) }
  }
  const zoomOut = () => {
    viewport.value = { ...viewport.value, zoom: clampZoom(viewport.value.zoom / zoomStep) }
  }

  /** Сдвиг панели на dx,dy в screen pixels. */
  const panBy = (dx: number, dy: number) => {
    viewport.value = { ...viewport.value, x: viewport.value.x + dx, y: viewport.value.y + dy }
  }

  /**
   * Переместить view так, чтобы все ноды поместились с padding.
   * Передаём bbox в координатах канваса.
   */
  const fitBounds = (bounds: { minX: number; minY: number; maxX: number; maxY: number }, viewportSize: { width: number; height: number }, padding = 0.1) => {
    const w = bounds.maxX - bounds.minX
    const h = bounds.maxY - bounds.minY
    if (w <= 0 || h <= 0) return
    const padX = viewportSize.width * padding
    const padY = viewportSize.height * padding
    const zoomX = (viewportSize.width - 2 * padX) / w
    const zoomY = (viewportSize.height - 2 * padY) / h
    const newZoom = clampZoom(Math.min(zoomX, zoomY))
    const cx = bounds.minX + w / 2
    const cy = bounds.minY + h / 2
    viewport.value = {
      zoom: newZoom,
      x: viewportSize.width / 2 - cx * newZoom,
      y: viewportSize.height / 2 - cy * newZoom,
    }
  }

  const zoomMaxReached = () => viewport.value.zoom >= maxZoom.value
  const zoomMinReached = () => viewport.value.zoom <= minZoom.value

  return {
    viewport,
    minZoom: minZoom as Readonly<Ref<number>>,
    maxZoom: maxZoom as Readonly<Ref<number>>,
    setViewport,
    zoomAtPoint,
    zoomIn,
    zoomOut,
    panBy,
    fitBounds,
    screenToFlow,
    flowToScreen,
    project,
    zoomMaxReached,
    zoomMinReached,
  }
}
