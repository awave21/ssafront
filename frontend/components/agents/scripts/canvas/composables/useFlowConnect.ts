/**
 * useFlowConnect — drag-to-connect между handle'ами.
 *
 * Слушает pointerdown на [data-handle-type="source"], рисует "phantom" путь от
 * handle до курсора, и при pointerup на [data-handle-type="target"] эмитит
 * connect-событие с {source, target, sourceHandle, targetHandle}.
 */
import { ref, type Ref } from 'vue'
import type { Viewport } from './useFlowViewport'

export interface ConnectionInProgress {
  sourceNodeId: string
  sourceHandleId: string
  /** Стартовая точка в screen-координатах. */
  startScreen: { x: number; y: number }
  /** Текущая точка курсора в screen-координатах. */
  currentScreen: { x: number; y: number }
}

export interface ConnectionEndpoint {
  nodeId: string
  handleId: string
  handleType: 'source' | 'target'
}

export interface UseFlowConnectOptions {
  /** Эмитится когда соединение завершено успешно. */
  onConnect: (params: { source: string; target: string; sourceHandle: string; targetHandle: string }) => void
}

export function useFlowConnect(options: UseFlowConnectOptions) {
  const inProgress = ref<ConnectionInProgress | null>(null)

  /**
   * Парсит атрибуты [data-*] handle-элемента.
   */
  const parseHandleEl = (el: HTMLElement | null): ConnectionEndpoint | null => {
    if (!el) return null
    const handle = el.closest('[data-handle-id]') as HTMLElement | null
    if (!handle) return null
    const nodeId = handle.dataset.nodeId
    const handleId = handle.dataset.handleId
    const handleType = handle.dataset.handleType as 'source' | 'target' | undefined
    if (!nodeId || !handleId || !handleType) return null
    return { nodeId, handleId, handleType }
  }

  /**
   * Запускается на pointerdown handle-элемента.
   * Возвращает true если действительно начался connect-drag (нужно вызвать stopPropagation).
   */
  const tryStartConnect = (e: PointerEvent): boolean => {
    const ep = parseHandleEl(e.target as HTMLElement | null)
    if (!ep || ep.handleType !== 'source') return false

    e.stopPropagation()
    e.preventDefault()

    inProgress.value = {
      sourceNodeId: ep.nodeId,
      sourceHandleId: ep.handleId,
      startScreen: { x: e.clientX, y: e.clientY },
      currentScreen: { x: e.clientX, y: e.clientY },
    }

    const onMove = (ev: PointerEvent) => {
      if (!inProgress.value) return
      inProgress.value = {
        ...inProgress.value,
        currentScreen: { x: ev.clientX, y: ev.clientY },
      }
    }

    const onUp = (ev: PointerEvent) => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
      if (!inProgress.value) return
      // Определяем target handle под курсором.
      const dropEl = document.elementFromPoint(ev.clientX, ev.clientY) as HTMLElement | null
      const target = parseHandleEl(dropEl)
      if (target && target.handleType === 'target' && target.nodeId !== inProgress.value.sourceNodeId) {
        options.onConnect({
          source: inProgress.value.sourceNodeId,
          sourceHandle: inProgress.value.sourceHandleId,
          target: target.nodeId,
          targetHandle: target.handleId,
        })
      }
      inProgress.value = null
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return true
  }

  return {
    inProgress: inProgress as Readonly<Ref<ConnectionInProgress | null>>,
    tryStartConnect,
  }
}
